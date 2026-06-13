"""mindmap 生成器 — 从 KG 输出 Mermaid `.mmd` 文件。

后续切片可加：
- 调用 mermaid-cli 渲染 PNG / SVG
- 多种布局（mindmap / flowchart / classDiagram）
- 按 cognitive_load 染色
"""
from __future__ import annotations

from pathlib import Path

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow
from shared.schemas import ArtifactURI
from shared.storage import RelationalStore

logger = get_logger("digest_mcp.mindmap")


def _safe_node_id(concept_id: str) -> str:
    """Mermaid ID 不允许 `:` `.` `-`。"""
    return concept_id.replace(":", "__").replace(".", "_").replace("-", "_")


def _chapter_depth(concept_id: str) -> int:
    """从 concept.id 中段（"1.4.2"）数 `.` 个数 +1。"""
    try:
        chapter = concept_id.split(":")[1]
        return chapter.count(".") + 1
    except IndexError:
        return 0


def generate_mindmap(
    *,
    db: RelationalStore,
    kg_id: str,
    out_dir: Path,
    max_depth: int | None = None,
    only_low_confidence: bool = False,
    confidence_threshold: float = 0.5,
) -> ArtifactURI:
    """从 KG 生成 Mermaid 文件，返回 ArtifactURI。

    Args:
        max_depth: 最大章节深度（按 concept.id 中 `.` 计数）；None=全部
        only_low_confidence: True → 只画 confidence < threshold 的节点（聚焦审阅）
        confidence_threshold: 默认 0.5
    """
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)
        nodes_q = s.query(ConceptRow).filter_by(kg_id=kg_id)
        nodes = nodes_q.all()
        if only_low_confidence:
            nodes = [n for n in nodes if n.confidence < confidence_threshold]
        if max_depth is not None:
            nodes = [n for n in nodes if _chapter_depth(n.id) <= max_depth]
        node_ids = {n.id for n in nodes}
        edges = s.query(RelationRow).filter_by(kg_id=kg_id).all()
        edges = [e for e in edges if e.from_id in node_ids and e.to_id in node_ids]

    out_dir = Path(out_dir).resolve()  # 保证生成的 ArtifactURI 是绝对路径
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"mindmap-{kg_id}.mmd"

    lines = ["graph TD"]
    for n in nodes:
        label = (n.name_primary or "").replace('"', "'")
        lines.append(f'  {_safe_node_id(n.id)}["{label}"]')
    for e in edges:
        lines.append(
            f"  {_safe_node_id(e.from_id)} -->|{e.type}| {_safe_node_id(e.to_id)}"
        )
    if not nodes:
        # 防止空文件，至少写一个占位
        lines.append('  empty["（无匹配概念）"]')
    text = "\n".join(lines) + "\n"
    file_path.write_text(text, encoding="utf-8")

    logger.info(
        "mindmap.done",
        kg_id=kg_id,
        nodes=len(nodes),
        edges=len(edges),
        file=str(file_path),
    )
    return ArtifactURI(
        uri=f"file:///{file_path.as_posix()}",
        mime_type="text/vnd.mermaid",
        size_bytes=file_path.stat().st_size,
    )
