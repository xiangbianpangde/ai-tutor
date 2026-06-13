"""拓扑排序的章节号 tie-break 回归测试。

发现于真实笔记验证（4月24日-星期四-聚类.md）：
入度都为 0 时按字符串排序会让 "1.1:x" 排在 "1:x" 之前
（"." ASCII 46 < ":" ASCII 58），父节点反而排到子节点之后。
"""
from __future__ import annotations

from servers.tutoring_mcp.server import _chapter_key, _topological_order
from shared.storage import RelationalStore


def test_chapter_key_parses_dotted_decimal() -> None:
    assert _chapter_key("subject:1:slug") == (1,)
    assert _chapter_key("subject:1.1:slug") == (1, 1)
    assert _chapter_key("subject:1.4.2:slug") == (1, 4, 2)


def test_chapter_key_parent_before_child() -> None:
    assert _chapter_key("x:1:a") < _chapter_key("x:1.1:b")
    assert _chapter_key("x:1.1:a") < _chapter_key("x:1.1.1:b")
    assert _chapter_key("x:1:a") < _chapter_key("x:2:b")


def test_chapter_key_handles_malformed_id() -> None:
    assert _chapter_key("garbage") == (10**9,)
    assert _chapter_key("subject:nonnumeric:slug") == (10**9,)


def test_topological_order_puts_parent_before_child_when_indegree_zero(tmp_db: RelationalStore) -> None:
    """模拟真实 bug 场景：父节 # 词袋模型 和子节 ## 用法 都入度=0。

    期望：父节排在前。
    """
    from shared.models import ConceptRow as ConceptRowORM
    from shared.models import KnowledgeGraphRow
    from shared.models import RelationRow as RelationRowORM

    kg_id = "test-kg"
    with tmp_db.session() as s:
        s.add(
            KnowledgeGraphRow(
                kg_id=kg_id,
                subject_id="test",
                corpus_id="c1",
                version="v1",
                node_count=3,
                edge_count=2,
                manifest_json={},
            )
        )
        # 父节 + 两个子节，子节间有 prerequisite_strong
        for cid, name in [
            ("test:1:parent", "父"),
            ("test:1.1:child_a", "子A"),
            ("test:1.2:child_b", "子B"),
        ]:
            s.add(
                ConceptRowORM(
                    id=cid,
                    kg_id=kg_id,
                    name_primary=name,
                    names_json=[name],
                    category="definition",
                    definition=name,
                    informal_description="",
                    abstract_level=0.3,
                    bloom_level="remember",
                    domain="test",
                    cognitive_load_estimate=0.3,
                    typical_learning_time_min=10,
                    prereq_count=0,
                    prereq_max_depth=0,
                    formula_density=0.0,
                    coupling=0.0,
                    confidence=0.5,
                    full_json={"id": cid, "names": [name]},
                )
            )
        # 子A → 子B：prereq；父和子之间是 part_of（不参与拓扑）
        s.add(
            RelationRowORM(
                kg_id=kg_id, from_id="test:1.1:child_a", to_id="test:1.2:child_b",
                type="prerequisite_strong", weight=0.6, explanation="", confidence=0.5,
            )
        )
        s.add(
            RelationRowORM(
                kg_id=kg_id, from_id="test:1.1:child_a", to_id="test:1:parent",
                type="part_of", weight=0.9, explanation="", confidence=0.7,
            )
        )
        s.commit()

    order = _topological_order(tmp_db, kg_id)
    ids = [n.id for n in order]
    # 父节点必须排在子节点之前
    assert ids.index("test:1:parent") < ids.index("test:1.1:child_a")
    # prereq 顺序：child_a 在 child_b 之前
    assert ids.index("test:1.1:child_a") < ids.index("test:1.2:child_b")


def test_topological_handles_multi_chapter(tmp_db: RelationalStore) -> None:
    """两章 + 各 2 子节，确保章节内顺序正确。"""
    from shared.models import ConceptRow as ConceptRowORM
    from shared.models import KnowledgeGraphRow

    kg_id = "multi-kg"
    with tmp_db.session() as s:
        s.add(
            KnowledgeGraphRow(
                kg_id=kg_id, subject_id="t", corpus_id="c", version="v",
                node_count=6, edge_count=0, manifest_json={},
            )
        )
        for cid in [
            "t:1:ch1", "t:1.1:a", "t:1.2:b",
            "t:2:ch2", "t:2.1:c", "t:2.2:d",
        ]:
            s.add(ConceptRowORM(
                id=cid, kg_id=kg_id, name_primary=cid, names_json=[cid],
                category="definition", definition=cid, informal_description="",
                abstract_level=0.3, bloom_level="remember", domain="t",
                cognitive_load_estimate=0.3, typical_learning_time_min=10,
                prereq_count=0, prereq_max_depth=0, formula_density=0.0,
                coupling=0.0, confidence=0.5, full_json={"id": cid},
            ))
        s.commit()

    order = [n.id for n in _topological_order(tmp_db, kg_id)]
    assert order == ["t:1:ch1", "t:1.1:a", "t:1.2:b", "t:2:ch2", "t:2.1:c", "t:2.2:d"]
