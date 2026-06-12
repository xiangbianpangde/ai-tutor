"""build_knowledge_graph 的适配层。

depth=toc:     纯规则。从 markdown 的 #/## 抽 Concept 骨架 + prerequisite_strong 边。
depth=concept: TODO 下一切片：接 research_tool.ExtractResult.triples + LLM 二次增强
depth=full:    TODO 同上 + 难度评分 + embedding
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterator

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
_NOISE_SEPARATOR_RE = re.compile(r"^[=\-_*~·•#>\s]+$")
_NOISE_SOURCE_FILE_RE = re.compile(r"^\d{1,3}-[\w.-]+-[0-9a-f]{4,12}$", re.IGNORECASE)
_NOISE_URL_RE = re.compile(r"https?://|www\.")
_MAX_TITLE_CHARS = 64
_SENTENCE_ENDINGS = ("。", "．", "；", ";")


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
    """把 concepts + edges 落 knowledge_graphs/concepts/relations 三张表。"""
    with db.session() as s:
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
