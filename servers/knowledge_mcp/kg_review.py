"""KG 人工确认（adopted-fixes 修正 1）。

review_kg(db, kg_id, mode, limit) → ReviewKGResult

quick 模式: 取 confidence ASC 前 N 个 + Quality Gate warnings + 缩略 Mermaid 图
full 模式:  取 confidence < 0.5 全部 + 完整 Mermaid 图

后续切片(K2)的 update_kg 接受 KgEditAction 列表，对低置信概念做编辑/合并/批准。
"""
from __future__ import annotations

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import KnowledgeGraphRow, RelationRow, ConceptRow
from shared.schemas import (
    KgEditAction,
    LowConfidenceConcept,
    ReviewKGResult,
)
from shared.storage import RelationalStore

from .kg_enrich_adapter import _safe_node_id

logger = get_logger("knowledge_mcp.kg_review")


_LOW_CONF_THRESHOLD = 0.5


def _build_mermaid_subset(rows: list[ConceptRow], edges: list[RelationRow]) -> str:
    """只画给定的 concept 子集 + 它们之间的边。"""
    selected_ids = {r.id for r in rows}
    lines = ["graph TD"]
    for r in rows:
        safe_label = r.name_primary.replace('"', "'")
        lines.append(f'  {_safe_node_id(r.id)}["{safe_label}"]')
    for e in edges:
        if e.from_id in selected_ids and e.to_id in selected_ids:
            lines.append(
                f"  {_safe_node_id(e.from_id)} -->|{e.type}| {_safe_node_id(e.to_id)}"
            )
    return "\n".join(lines)


def _build_full_mermaid(
    all_concepts: list[ConceptRow], all_edges: list[RelationRow], max_nodes: int = 80
) -> str:
    """完整图（节点过多时截断）。"""
    lines = ["graph TD"]
    selected = all_concepts[:max_nodes]
    selected_ids = {c.id for c in selected}
    for c in selected:
        safe_label = c.name_primary.replace('"', "'")
        lines.append(f'  {_safe_node_id(c.id)}["{safe_label}"]')
    for e in all_edges:
        if e.from_id in selected_ids and e.to_id in selected_ids:
            lines.append(
                f"  {_safe_node_id(e.from_id)} -->|{e.type}| {_safe_node_id(e.to_id)}"
            )
    return "\n".join(lines)


def review_kg(
    *,
    db: RelationalStore,
    kg_id: str,
    mode: str = "quick",
    limit: int = 20,
) -> ReviewKGResult:
    """对一个 KG 做人工确认前的低置信度概念盘点。"""
    if mode not in ("quick", "full"):
        raise TutorError(
            "DEPENDENCY_MISSING",
            hint=f"mode 必须是 quick 或 full，收到 {mode!r}",
        )

    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)

        # 低置信概念查询
        q = s.query(ConceptRow).filter_by(kg_id=kg_id)
        if mode == "quick":
            low_conf = q.order_by(ConceptRow.confidence.asc()).limit(limit).all()
        else:
            low_conf = (
                q.filter(ConceptRow.confidence < _LOW_CONF_THRESHOLD)
                .order_by(ConceptRow.confidence.asc())
                .all()
            )

        all_edges = s.query(RelationRow).filter_by(kg_id=kg_id).all()

        # mermaid
        if mode == "quick":
            thumb = _build_mermaid_subset(low_conf, all_edges)
            full_mermaid = None
        else:
            all_concepts = (
                s.query(ConceptRow)
                .filter_by(kg_id=kg_id)
                .order_by(ConceptRow.id)
                .all()
            )
            thumb = None
            full_mermaid = _build_full_mermaid(all_concepts, all_edges)

        # quality warnings 透传
        warnings: list[str] = []
        if kg.quality_json:
            qj = kg.quality_json
            if isinstance(qj, dict):
                warnings = list(qj.get("warnings") or [])

    # 建议动作：低置信度 → 推 edit_definition + approve_all 两个 op 候选
    suggested_actions: list[KgEditAction] = []
    if low_conf:
        suggested_actions.append(
            KgEditAction(
                op="edit_definition",
                concept_id=low_conf[0].id,
                note=f"该 concept 置信度 {low_conf[0].confidence:.2f} 偏低，建议人工补全定义",
            )
        )
        suggested_actions.append(
            KgEditAction(op="approve_all", note="批准全部并继续 start_learning_session")
        )

    suggestions = [
        f"共发现 {len(low_conf)} 个低置信概念，建议逐个审阅或调用 update_kg",
    ]

    logger.info(
        "review_kg.done",
        kg_id=kg_id,
        mode=mode,
        low_conf_count=len(low_conf),
    )

    return ReviewKGResult(
        kg_id=kg_id,
        mode=mode,  # type: ignore[arg-type]
        low_confidence_concepts=[
            LowConfidenceConcept(
                concept_id=c.id,
                name=c.name_primary,
                confidence=c.confidence,
                definition_preview=(c.definition or "")[:160],
            )
            for c in low_conf
        ],
        warnings=warnings,
        suggestions=suggestions,
        mermaid_thumb=thumb,
        full_mermaid=full_mermaid,
        suggested_actions=suggested_actions,
    )
