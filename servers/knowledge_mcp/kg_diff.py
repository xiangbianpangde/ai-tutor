"""diff_kg — 按 base_id 对齐两 KG，输出 added/removed/definition_changed 等差异。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow
from shared.storage import RelationalStore

logger = get_logger("knowledge_mcp.kg_diff")


_CONF_DELTA_THRESHOLD = 0.10


@dataclass
class KgDiffResult:
    kg_id_a: str
    kg_id_b: str
    added: list[dict[str, Any]] = field(default_factory=list)         # b 有 a 没有
    removed: list[dict[str, Any]] = field(default_factory=list)       # a 有 b 没有
    definition_changed: list[dict[str, Any]] = field(default_factory=list)
    confidence_changed: list[dict[str, Any]] = field(default_factory=list)
    edges_added: list[dict[str, Any]] = field(default_factory=list)
    edges_removed: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def diff_kg(*, db: RelationalStore, kg_id_a: str, kg_id_b: str) -> KgDiffResult:
    with db.session() as s:
        kg_a = s.get(KnowledgeGraphRow, kg_id_a)
        kg_b = s.get(KnowledgeGraphRow, kg_id_b)
        if kg_a is None or kg_b is None:
            missing = kg_id_a if kg_a is None else kg_id_b
            raise TutorError("KG_NOT_FOUND", hint=missing)

        rows_a = s.query(ConceptRow).filter_by(kg_id=kg_id_a).all()
        rows_b = s.query(ConceptRow).filter_by(kg_id=kg_id_b).all()
        edges_a = s.query(RelationRow).filter_by(kg_id=kg_id_a).all()
        edges_b = s.query(RelationRow).filter_by(kg_id=kg_id_b).all()

    a_by_base = {r.base_id: r for r in rows_a}
    b_by_base = {r.base_id: r for r in rows_b}

    result = KgDiffResult(kg_id_a=kg_id_a, kg_id_b=kg_id_b)

    # added / removed
    only_in_b = set(b_by_base) - set(a_by_base)
    only_in_a = set(a_by_base) - set(b_by_base)
    for base in sorted(only_in_b):
        r = b_by_base[base]
        result.added.append({"base_id": base, "name": r.name_primary, "id_in_b": r.id})
    for base in sorted(only_in_a):
        r = a_by_base[base]
        result.removed.append({"base_id": base, "name": r.name_primary, "id_in_a": r.id})

    # common — 看变化
    for base in sorted(set(a_by_base) & set(b_by_base)):
        a, b = a_by_base[base], b_by_base[base]
        if (a.definition or "") != (b.definition or ""):
            result.definition_changed.append({
                "base_id": base,
                "name": a.name_primary,
                "from": (a.definition or "")[:160],
                "to": (b.definition or "")[:160],
            })
        if abs((a.confidence or 0.0) - (b.confidence or 0.0)) >= _CONF_DELTA_THRESHOLD:
            result.confidence_changed.append({
                "base_id": base,
                "name": a.name_primary,
                "from": round(a.confidence or 0.0, 3),
                "to": round(b.confidence or 0.0, 3),
            })

    # edges: 把每条边映射成 (from_base, to_base, type) tuple 对齐
    def _edge_key(e: RelationRow, lookup: dict[str, ConceptRow]) -> tuple[str, str, str] | None:
        # lookup: id → row（id 是各自 KG 的版本化 id）
        from_row = lookup.get(e.from_id)
        to_row = lookup.get(e.to_id)
        if from_row is None or to_row is None:
            return None
        return (from_row.base_id, to_row.base_id, e.type)

    a_id_to_row = {r.id: r for r in rows_a}
    b_id_to_row = {r.id: r for r in rows_b}
    set_a_keys = {_edge_key(e, a_id_to_row) for e in edges_a}
    set_a_keys.discard(None)
    set_b_keys = {_edge_key(e, b_id_to_row) for e in edges_b}
    set_b_keys.discard(None)
    for k in sorted(set_b_keys - set_a_keys):
        result.edges_added.append({"from": k[0], "to": k[1], "type": k[2]})
    for k in sorted(set_a_keys - set_b_keys):
        result.edges_removed.append({"from": k[0], "to": k[1], "type": k[2]})

    result.summary = {
        "added_count": len(result.added),
        "removed_count": len(result.removed),
        "definition_changed_count": len(result.definition_changed),
        "confidence_changed_count": len(result.confidence_changed),
        "edges_added_count": len(result.edges_added),
        "edges_removed_count": len(result.edges_removed),
    }
    logger.info("diff_kg.done", kg_id_a=kg_id_a, kg_id_b=kg_id_b, **result.summary)
    return result
