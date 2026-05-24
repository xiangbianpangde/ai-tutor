"""resolve_conflicts 契约测试。

6 种冲突检测:
- circular_prerequisite   prerequisite_strong 成环 (A→B→C→A)
- reversed_prerequisite   A→B 且 B→A 同时存在
- duplicate_concept       同 name_primary 不同 id
- broken_reference        edge 端点不在 concepts 表
- isolated_subgraph       与主连通分量断开的小岛
- contradictory_definition  LLM stub（无 LLM → 跳过）

主入口 find_conflicts(db, kg_id, llm=None) → list[ConflictItem]
"""
from __future__ import annotations

import pytest

from shared.errors import TutorError
from shared.models import (
    ConceptRow,
    Corpus,
    KnowledgeGraphRow,
    RelationRow,
)
from shared.storage import RelationalStore


def _concept(kg_id: str, cid: str, name: str | None = None) -> ConceptRow:
    return ConceptRow(
        id=cid, kg_id=kg_id, base_id=cid,
        name_primary=name or cid, names_json=[name or cid],
        category="definition", definition=f"{cid} 定义",
        informal_description="", abstract_level=0.5,
        bloom_level="understand", domain="x",
        cognitive_load_estimate=0.3, typical_learning_time_min=10,
        prereq_count=0, prereq_max_depth=0, formula_density=0,
        coupling=0, confidence=0.9, full_json={},
    )


def _edge(kg_id, frm, to, typ="prerequisite_strong") -> RelationRow:
    return RelationRow(
        kg_id=kg_id, from_id=frm, to_id=to, type=typ,
        weight=0.6, explanation="", confidence=0.5, deprecated=False,
    )


def _make_kg(db: RelationalStore, kg_id: str, concepts: list, edges: list) -> None:
    with db.session() as s:
        if s.get(KnowledgeGraphRow, kg_id) is None:
            s.add(Corpus(id=f"c-{kg_id}", subject_id="x", user_id="u", manifest_json={}))
            s.add(KnowledgeGraphRow(
                kg_id=kg_id, subject_id="x", corpus_id=f"c-{kg_id}",
                version="v1", node_count=len(concepts), edge_count=len(edges),
                manifest_json={},
            ))
        for c in concepts:
            s.add(c)
        for e in edges:
            s.add(e)
        s.commit()


def test_detect_circular_prerequisite(tmp_db: RelationalStore) -> None:
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    kg = "kg-cycle"
    cs = [_concept(kg, "x:1:a"), _concept(kg, "x:1:b"), _concept(kg, "x:1:c")]
    # a→b→c→a 成环
    es = [_edge(kg, "x:1:a", "x:1:b"), _edge(kg, "x:1:b", "x:1:c"), _edge(kg, "x:1:c", "x:1:a")]
    _make_kg(tmp_db, kg, cs, es)

    conflicts = find_conflicts(db=tmp_db, kg_id=kg)
    types = {c.type for c in conflicts}
    assert "circular_prerequisite" in types


def test_detect_reversed_prerequisite(tmp_db: RelationalStore) -> None:
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    kg = "kg-rev"
    cs = [_concept(kg, "x:1:a"), _concept(kg, "x:1:b")]
    es = [_edge(kg, "x:1:a", "x:1:b"), _edge(kg, "x:1:b", "x:1:a")]
    _make_kg(tmp_db, kg, cs, es)

    conflicts = find_conflicts(db=tmp_db, kg_id=kg)
    rev = [c for c in conflicts if c.type == "reversed_prerequisite"]
    assert len(rev) >= 1
    # 应指出涉及的两个概念
    pair = {rev[0].concept_a, rev[0].concept_b}
    assert pair == {"x:1:a", "x:1:b"}


def test_detect_duplicate_concept(tmp_db: RelationalStore) -> None:
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    kg = "kg-dup"
    cs = [
        _concept(kg, "x:1:a", name="词袋模型"),
        _concept(kg, "x:2:b", name="词袋模型"),  # 同名不同 id
        _concept(kg, "x:3:c", name="稀疏向量"),
    ]
    _make_kg(tmp_db, kg, cs, [])

    conflicts = find_conflicts(db=tmp_db, kg_id=kg)
    dups = [c for c in conflicts if c.type == "duplicate_concept"]
    assert len(dups) >= 1
    assert {dups[0].concept_a, dups[0].concept_b} == {"x:1:a", "x:2:b"}


def test_detect_broken_reference(tmp_db: RelationalStore) -> None:
    """边端点指向不存在的 concept。"""
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    kg = "kg-broken"
    cs = [_concept(kg, "x:1:a")]
    # 边指向不存在的 x:1:ghost — 但 CHECK constraint 只防自环，FK 在 SQLite 默认不强制
    es = [_edge(kg, "x:1:a", "x:1:ghost")]
    # 直接构造（绕过 ORM 关系校验）
    with tmp_db.session() as s:
        s.add(Corpus(id=f"c-{kg}", subject_id="x", user_id="u", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id=kg, subject_id="x", corpus_id=f"c-{kg}",
            version="v1", node_count=1, edge_count=1, manifest_json={},
        ))
        s.add(cs[0])
        s.commit()
    with tmp_db.session() as s:
        s.add(es[0])
        s.commit()

    conflicts = find_conflicts(db=tmp_db, kg_id=kg)
    broken = [c for c in conflicts if c.type == "broken_reference"]
    assert len(broken) >= 1
    assert "x:1:ghost" in (broken[0].concept_b, broken[0].concept_a)


def test_detect_isolated_subgraph(tmp_db: RelationalStore) -> None:
    """两个互不连通的子图 → 小的那个被标为 isolated。"""
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    kg = "kg-iso"
    cs = [
        _concept(kg, "x:1:a"), _concept(kg, "x:1:b"), _concept(kg, "x:1:c"),  # 主图
        _concept(kg, "x:9:z"),  # 孤岛
    ]
    es = [
        _edge(kg, "x:1:a", "x:1:b"), _edge(kg, "x:1:b", "x:1:c"),
    ]
    _make_kg(tmp_db, kg, cs, es)

    conflicts = find_conflicts(db=tmp_db, kg_id=kg)
    iso = [c for c in conflicts if c.type == "isolated_subgraph"]
    # 孤岛 z 应被标出
    assert len(iso) >= 1
    iso_ids = {c.concept_a for c in iso}
    assert "x:9:z" in iso_ids


def test_no_conflicts_in_clean_kg(tmp_db: RelationalStore) -> None:
    """健康的链状 KG 不应报结构冲突。"""
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    kg = "kg-clean"
    cs = [_concept(kg, "x:1:a", "A"), _concept(kg, "x:1:b", "B"), _concept(kg, "x:1:c", "C")]
    es = [_edge(kg, "x:1:a", "x:1:b"), _edge(kg, "x:1:b", "x:1:c")]
    _make_kg(tmp_db, kg, cs, es)

    conflicts = find_conflicts(db=tmp_db, kg_id=kg)
    structural = [
        c for c in conflicts
        if c.type in (
            "circular_prerequisite", "reversed_prerequisite",
            "duplicate_concept", "broken_reference",
        )
    ]
    assert structural == []


def test_conflict_item_has_resolution(tmp_db: RelationalStore) -> None:
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    kg = "kg-res"
    cs = [_concept(kg, "x:1:a"), _concept(kg, "x:1:b")]
    es = [_edge(kg, "x:1:a", "x:1:b"), _edge(kg, "x:1:b", "x:1:a")]
    _make_kg(tmp_db, kg, cs, es)

    conflicts = find_conflicts(db=tmp_db, kg_id=kg)
    assert conflicts
    for c in conflicts:
        assert c.description
        assert c.suggested_resolution


def test_unknown_kg_raises(tmp_db: RelationalStore) -> None:
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    with pytest.raises(TutorError) as exc:
        find_conflicts(db=tmp_db, kg_id="no-such-kg")
    assert exc.value.code == "KG_NOT_FOUND"


def test_self_loop_excluded_from_reversed(tmp_db: RelationalStore) -> None:
    """自环边不存在（CHECK 约束），但确保检测不误判单向边为 reversed。"""
    from servers.knowledge_mcp.resolve_conflicts import find_conflicts

    kg = "kg-single"
    cs = [_concept(kg, "x:1:a"), _concept(kg, "x:1:b")]
    es = [_edge(kg, "x:1:a", "x:1:b")]  # 仅单向
    _make_kg(tmp_db, kg, cs, es)

    conflicts = find_conflicts(db=tmp_db, kg_id=kg)
    rev = [c for c in conflicts if c.type == "reversed_prerequisite"]
    assert rev == []


@pytest.mark.asyncio
async def test_resolve_conflicts_tool_no_longer_stub(tmp_db: RelationalStore) -> None:
    from servers.knowledge_mcp import server as srv

    fn = getattr(srv.resolve_conflicts, "fn", srv.resolve_conflicts)
    import os
    os.environ["DATABASE_URL"] = tmp_db.url
    with pytest.raises(TutorError) as exc:
        await fn(kg_id="no-such-kg")
    assert exc.value.code == "KG_NOT_FOUND"
