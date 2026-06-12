"""study_pack generator — 把语料 markdown 拆成可读的小份学习材料（#2）。

问题来源：系统此前唯一完整可读物是原始拼接语料（ACP 实测 75,393 行直接交给
学习者"阅读"），人工补救是手工拆成 121 份小文件。本产物把补救产品化：

- 从 KG manifest 的 source 取语料 markdown
- fence 感知按 H1 切章；超过 ~25 分钟阅读量（400 字/分钟）的章再按 H2 细分，
  相邻小块回填合并，目标每份 15-30 分钟读完
- 写 `NN_<标题>.md` + `00_索引.md`（顺序 / 标题 / 预计阅读分钟）
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import KnowledgeGraphRow
from shared.schemas import ArtifactURI
from shared.storage import RelationalStore

logger = get_logger("digest_mcp.study_pack")

# 与 knowledge_mcp.kg_enrich_adapter 同款 fence 感知解析；digest 不依赖
# knowledge server（避免 server 间横向 import），故本地保留这份极小实现。
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")
_FENCE_RE = re.compile(r"^\s{0,3}(?P<marker>```|~~~)")

CHARS_PER_MIN = 400        # 中文技术文阅读速度估计
MAX_MIN_PER_PART = 25      # 单份材料目标上限（15-30 分钟一份）

_ILLEGAL_FN = re.compile(r'[\\/:*?"<>|\s]+')


def _iter_lines(text: str) -> Iterator[tuple[str, int | None, str | None]]:
    """逐行 yield (line, heading_level | None, title | None)；围栏代码内不识别标题。"""
    fence: str | None = None
    for line in text.splitlines():
        m = _FENCE_RE.match(line)
        if m:
            marker = m.group("marker")
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            yield line, None, None
            continue
        if fence is not None:
            yield line, None, None
            continue
        h = _HEADING_RE.match(line)
        if h:
            yield line, len(h.group("hashes")), h.group("title").strip()
        else:
            yield line, None, None


def _chars(lines: list[str]) -> int:
    return sum(len(l) for l in lines)


def _split_chapter(
    title: str, lines: list[str], max_chars: int, level: int = 2
) -> list[tuple[str, list[str]]]:
    """超长章按下一级标题递归切块，相邻小块回填合并到 max_chars 以内。

    FIX-K 补充：web 语料结构是 `H1=科目 → H2=主题 → H3=来源文章`，只切到 H2
    会得到几个 ⚠️超长大块（FastAPI 复跑实测 1.4MB → 3 块）——单块仍超长时
    继续往 H3…H6 下钻，直到尺寸达标或没有更深标题。
    """
    head: list[str] = []
    chunks: list[tuple[str, list[str]]] = []
    cur: tuple[str, list[str]] | None = None
    for line, lv, t in _iter_lines("\n".join(lines)):
        if lv == level:
            if cur is not None:
                chunks.append(cur)
            cur = (f"{title}·{t}", [line])
        elif cur is None:
            head.append(line)
        else:
            cur[1].append(line)
    if cur is not None:
        chunks.append(cur)

    if not chunks:  # 本级没有标题可切：往更深一级试；到底仍超长就整章一份（索引会标出）
        if level < 6:
            return _split_chapter(title, lines, max_chars, level + 1)
        return [(title, lines)]
    # 章头（本级标题行 + 第一个子标题之前的内容）并入第一块
    chunks[0] = (chunks[0][0], head + chunks[0][1])

    # 单块仍超长 → 递归下一级
    expanded: list[tuple[str, list[str]]] = []
    for t, ls in chunks:
        if _chars(ls) > max_chars and level < 6:
            expanded.extend(_split_chapter(t, ls, max_chars, level + 1))
        else:
            expanded.append((t, ls))

    merged: list[tuple[str, list[str]]] = []
    for t, ls in expanded:
        if merged and _chars(merged[-1][1]) + _chars(ls) <= max_chars:
            merged[-1] = (merged[-1][0], merged[-1][1] + ls)
        else:
            merged.append((t, ls))
    return merged


def _split_parts(text: str) -> list[tuple[str, list[str]]]:
    """[(标题, 行列表)]：H1 起新章，超长章二次细分。"""
    chapters: list[tuple[str, list[str]]] = []
    cur_title, cur_lines = "前言", []
    for line, level, title in _iter_lines(text):
        if level == 1:
            if any(l.strip() for l in cur_lines):
                chapters.append((cur_title, cur_lines))
            cur_title, cur_lines = title or "未命名章节", [line]
        else:
            cur_lines.append(line)
    if any(l.strip() for l in cur_lines):
        chapters.append((cur_title, cur_lines))

    max_chars = MAX_MIN_PER_PART * CHARS_PER_MIN
    parts: list[tuple[str, list[str]]] = []
    for title, lines in chapters:
        if _chars(lines) <= max_chars:
            parts.append((title, lines))
        else:
            parts.extend(_split_chapter(title, lines, max_chars))
    return parts


def _safe_name(title: str) -> str:
    return _ILLEGAL_FN.sub("-", title).strip("-·")[:24] or "片段"


def _artifact(file_path: Path) -> ArtifactURI:
    return ArtifactURI(
        uri=f"file:///{file_path.as_posix()}",
        mime_type="text/markdown",
        size_bytes=file_path.stat().st_size,
    )


def generate_study_pack(
    *, db: RelationalStore, kg_id: str, out_dir: Path
) -> list[ArtifactURI]:
    """生成学习材料分片包，返回 [索引, 各分片] 的 ArtifactURI 列表。"""
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)
        source = (kg.manifest_json or {}).get("source")
    if not source or not Path(source).exists():
        raise TutorError(
            "CORPUS_NOT_FOUND",
            hint=f"KG manifest 无可用语料 source: {source!r}（重新 acquire 后再 build）",
        )

    text = Path(source).read_text(encoding="utf-8")
    parts = _split_parts(text)
    if not parts:
        raise TutorError("CORPUS_NOT_FOUND", hint=f"语料为空: {source}")

    pack_dir = Path(out_dir) / f"study_pack-{kg_id}"
    pack_dir.mkdir(parents=True, exist_ok=True)

    artifacts: list[ArtifactURI] = []
    index_rows: list[str] = []
    total_min = 0
    for i, (title, lines) in enumerate(parts, start=1):
        minutes = max(1, round(_chars(lines) / CHARS_PER_MIN))
        total_min += minutes
        fpath = pack_dir / f"{i:02d}_{_safe_name(title)}.md"
        fpath.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        flag = " ⚠️超长" if minutes > MAX_MIN_PER_PART * 1.5 else ""
        index_rows.append(f"| {i} | [{title}]({fpath.name}) | {minutes} min{flag} |")
        artifacts.append(_artifact(fpath))

    index_text = (
        "# 学习材料索引\n\n"
        f"> 共 {len(parts)} 份 · 预计总阅读 {total_min} 分钟 · 按顺序阅读，每次 1-2 份\n\n"
        "| 顺序 | 材料 | 预计阅读 |\n"
        "|------|------|----------|\n" + "\n".join(index_rows) + "\n"
    )
    index_path = pack_dir / "00_索引.md"
    index_path.write_text(index_text, encoding="utf-8")
    artifacts.insert(0, _artifact(index_path))

    logger.info(
        "study_pack.done", kg_id=kg_id, parts=len(parts), total_min=total_min,
        out=str(pack_dir),
    )
    return artifacts
