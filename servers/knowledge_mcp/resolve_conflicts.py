"""resolve_conflicts — 检测 KG 中的结构性 / 语义冲突。

合同来源: ai-tutor-system-design/specs/server-api-spec.md §1.4

6 种冲突:
- circular_prerequisite    prerequisite_strong 成环
- reversed_prerequisite    A→B 且 B→A 同时存在
- duplicate_concept        同 name_primary 不同 id
- broken_reference         edge 端点不在 concepts
- isolated_subgraph        与最大连通分量断开的小岛
- contradictory_definition LLM 判定（无 LLM → 跳过）

前 5 种纯算法（networkx）；第 6 种需要 LLM，无 provider 时静默跳过。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from shared.errors import TutorError
from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow

logger = get_logger("knowledge_mcp.resolve_conflicts")


@dataclass
class ConflictItem:
    type: str
    concept_a: str
    concept_b: str | None
    description: str
    suggested_resolution: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "concept_a": self.concept_a,
            "concept_b": self.concept_b,
            "description": self.description,
            "suggested_resolution": self.suggested_resolution,
            "detail": self.detail,
        }


def _detect_reversed(edges: list[RelationRow]) -> list[ConflictItem]:
    prereq = {
        (e.from_id, e.to_id)
        for e in edges
        if e.type == "prerequisite_strong" and not e.deprecated
    }
    out: list[ConflictItem] = []
    seen: set[frozenset] = set()
    for (a, b) in prereq:
        if (b, a) in prereq:
            key = frozenset((a, b))
            if key in seen:
                continue
            seen.add(key)
            out.append(ConflictItem(
                type="reversed_prerequisite",
                concept_a=a, concept_b=b,
                description=f"{a} 和 {b} 互为前置（A→B 且 B→A），逻辑矛盾。",
                suggested_resolution="保留更符合教材顺序的一条 prerequisite，删除反向边。",
            ))
    return out


def _detect_circular(edges: list[RelationRow]) -> list[ConflictItem]:
    g = nx.DiGraph()
    for e in edges:
        if e.type == "prerequisite_strong" and not e.deprecated:
            g.add_edge(e.from_id, e.to_id)
    out: list[ConflictItem] = []
    try:
        cycles = list(nx.simple_cycles(g))
    except Exception:  # noqa: BLE001
        cycles = []
    for cyc in cycles:
        if len(cyc) < 2:
            continue
        # 2 元环已由 reversed 覆盖，这里只报 ≥3 元环
        if len(cyc) == 2:
            continue
        out.append(ConflictItem(
            type="circular_prerequisite",
            concept_a=cyc[0],
            concept_b=cyc[-1],
            description=f"前置关系成环：{' → '.join(cyc)} → {cyc[0]}",
            suggested_resolution="打破环：删掉环中最弱（weight 最低）的一条 prerequisite。",
            detail={"cycle": cyc},
        ))
    return out


def _detect_duplicate(concepts: list[ConceptRow]) -> list[ConflictItem]:
    by_name: dict[str, list[str]] = defaultdict(list)
    for c in concepts:
        by_name[(c.name_primary or "").strip()].append(c.id)
    out: list[ConflictItem] = []
    for name, ids in by_name.items():
        if name and len(ids) > 1:
            ids_sorted = sorted(ids)
            # 两两报（通常只有一对）
            for i in range(len(ids_sorted) - 1):
                out.append(ConflictItem(
                    type="duplicate_concept",
                    concept_a=ids_sorted[i],
                    concept_b=ids_sorted[i + 1],
                    description=f"概念名 '{name}' 出现在多个节点：{ids_sorted}",
                    suggested_resolution="用 update_kg 的 merge_concepts 把它们合并为一个。",
                    detail={"name": name, "ids": ids_sorted},
                ))
    return out


def _detect_broken_reference(
    concepts: list[ConceptRow], edges: list[RelationRow]
) -> list[ConflictItem]:
    valid_ids = {c.id for c in concepts}
    out: list[ConflictItem] = []
    for e in edges:
        for endpoint in (e.from_id, e.to_id):
            if endpoint not in valid_ids:
                out.append(ConflictItem(
                    type="broken_reference",
                    concept_a=e.from_id,
                    concept_b=e.to_id,
                    description=f"边 ({e.from_id} →{e.type}→ {e.to_id}) 引用了不存在的概念 {endpoint}。",
                    suggested_resolution="删除这条悬空边，或补建缺失的概念节点。",
                    detail={"missing": endpoint, "edge_type": e.type},
                ))
                break  # 一条边只报一次
    return out


def _detect_isolated(
    concepts: list[ConceptRow], edges: list[RelationRow]
) -> list[ConflictItem]:
    if len(concepts) <= 1:
        return []
    g = nx.Graph()
    for c in concepts:
        g.add_node(c.id)
    valid = {c.id for c in concepts}
    for e in edges:
        if e.from_id in valid and e.to_id in valid:
            g.add_edge(e.from_id, e.to_id)

    components = list(nx.connected_components(g))
    if len(components) <= 1:
        return []
    # 最大分量视为主图，其余视为孤岛
    components.sort(key=len, reverse=True)
    main = components[0]
    out: list[ConflictItem] = []
    for comp in components[1:]:
        for cid in sorted(comp):
            out.append(ConflictItem(
                type="isolated_subgraph",
                concept_a=cid,
                concept_b=None,
                description=f"概念 {cid} 所在的子图（{len(comp)} 个节点）与主图（{len(main)} 个节点）不连通。",
                suggested_resolution="补一条 prerequisite / part_of 边把它接到主图，或确认它确实是独立主题。",
                detail={"component_size": len(comp)},
            ))
    return out


def find_conflicts(
    *,
    db,
    kg_id: str,
    llm: LLMProvider | None = None,
) -> list[ConflictItem]:
    """检测一个 KG 的所有冲突。前 5 种纯算法；contradictory_definition 需 LLM。"""
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)
        concepts = s.query(ConceptRow).filter_by(kg_id=kg_id).all()
        edges = s.query(RelationRow).filter_by(kg_id=kg_id).all()

    conflicts: list[ConflictItem] = []
    conflicts += _detect_reversed(edges)
    conflicts += _detect_circular(edges)
    conflicts += _detect_duplicate(concepts)
    conflicts += _detect_broken_reference(concepts, edges)
    conflicts += _detect_isolated(concepts, edges)
    # contradictory_definition: 需要 LLM，留待有 provider 时实现
    # （duplicate_concept 已能抓"同名"，语义对立判定后续切片接 LLM）

    logger.info(
        "resolve_conflicts.done",
        kg_id=kg_id,
        total=len(conflicts),
        by_type={t: sum(1 for c in conflicts if c.type == t) for t in {c.type for c in conflicts}},
    )
    return conflicts
