"""kg_query 契约测试：shortest_learning_path + extract_subgraph。

KG 拓扑（prerequisite_strong，A→B = A 是 B 前置）:
  a → b → c → d        （主链）
  a → e                （旁支）
  z                    （孤立节点）
part_of: e -part_of-> a
"""
from __future__ import annotations

import pytest

from shared.errors import TutorError
from shared.models import ConceptRow, Corpus, KnowledgeGraphRow, RelationRow
from shared.storage import RelationalStore


def _concept(kg, cid, name=None):
    return ConceptRow(
        id=cid, kg_id=kg, base_id=cid,
        name_primary=name or cid, names_json=[name or cid],
        category="definition", definition=f"{cid} 定义",
        informal_description="", abstract_level=0.5, bloom_level="understand",
        domain="x", cognitive_load_estimate=0.3, typical_learning_time_min=10,
        prereq_count=0, prereq_max_depth=0, formula_density=0,
        coupling=0, confidence=0.9, full_json={},
    )


def _edge(kg, frm, to, typ="prerequisite_strong"):
    return RelationRow(kg_id=kg, from_id=frm, to_id=to, type=typ,
                       weight=0.6, explanation="", confidence=0.5, deprecated=False)


@pytest.fixture
def kg(tmp_db: RelationalStore):
    k = "kg-q"
    with tmp_db.session() as s:
        s.add(Corpus(id="c", subject_id="x", user_id="u", manifest_json={}))
        s.add(KnowledgeGraphRow(kg_id=k, subject_id="x", corpus_id="c",
                                version="v1", node_count=6, edge_count=5, manifest_json={}))
        for cid in ["x:1:a", "x:1:b", "x:1:c", "x:1:d", "x:1:e", "x:9:z"]:
            s.add(_concept(k, cid))
        s.add(_edge(k, "x:1:a", "x:1:b"))
        s.add(_edge(k, "x:1:b", "x:1:c"))
        s.add(_edge(k, "x:1:c", "x:1:d"))
        s.add(_edge(k, "x:1:a", "x:1:e"))
        s.add(_edge(k, "x:1:e", "x:1:a", typ="part_of"))
        s.commit()
    return tmp_db, k


# ---------------- path ---------------- #


def test_path_finds_chain(kg):
    from servers.knowledge_mcp.kg_query import shortest_learning_path

    db, k = kg
    r = shortest_learning_path(db=db, kg_id=k, from_id="x:1:a", to_id="x:1:d")
    assert r["found"] is True
    assert r["path"] == ["x:1:a", "x:1:b", "x:1:c", "x:1:d"]
    assert r["length"] == 3
    assert r["steps"][0]["name"]  # 带名字


def test_path_same_node(kg):
    from servers.knowledge_mcp.kg_query import shortest_learning_path

    db, k = kg
    r = shortest_learning_path(db=db, kg_id=k, from_id="x:1:b", to_id="x:1:b")
    assert r["found"] is True
    assert r["path"] == ["x:1:b"]
    assert r["length"] == 0


def test_path_no_route_returns_found_false(kg):
    """d 不是 a 的前置 → a 无法从 d 出发到达。"""
    from servers.knowledge_mcp.kg_query import shortest_learning_path

    db, k = kg
    r = shortest_learning_path(db=db, kg_id=k, from_id="x:1:d", to_id="x:1:a")
    assert r["found"] is False
    assert "前置" in r["reason"] or "路径" in r["reason"]


def test_path_missing_endpoint_found_false(kg):
    from servers.knowledge_mcp.kg_query import shortest_learning_path

    db, k = kg
    r = shortest_learning_path(db=db, kg_id=k, from_id="x:1:a", to_id="x:1:ghost")
    assert r["found"] is False
    assert "x:1:ghost" in r["reason"]


def test_path_ignores_part_of_edges(kg):
    """part_of 不算 prerequisite；e→a 是 part_of，不应让 e 成为 a 的学习前置路径。"""
    from servers.knowledge_mcp.kg_query import shortest_learning_path

    db, k = kg
    r = shortest_learning_path(db=db, kg_id=k, from_id="x:1:e", to_id="x:1:a")
    assert r["found"] is False


def test_path_unknown_kg_raises(tmp_db: RelationalStore):
    from servers.knowledge_mcp.kg_query import shortest_learning_path

    with pytest.raises(TutorError) as exc:
        shortest_learning_path(db=tmp_db, kg_id="no-such", from_id="a", to_id="b")
    assert exc.value.code == "KG_NOT_FOUND"


# ---------------- subgraph ---------------- #


def test_subgraph_depth1(kg):
    from servers.knowledge_mcp.kg_query import extract_subgraph

    db, k = kg
    r = extract_subgraph(db=db, kg_id=k, center_id="x:1:b", depth=1)
    assert r["found"] is True
    ids = {c["concept_id"] for c in r["concepts"]}
    # b 的 1 跳邻居：a (a→b) 和 c (b→c)
    assert ids == {"x:1:a", "x:1:b", "x:1:c"}


def test_subgraph_depth2(kg):
    from servers.knowledge_mcp.kg_query import extract_subgraph

    db, k = kg
    r = extract_subgraph(db=db, kg_id=k, center_id="x:1:b", depth=2)
    ids = {c["concept_id"] for c in r["concepts"]}
    # 2 跳：a,c + (a 的邻居 e) + (c 的邻居 d)
    assert "x:1:d" in ids
    assert "x:1:e" in ids
    assert "x:9:z" not in ids  # 孤立节点永不出现


def test_subgraph_depth0_just_center(kg):
    from servers.knowledge_mcp.kg_query import extract_subgraph

    db, k = kg
    r = extract_subgraph(db=db, kg_id=k, center_id="x:1:b", depth=0)
    assert {c["concept_id"] for c in r["concepts"]} == {"x:1:b"}
    assert r["edges"] == []


def test_subgraph_edges_within_only(kg):
    from servers.knowledge_mcp.kg_query import extract_subgraph

    db, k = kg
    r = extract_subgraph(db=db, kg_id=k, center_id="x:1:b", depth=1)
    # 边端点都必须在子图节点集合内
    ids = {c["concept_id"] for c in r["concepts"]}
    for e in r["edges"]:
        assert e["from"] in ids and e["to"] in ids


def test_subgraph_missing_center_found_false(kg):
    from servers.knowledge_mcp.kg_query import extract_subgraph

    db, k = kg
    r = extract_subgraph(db=db, kg_id=k, center_id="x:1:ghost", depth=1)
    assert r["found"] is False


def test_subgraph_unknown_kg_raises(tmp_db: RelationalStore):
    from servers.knowledge_mcp.kg_query import extract_subgraph

    with pytest.raises(TutorError) as exc:
        extract_subgraph(db=tmp_db, kg_id="no-such", center_id="a", depth=1)
    assert exc.value.code == "KG_NOT_FOUND"
