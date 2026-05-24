"""notes generator — 从 KG 输出结构化 markdown 学习笔记。

按 concept.id 中的章节号自然排序，深度 N → N 个 `#`。每个 concept 一段:
  - heading
  - 定义（definition）
  - 通俗解释（informal_description）
  - 例子（examples）
  - 常见误解（common_misconceptions）

后续切片可加: reportlab PDF（手写体）、章节摘要、双语对照。
"""
from __future__ import annotations

from pathlib import Path

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import ConceptRow, KnowledgeGraphRow
from shared.schemas import ArtifactURI
from shared.storage import RelationalStore

logger = get_logger("digest_mcp.notes")


def _chapter_key(concept_id: str) -> tuple[int, ...]:
    try:
        chapter = concept_id.split(":")[1]
        return tuple(int(x) for x in chapter.split("."))
    except (IndexError, ValueError):
        return (10**9,)


def _chapter_depth(concept_id: str) -> int:
    try:
        return concept_id.split(":")[1].count(".") + 1
    except IndexError:
        return 1


Grade = str  # "high_school" | "college" | ...


def _render_concept(row: ConceptRow, grade: Grade = "college") -> str:
    depth = _chapter_depth(row.id)
    heading = "#" * min(max(depth, 1), 6)  # 1-6 级
    lines: list[str] = [f"{heading} {row.name_primary}", ""]

    full = row.full_json or {}
    examples = full.get("examples") or []
    misc = full.get("common_misconceptions") or []

    if grade == "high_school":
        # 高中版：直觉优先、更浅显，不堆术语
        intuition = row.informal_description or row.definition
        if intuition:
            lines.append(f"**一句话理解**：{intuition}")
            lines.append("")
        # 仅当存在更正式的定义且与直觉不同，才补一句「更准确地说」
        if row.informal_description and row.definition:
            lines.append(f"**更准确地说**：{row.definition}")
            lines.append("")
        if examples:
            lines.append("**举个例子**：")
            for ex in examples:
                lines.append(f"- {ex.get('text', '')}")
            lines.append("")
    else:
        # 大学版（默认）：形式化定义优先 + 专业元信息（抽象度/领域）
        if row.definition:
            lines.append(f"**定义**：{row.definition}")
            lines.append("")
        if row.informal_description:
            lines.append(f"**通俗解释**：{row.informal_description}")
            lines.append("")
        lines.append(
            f"**形式化程度**：抽象度 {row.abstract_level:.2f} · 领域 {row.domain}"
        )
        lines.append("")
        if examples:
            lines.append("**例子**：")
            for ex in examples:
                text = ex.get("text", "")
                etype = ex.get("type", "")
                lines.append(f"- 例（{etype}）：{text}")
            lines.append("")
        if misc:
            lines.append("**常见误解**：")
            for m in misc:
                lines.append(f"- 误：{m}")
            lines.append("")

    lines.append(f"<!-- concept_id: {row.id}, confidence: {row.confidence:.2f} -->")
    lines.append("")
    return "\n".join(lines)


def generate_notes(
    *,
    db: RelationalStore,
    kg_id: str,
    out_dir: Path,
    grade: Grade = "college",
) -> ArtifactURI:
    """生成 markdown 笔记文件，返回 ArtifactURI。

    grade 适配（确定性、无需 LLM）:
    - "high_school": 直觉优先（「一句话理解」），语言更浅显，省略形式化术语行
    - "college"（默认）: 形式化定义优先 + 抽象度/领域等专业元信息 + 常见误解
    """
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)
        rows = s.query(ConceptRow).filter_by(kg_id=kg_id).all()

    rows.sort(key=lambda r: _chapter_key(r.id))
    out_dir = Path(out_dir).resolve()  # 绝对路径保证 ArtifactURI 可被 sync-mcp 解析
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"notes-{kg_id}.md"

    grade_label = "高中版（直觉优先）" if grade == "high_school" else "大学版（形式化）"
    parts: list[str] = [
        f"# 学习笔记 — {kg.subject_id}",
        "",
        f"> 来自 KG `{kg_id}` · 共 {len(rows)} 概念 · 适配年级 {grade}（{grade_label}）· "
        f"avg confidence {(sum(r.confidence for r in rows) / max(len(rows),1)):.2f}",
        "",
        "---",
        "",
    ]
    if not rows:
        parts.append("（无概念可输出）")
    else:
        for r in rows:
            parts.append(_render_concept(r, grade))

    text = "\n".join(parts)
    file_path.write_text(text, encoding="utf-8")

    logger.info("notes.done", kg_id=kg_id, concepts=len(rows), grade=grade, file=str(file_path))
    return ArtifactURI(
        uri=f"file:///{file_path.as_posix()}",
        mime_type="text/markdown",
        size_bytes=file_path.stat().st_size,
    )
