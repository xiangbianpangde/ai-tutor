"""kg_query — query_knowledge 的 path / subgraph 两种图查询。

- shortest_learning_path: 沿 prerequisite_strong 求 from→to 的最短学习路径
  （边 A→B 表示 "A 是 B 的前置"，学习顺序 A 然后 B）
- extract_subgraph: 以某 concept 为中心，无向 BFS 取 N 跳邻域子图

KG 不存在 → KG_NOT_FOUND。端点 concept 不在 KG → 返回 found=False（不 raise，
便于 LLM 调用方分支处理）。
"""
from __future__ import annotations

from typing import Any

import networkx as nx

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow

logger = get_logger("knowledge_mcp.kg_query")


def _load_graph(db, kg_id: str):
    """返回 (id→name dict, prerequisite DiGraph, 全类型无向 Graph, edges 列表)。"""
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)
        concepts = s.query(ConceptRow).filter_by(kg_id=kg_id).all()
        edges = s.query(RelationRow).filter_by(kg_id=kg_id).all()
        names = {c.id: (c.name_primary or c.id) for c in concepts}
        edge_tuples = [
            (e.from_id, e.to_id, e.type, bool(e.deprecated)) for e in edges
        ]

    prereq = nx.DiGraph()
    undirected = nx.Graph()
    for cid in names:
        prereq.add_node(cid)
        undirected.add_node(cid)
    for frm, to, typ, dep in edge_tuples:
        if dep:
            continue
        if typ == "prerequisite_strong":
            prereq.add_edge(frm, to)
        undirected.add_edge(frm, to, type=typ)
    return names, prereq, undirected, edge_tuples


def shortest_learning_path(
    *, db, kg_id: str, from_id: str, to_id: str,
) -> dict[str, Any]:
    """沿 prerequisite_strong 求 from_id → to_id 的最短学习路径。"""
    names, prereq, _undirected, _edges = _load_graph(db, kg_id)

    if from_id not in names or to_id not in names:
        missing = [c for c in (from_id, to_id) if c not in names]
        return {
            "from": from_id, "to": to_id, "found": False,
            "reason": f"概念不在 KG: {missing}",
            "path": [], "steps": [], "length": 0,
        }
    if from_id == to_id:
        return {
            "from": from_id, "to": to_id, "found": True,
            "path": [from_id],
            "steps": [{"concept_id": from_id, "name": names[from_id]}],
            "length": 0,
        }

    try:
        node_path = nx.shortest_path(prereq, source=from_id, target=to_id)
    except nx.NetworkXNoPath:
        return {
            "from": from_id, "to": to_id, "found": False,
            "reason": f"{from_id} 不是 {to_id} 的（间接）前置，无 prerequisite 路径",
            "path": [], "steps": [], "length": 0,
        }
    except nx.NodeNotFound:
        return {
            "from": from_id, "to": to_id, "found": False,
            "reason": "节点不在前置图中", "path": [], "steps": [], "length": 0,
        }

    logger.info("kg_query.path", kg_id=kg_id, from_id=from_id, to_id=to_id, length=len(node_path) - 1)
    return {
        "from": from_id, "to": to_id, "found": True,
        "path": node_path,
        "steps": [{"concept_id": c, "name": names[c]} for c in node_path],
        "length": len(node_path) - 1,
    }


def extract_subgraph(
    *, db, kg_id: str, center_id: str, depth: int = 1,
) -> dict[str, Any]:
    """以 center_id 为中心，无向 BFS 取 depth 跳邻域子图。"""
    if depth < 0:
        depth = 0
    names, _prereq, undirected, edge_tuples = _load_graph(db, kg_id)

    if center_id not in names:
        return {
            "center": center_id, "depth": depth, "found": False,
            "reason": f"中心概念不在 KG: {center_id}",
            "concepts": [], "edges": [], "node_count": 0,
        }

    # BFS 限定半径
    within = {center_id}
    if depth > 0:
        lengths = nx.single_source_shortest_path_length(
            undirected, center_id, cutoff=depth
        )
        within = set(lengths.keys())

    concepts = [{"concept_id": c, "name": names[c]} for c in sorted(within)]
    sub_edges = [
        {"from": frm, "to": to, "type": typ}
        for frm, to, typ, dep in edge_tuples
        if not dep and frm in within and to in within
    ]

    logger.info("kg_query.subgraph", kg_id=kg_id, center=center_id, depth=depth,
                nodes=len(within), edges=len(sub_edges))
    return {
        "center": center_id, "depth": depth, "found": True,
        "concepts": concepts, "edges": sub_edges, "node_count": len(within),
    }
