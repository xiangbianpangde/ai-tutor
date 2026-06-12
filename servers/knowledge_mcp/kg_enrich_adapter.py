"""build_knowledge_graph 的适配层。

depth=toc:     纯规则。从 markdown 的 #/## 抽 Concept 骨架 + prerequisite_strong 边。
depth=concept: TODO 下一切片：接 research_tool.ExtractResult.triples + LLM 二次增强
depth=full:    TODO 同上 + 难度评分 + embedding
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow
from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    QualityReport,
    Relation,
    SourceRef,
)
from shared.storage import RelationalStore

logger = get_logger("knowledge_mcp.kg_enrich")


_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")
_FENCE_RE = re.compile(r"^\s{0,3}(?P<marker>```|~~~)")


from shared.slug import slugify as _slug  # noqa: E402  function alias


def iter_markdown_lines(text: str) -> Iterator[tuple[int, str, bool]]:
    """逐行扫 markdown，yield (line_no, line, in_code)。

    跟踪 ```/~~~ 围栏开闭（围栏标记行本身也算 in_code）。采集语料含大量示例代码，
    代码里的 `# 注释` 不是章节标题——ACP 实测它们曾批量变成 KG 概念（#22）。
    """
    fence: str | None = None
    for line_no, line in enumerate(text.splitlines(), start=1):
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group("marker")
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            yield line_no, line, True
            continue
        yield line_no, line, fence is not None


def demote_headings(text: str, *, min_level: int) -> str:
    """把正文标题整体降级，使最小标题层级 ≥ min_level（fence 感知，封顶 6 级，只降不升）。

    合并语料会给每个来源加上层标题（`# 主题` / `## 来源`），来源正文里的 H1/H2
    若不降级会跳出所属层级，被 KG 当成顶层章节。
    """
    levels = [
        len(m.group("hashes"))
        for _no, line, in_code in iter_markdown_lines(text)
        if not in_code and (m := _HEADING_RE.match(line))
    ]
    shift = min_level - min(levels) if levels else 0
    if shift <= 0:
        return text

    out: list[str] = []
    for _no, line, in_code in iter_markdown_lines(text):
        m = None if in_code else _HEADING_RE.match(line)
        if m:
            level = min(len(m.group("hashes")) + shift, 6)
            out.append("#" * level + " " + m.group("title"))
        else:
            out.append(line)
    return "\n".join(out)


# 「非章节标题」过滤（#22 根因之一）：纯分隔线 / 来源文件名（01-edu.aliyun.com-087e03）/
# 含 URL / 超长 / 以句末标点结尾的整句。问号、叹号不算句末——「什么是大模型？」是合法标题。
# FIX-K（FastAPI web 语料复跑实测）：博客正文里**未围栏**的代码注释顶格出现时，
# `# 注释` 在 markdown 语法上就是合法标题，围栏跳过救不了——只能按文本特征过滤：
# 时间戳 / 裸代码文件名 / 装饰性注释（===== xx =====）/ 含 emoji·箭头 /
# 批注引导（正确：/注意：…）/ 含逗号或以冒号收尾的整句。
_NOISE_SEPARATOR_RE = re.compile(r"^[=\-_*~·•#>\s]+$")
_NOISE_SOURCE_FILE_RE = re.compile(r"^\d{1,3}-[\w.-]+-[0-9a-f]{4,12}$", re.IGNORECASE)
_NOISE_URL_RE = re.compile(r"\w+://|www\.")  # 任意 scheme（postgresql:// 也算）
_NOISE_ASSIGNMENT_RE = re.compile(r"""=\s*["']""")  # 代码赋值行（realm="protected"）
_NOISE_CODE_CALL_RE = re.compile(r"^[\w.]+\(.*\)\s*[:;]?$")  # 裸函数调用行 asyncio.run(x())
_NOISE_NO_WORDS_RE = re.compile(r"[\W\d_]+")  # 只有数字/标点（mkdocs 标注 "(1)!"）
# 英文整句注释（"Do some stuff to create..."）：≥4 词且 ≥2 个功能词
_EN_STOPWORDS = frozenset(
    "a an the this that these those is are was were be will would can could to of in on at "
    "for with and or some any do does did it its you your we our".split()
)
_NOISE_TIMESTAMP_RE = re.compile(
    r"^\d{4}[-/.年]\s?\d{1,2}[-/.月]\s?\d{1,2}日?([ T]\d{1,2}:\d{2}(:\d{2})?)?$"
)
_NOISE_BARE_FILENAME_RE = re.compile(  # 含相对路径形态 app/routers/users.py
    r"^[\w.\-/\\ ]{1,60}\.(py|pyc|ipynb|js|jsx|ts|tsx|mjs|json|jsonl|yaml|yml|toml|ini|cfg|conf"
    r"|env|md|rst|txt|html|htm|css|scss|sql|db|sh|bash|zsh|bat|ps1|dockerfile|lock|csv|tsv"
    r"|xml|proto|go|rs|java|kt|c|h|cpp|hpp)\s*(（.{0,16}）|\(.{0,16}\))?$",
    re.IGNORECASE,
)
_NOISE_REPO_PATH_RE = re.compile(r"\bat (main|master)$")  # GitHub 仓库路径页标题尾巴
_NOISE_DECORATED_RE = re.compile(r"^[=\-*~#]{3,}.*[=\-*~#]{3,}$")
_NOISE_DOTFILE_RE = re.compile(  # .env.production / .gitignore；放过 ".NET" 这类技术名
    r"^\.(env|git[\w-]*|docker[\w-]*|npmrc|babelrc|eslintrc[\w.]*|prettierrc[\w.]*"
    r"|editorconfig|venv)(\.[\w.-]+)?$",
    re.IGNORECASE,
)
# emoji / 箭头 / 装饰符号（✅👇→▶…）。刻意绕开 U+2460-24FF（①⑴ⓐ 枚举编号是合法标题）。
_NOISE_SYMBOL_RE = re.compile(
    "[\U0001F000-\U0001FAFF"  # emoji 主区（👇🔥📌…）
    "←-⇿"           # 箭头（→ ⇒）
    "⌀-⑟"           # 杂项技术符号（⌚⏰）
    "─-➿"           # 制表/几何/dingbats（▶ ■ ✅ ❌ ⚠ ➡）
    "⬀-⯿"           # 杂项符号与箭头（⬇ ⭐）
    "️]"                 # emoji 变体选择符
)
_NOISE_CALLOUT_RE = re.compile(
    r"^(正确|错误|注意|提示|警告|示例|例如|举例|说明|备注|详细介绍|tips?|note|warning)\s*[:：]",
    re.IGNORECASE,
)
# FIX-M：论文/文档骨架节名（换体裁攻击 2026-06-13 发现——学术论文 PDF 语料里
# 摘要/致谢/参考文献 占 3/19=15.8% 禁类）。只杀无歧义的纯骨架：引言/结论/相关工作
# 这类常含实质内容的结构节保留（宁可留弱概念，不误杀内容节）。
_NOISE_DOC_SKELETON_RE = re.compile(
    r"^(摘要|abstract|致谢|acknowledg(e)?ments?|参考文献|references?|bibliography"
    r"|目录|table\s+of\s+contents|附录\s*[A-Za-z一-十]?|appendix(\s+[A-Za-z])?"
    r"|索引|index|版权声明|copyright|免责声明|disclaimer|作者简介|about\s+the\s+authors?)$",
    re.IGNORECASE,
)
_MAX_TITLE_CHARS = 64
_SENTENCE_ENDINGS = ("。", "．", "；", ";", "：", ":", "，", ",")

# 来源标题的「站点/栏目」尾巴（`xxx - CSDN博客` / `xxx | 思否`）。仅当尾段命中
# 站点关键词才剥；命中后允许再剥一段短尾（作者名 / `- FastAPI` 这类链式尾巴）。
_SITE_SUFFIX_SEP_RE = re.compile(r"\s+[-|–—｜]+\s+")
_SITE_SUFFIX_KEYWORD_RE = re.compile(
    r"博客|笔记|技术栈|思否|segmentfault|掘金|知乎|简书|csdn|腾讯云|阿里云|社区|51cto"
    r"|infoq|开源中国|oschina|文档|教程|专栏|框架|百科|wiki|github|gitee|stack\s*overflow"
    r"|medium|博客园|bilibili|哔哩哔哩|^fastapi$|^pydantic$",
    re.IGNORECASE,
)


def strip_site_suffix(title: str) -> str:
    """剥掉来源页标题的站点尾巴：`路径参数 - FastAPI - FastAPI 框架` → `路径参数`。

    两遍：① 带空格分隔（` - `/` | `），命中站点关键词的尾段剥掉，之后允许再剥一段
    短作者尾；② 无空格连字符（`…IO堵塞-开发者社区-阿里云`），只剥关键词命中段。
    未剥离时原样返回（不重组字符串，避免把 `—`/`｜` 误改成 `-`）。
    """
    segments = _SITE_SUFFIX_SEP_RE.split(title)
    stripped_site = False
    popped = False
    while len(segments) > 1:
        tail = segments[-1].strip()
        if _SITE_SUFFIX_KEYWORD_RE.search(tail):
            segments.pop()
            stripped_site = popped = True
            continue
        # 站点尾段之前常挂作者名/产品名短尾，只在已剥过站点段后再剥一段
        if stripped_site and len(tail) <= 16:
            segments.pop()
            stripped_site = False
            popped = True
            continue
        break
    out = " - ".join(s.strip() for s in segments).strip() if popped else title

    # 第二遍：保留分隔符切分，剥尾后按原分隔符精确重建
    parts = re.split(r"([-—｜|])", out)
    while len(parts) > 2 and _SITE_SUFFIX_KEYWORD_RE.search(parts[-1].strip()):
        parts = parts[:-2]
    return "".join(parts).strip("-—｜| ").strip()


def is_noise_title(title: str) -> bool:
    """该标题是否不应成为 KG 概念。"""
    t = title.strip().strip("*_`~").strip()
    if not t:
        return True
    if _NOISE_SEPARATOR_RE.match(t):
        return True
    if _NOISE_SOURCE_FILE_RE.match(t):
        return True
    if _NOISE_URL_RE.search(t):
        return True
    if _NOISE_TIMESTAMP_RE.match(t):
        return True
    if _NOISE_BARE_FILENAME_RE.match(t):
        return True
    if _NOISE_DECORATED_RE.match(t):
        return True
    if _NOISE_SYMBOL_RE.search(t):
        return True
    if _NOISE_CALLOUT_RE.match(t):
        return True
    if _NOISE_DOC_SKELETON_RE.match(t):
        return True
    if "，" in t:  # 概念名不该是带逗号的整句（"创建一个线程池，比如最多4个线程"）
        return True
    if "！" in t[:-1] or "!" in t[:-1]:  # 中段感叹（"可以！async def 也支持"）；句尾感叹合法
        return True
    if _NOISE_ASSIGNMENT_RE.search(t):
        return True
    if _NOISE_NO_WORDS_RE.fullmatch(t):
        return True
    if _NOISE_DOTFILE_RE.match(t):
        return True
    if _NOISE_CODE_CALL_RE.match(t):
        return True
    if _NOISE_REPO_PATH_RE.search(t):
        return True
    if t.endswith(("...", "…")):  # 搜索结果页的截断标题（"…两种启动方式差异的 ..."）
        return True
    if " --" in t:  # 命令行标题（"启动：uvicorn main:app --reload"）
        return True
    words = re.findall(r"[A-Za-z']+", t)
    if (
        len(words) >= 4
        and not re.search(r"[一-鿿]", t)
        and sum(w.lower() in _EN_STOPWORDS for w in words) >= 2
    ):  # 英文整句注释（"Do some stuff to create the burgers"）
        return True
    if len(t) > _MAX_TITLE_CHARS:
        return True
    return t.endswith(_SENTENCE_ENDINGS)


def _iter_headings(markdown: str) -> Iterator[tuple[int, str, int]]:
    """逐行扫 markdown，yield (level, title, line_no)。跳过代码围栏内的行与噪声标题。"""
    for line_no, line, in_code in iter_markdown_lines(markdown):
        if in_code:
            continue
        m = _HEADING_RE.match(line)
        if not m:
            continue
        title = m.group("title").strip().strip("*_`~").strip()
        title = strip_site_suffix(title)
        if is_noise_title(title):
            continue
        yield len(m.group("hashes")), title, line_no


def _bloom(level: int) -> str:
    """章节深度粗映射 Bloom 层级。"""
    return {1: "remember", 2: "understand", 3: "apply", 4: "analyze"}.get(level, "understand")


def _build_concept(
    *,
    subject_slug: str,
    chapter_counters: list[int],
    title: str,
    level: int,
    source_file: str,
    line_no: int,
) -> Concept:
    chapter_id = ".".join(str(n) for n in chapter_counters)
    cid = f"{subject_slug}:{chapter_id}:{_slug(title)}"

    # toc 模式：所有难度字段用启发式默认值（标注 confidence=0.4 留给后续增强）
    return Concept(
        id=cid,
        names=[title],
        category="definition" if level <= 2 else "method",
        definition=title,
        informal_description=f"来自 {Path(source_file).name} 行 {line_no} 的章节标题",
        classification=ConceptClassification(
            bloom_level=_bloom(level),
            abstract_level=min(0.3 + 0.15 * (level - 1), 0.85),
            domain=subject_slug,
        ),
        difficulty=ConceptDifficulty(
            prereq_count=max(level - 1, 0),
            prereq_max_depth=max(level - 1, 0),
            formula_density=0.3,
            coupling=0.3,
            cognitive_load_estimate=0.4,
            typical_learning_time_min=30,
        ),
        confidence=0.4,  # toc 模式：低置信，预期后续 review_kg / concept 模式增强
        sources=[SourceRef(type="textbook", ref=Path(source_file).name, page=str(line_no))],
    )


def _build_toc(
    *,
    subject_slug: str,
    markdown_path: Path,
) -> tuple[list[Concept], list[Relation]]:
    """从 markdown 章节生成 Concept + prerequisite_strong 边。"""
    text = markdown_path.read_text(encoding="utf-8")
    concepts: list[Concept] = []
    edges: list[Relation] = []

    counters: list[int] = []
    # parent_at_level[i] = level-(i+1) 的最近祖先 concept id；同时维护 level 之上的祖先
    parent_at_level: list[str | None] = []
    # prev_sibling_at_level[i] = level-(i+1) 的同级前一个 concept id
    prev_sibling_at_level: list[str | None] = []

    for level, title, line_no in _iter_headings(text):
        # ---- 1) 更新 counters 到 level 长度 ----
        if len(counters) >= level:
            counters = counters[: level - 1] + [counters[level - 1] + 1]
        else:
            while len(counters) < level - 1:
                counters.append(1)
            counters.append(1)

        # ---- 2) 清掉比当前 level 更深的栈条目 ----
        # 进入新 level 时，更深层的 sibling/parent 信息全部失效
        del parent_at_level[level:]
        del prev_sibling_at_level[level:]

        # ---- 3) 读父亲 + 同级前驱 ----
        parent_id = parent_at_level[level - 2] if level >= 2 and len(parent_at_level) >= level - 1 else None
        prev_sibling_id = prev_sibling_at_level[level - 1] if len(prev_sibling_at_level) >= level else None

        # ---- 4) 创建 concept ----
        concept = _build_concept(
            subject_slug=subject_slug,
            chapter_counters=counters,
            title=title,
            level=level,
            source_file=str(markdown_path),
            line_no=line_no,
        )
        concepts.append(concept)

        # ---- 5) 加边 ----
        if parent_id and parent_id != concept.id:
            edges.append(
                Relation(
                    from_id=concept.id,
                    to_id=parent_id,
                    type="part_of",
                    weight=0.9,
                    explanation=f"{title} 是上级章节的子项",
                    confidence=0.7,
                )
            )
        if prev_sibling_id and prev_sibling_id != concept.id:
            edges.append(
                Relation(
                    from_id=prev_sibling_id,
                    to_id=concept.id,
                    type="prerequisite_strong",
                    weight=0.6,
                    explanation="教材顺序：前一节是后一节的前置",
                    confidence=0.5,
                )
            )

        # ---- 6) 把当前节点写入栈 ----
        while len(parent_at_level) < level:
            parent_at_level.append(None)
        parent_at_level[level - 1] = concept.id

        while len(prev_sibling_at_level) < level:
            prev_sibling_at_level.append(None)
        prev_sibling_at_level[level - 1] = concept.id

    return concepts, edges


_COVERAGE_GATE = 0.85       # 章节覆盖率门槛
_CATEGORY_SKEW_GATE = 0.9   # 单一类别占比超此值视为分布失衡
_CATEGORY_SKEW_MIN_N = 5    # 概念太少时不做分布检查（小样本无意义）


def _chapter_coverage(concepts: list[Concept]) -> float:
    """有真实定义（非占位标题）的概念占比。

    toc 骨架的 definition 直接等于标题（占位）；concept/full 富化后才有真实定义。
    覆盖率即"多少章节被真正充实"。
    """
    covered = sum(
        1 for c in concepts
        if c.definition.strip() and c.definition.strip() != c.names[0].strip()
    )
    return covered / len(concepts)


def _compute_quality(concepts: list[Concept], edges: list[Relation]) -> QualityReport:
    if not concepts:
        return QualityReport(
            overall="fail",
            chapter_coverage=0.0,
            isolated_nodes=0,
            cycles=0,
            avg_confidence=0.0,
            warnings=["KG 为空"],
        )
    node_ids = {c.id for c in concepts}
    connected = {e.from_id for e in edges} | {e.to_id for e in edges}
    isolated = node_ids - connected
    avg_conf = sum(c.confidence for c in concepts) / len(concepts)
    coverage = _chapter_coverage(concepts)

    warnings: list[str] = []
    if isolated:
        warnings.append(f"{len(isolated)} 个孤立节点（无边连接）")
    if avg_conf < 0.5:
        warnings.append(f"平均置信度 {avg_conf:.2f} 偏低，建议 review_kg 人工确认")

    # 结构化质量门（输出为告警，供人工 review_kg 审查，不强制 fail——
    # toc 骨架天然低覆盖/无示例，硬 fail 会误杀合法的骨架图）。
    # 1) 章节覆盖率 ≥ 85%
    if coverage < _COVERAGE_GATE:
        missing = len(concepts) - round(coverage * len(concepts))
        warnings.append(
            f"章节覆盖率 {coverage:.0%} < {_COVERAGE_GATE:.0%}"
            f"（约 {missing} 个概念仍是占位定义，建议 build concept/full 或 review_kg 补全）"
        )
    # 2) 每概念 ≥ 1 示例
    no_example = [c for c in concepts if not c.examples]
    if no_example:
        warnings.append(f"{len(no_example)}/{len(concepts)} 个概念缺少示例（建议每概念 ≥1 示例）")
    # 3) 定义/方法/定理 类别分布合理性（避免全是一种类别）
    cats = Counter(c.category for c in concepts)
    dominant = cats.most_common(1)[0]
    dominant_ratio = dominant[1] / len(concepts)
    if len(concepts) >= _CATEGORY_SKEW_MIN_N and dominant_ratio > _CATEGORY_SKEW_GATE:
        warnings.append(
            f"概念类别分布失衡：{dominant_ratio:.0%} 都是「{dominant[0]}」，"
            f"定义/方法/定理分布建议更均衡"
        )
    # 4) 重复概念名 —— 多源近重复语料未归并的典型症状。跨章同名小节（习题/小结）
    #    是合法的，所以只告警不静默去重；去重交给人工 update_kg merge_concepts。
    name_counts = Counter(c.names[0].strip() for c in concepts)
    dup_names = [n for n, cnt in name_counts.items() if cnt > 1]
    if dup_names:
        sample = "、".join(dup_names[:3])
        warnings.append(
            f"{len(dup_names)} 组重复概念名（如：{sample}）——若来自多源重复语料，"
            f"建议先整理语料或用 update_kg merge_concepts 归并"
        )

    return QualityReport(
        overall="pass_with_warnings" if warnings else "pass",
        chapter_coverage=round(coverage, 3),
        isolated_nodes=len(isolated),
        cycles=0,
        avg_confidence=avg_conf,
        warnings=warnings,
        suggestions=["运行 review_kg(mode='quick') 查看低置信度概念"] if warnings else [],
    )


def _to_mermaid(concepts: list[Concept], edges: list[Relation], max_nodes: int = 50) -> str:
    """生成 Mermaid 图。节点过多时截断。"""
    lines = ["graph TD"]
    for c in concepts[:max_nodes]:
        safe_label = c.names[0].replace('"', "'")
        lines.append(f'  {_safe_node_id(c.id)}["{safe_label}"]')
    for e in edges:
        if e.from_id in {c.id for c in concepts[:max_nodes]} and e.to_id in {
            c.id for c in concepts[:max_nodes]
        }:
            lines.append(
                f"  {_safe_node_id(e.from_id)} -->|{e.type}| {_safe_node_id(e.to_id)}"
            )
    return "\n".join(lines)


def _safe_node_id(concept_id: str) -> str:
    """Mermaid 节点 ID 不能含 `:` 和 `.`。"""
    return concept_id.replace(":", "__").replace(".", "_").replace("-", "_")


# --------------------------------------------------------------------------- #
# 切节正文 — 给 concept 模式喂 ConceptEnricher
# --------------------------------------------------------------------------- #


def _split_sections(
    markdown_path: Path, concepts: list[Concept]
) -> dict[str, str]:
    """把 markdown 切成 {concept_id: 该节正文} 字典。

    一个 concept 的正文 = 它对应 heading 行的下一行 → 下一个 concept heading 之前。
    Concept.sources[0].page 存的是 heading 所在的 1-indexed 行号。
    """
    text = markdown_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    by_line: list[tuple[int, str]] = []
    for c in concepts:
        if not c.sources:
            continue
        try:
            ln = int(c.sources[0].page or "0")
        except (TypeError, ValueError):
            continue
        by_line.append((ln, c.id))
    by_line.sort()

    out: dict[str, str] = {}
    for i, (start, cid) in enumerate(by_line):
        end = by_line[i + 1][0] if i + 1 < len(by_line) else len(lines) + 1
        body = "\n".join(lines[start : end - 1]).strip()
        out[cid] = body
    return out


# --------------------------------------------------------------------------- #
# 持久化 — 给所有 builder 共用
# --------------------------------------------------------------------------- #


def _persist_kg(
    *,
    db: RelationalStore,
    kg_id: str,
    subject_slug: str,
    corpus_id: str,
    version: str,
    concepts: list[Concept],
    edges: list[Relation],
    quality: QualityReport,
    manifest: dict,
) -> None:
    """把 concepts + edges 落 knowledge_graphs/concepts/relations 三张表。

    重建语义（FIX-K）：
    - kg_id 由 corpus+depth 确定（`{corpus}-kg-full-v1`），同一语料重建（修过滤器后
      重跑）→ 同 id KG 整体替换，不让主键冲突把重建变成死路。
    - concept.id（`{subject}:{chapter}:{slug}`）**不含 corpus 命名空间**，而 corpus_id
      含时间戳——同科目重新采集后重建必然撞旧根版本 KG 的概念主键（ACP 实测只能靠
      手工删库脚本绕过）。撞 id 的同科目旧根版本 KG 在此整体替换并告警；versioned
      派生 KG 的概念 id 带 `@short` 后缀，不受影响。
    """
    with db.session() as s:
        existing = s.get(KnowledgeGraphRow, kg_id)
        if existing is not None:
            s.query(ConceptRow).filter_by(kg_id=kg_id).delete()
            s.query(RelationRow).filter_by(kg_id=kg_id).delete()
            s.delete(existing)
            logger.warning("kg.rebuild.replace", kg_id=kg_id)

        new_ids = [c.id for c in concepts]
        blocking: set[str] = set()
        for i in range(0, len(new_ids), 500):  # SQLite IN 变量数上限保护
            rows = (
                s.query(ConceptRow.kg_id)
                .filter(ConceptRow.id.in_(new_ids[i : i + 500]), ConceptRow.kg_id != kg_id)
                .distinct()
                .all()
            )
            blocking.update(r[0] for r in rows)
        for old_kg_id in sorted(blocking):
            s.query(ConceptRow).filter_by(kg_id=old_kg_id).delete()
            s.query(RelationRow).filter_by(kg_id=old_kg_id).delete()
            old_row = s.get(KnowledgeGraphRow, old_kg_id)
            if old_row is not None:
                s.delete(old_row)
            logger.warning(
                "kg.rebuild.replace_subject_kg", old_kg_id=old_kg_id, new_kg_id=kg_id
            )
        s.flush()
        s.add(
            KnowledgeGraphRow(
                kg_id=kg_id,
                subject_id=subject_slug,
                corpus_id=corpus_id,
                version=version,
                node_count=len(concepts),
                edge_count=len(edges),
                quality_json=quality.model_dump(mode="json"),
                manifest_json=manifest,
            )
        )
        s.flush()
        for c in concepts:
            s.add(
                ConceptRow(
                    id=c.id,
                    kg_id=kg_id,
                    name_primary=c.names[0],
                    names_json=c.names,
                    category=c.category,
                    definition=c.definition,
                    informal_description=c.informal_description,
                    abstract_level=c.classification.abstract_level,
                    bloom_level=c.classification.bloom_level,
                    domain=c.classification.domain,
                    cognitive_load_estimate=c.difficulty.cognitive_load_estimate,
                    typical_learning_time_min=c.difficulty.typical_learning_time_min,
                    prereq_count=c.difficulty.prereq_count,
                    prereq_max_depth=c.difficulty.prereq_max_depth,
                    formula_density=c.difficulty.formula_density,
                    coupling=c.difficulty.coupling,
                    confidence=c.confidence,
                    full_json=c.model_dump(mode="json"),
                )
            )
        for e in edges:
            s.add(
                RelationRow(
                    kg_id=kg_id,
                    from_id=e.from_id,
                    to_id=e.to_id,
                    type=e.type,
                    weight=e.weight,
                    explanation=e.explanation,
                    confidence=e.confidence,
                    deprecated=False,
                )
            )
        s.commit()


def build_kg_toc(
    *,
    corpus_id: str,
    subject_slug: str,
    markdown_path: Path,
    db: RelationalStore,
) -> tuple[str, list[Concept], list[Relation], QualityReport, str]:
    """toc 模式：从 markdown 章节生成 KG。

    返回 (kg_id, concepts, edges, quality, mermaid)
    """
    if not markdown_path.exists():
        raise TutorError("CORPUS_NOT_FOUND", hint=str(markdown_path))

    concepts, edges = _build_toc(subject_slug=subject_slug, markdown_path=markdown_path)
    if not concepts:
        raise TutorError(
            "KG_QUALITY_GATE_FAILED",
            hint="markdown 中没有任何 # 标题，无法生成 toc",
        )

    quality = _compute_quality(concepts, edges)
    mermaid = _to_mermaid(concepts, edges)
    kg_id = f"{corpus_id}-kg-toc-v1"

    _persist_kg(
        db=db,
        kg_id=kg_id,
        subject_slug=subject_slug,
        corpus_id=corpus_id,
        version="toc-v1",
        concepts=concepts,
        edges=edges,
        quality=quality,
        manifest={"depth": "toc", "source": str(markdown_path)},
    )

    logger.info(
        "build_kg_toc.done",
        kg_id=kg_id,
        concepts=len(concepts),
        edges=len(edges),
        overall=quality.overall,
    )
    return kg_id, concepts, edges, quality, mermaid
