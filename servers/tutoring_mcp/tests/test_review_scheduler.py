"""ReviewScheduler 多因子调度契约测试。

打分公式（多因子加权）:
    priority = urgency(1-recall) * difficulty * recency_decay

接口:
    schedule_review_plan(db, user, subject, available_minutes) → DailyReviewPlan
    pick_review_mode(mastery, has_recent_errors) → ReviewMode
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.models import (
    ConceptRow,
    KnowledgeGraphRow,
    Subject,
    User,
)
from shared.storage import RelationalStore


def _make_concept(
    cid: str = "ml:1:bow",
    kg_id: str = "kg1",
    name: str = "x",
    difficulty: float = 0.4,
    learning_time: int = 15,
) -> ConceptRow:
    return ConceptRow(
        id=cid, kg_id=kg_id, name_primary=name, names_json=[name],
        category="definition", definition=f"{name} 定义",
        informal_description="", abstract_level=0.5,
        bloom_level="understand", domain="ml",
        cognitive_load_estimate=difficulty,
        typical_learning_time_min=learning_time,
        prereq_count=1, prereq_max_depth=1,
        formula_density=0.3, coupling=0.3,
        confidence=0.85,
        full_json={"id": cid, "names": [name]},
    )


@pytest.fixture
def db_with_kg(tmp_db: RelationalStore) -> tuple[RelationalStore, str]:
    from shared.models import Corpus
    kg_id = "test-kg"
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ml", user_id="yhn", display_name="ML"))
        s.add(Corpus(id="c1", subject_id="ml", user_id="yhn", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id=kg_id, subject_id="ml", corpus_id="c1",
            version="v1", node_count=3, edge_count=0, manifest_json={},
        ))
        s.add(_make_concept("ml:1:a", kg_id, "A", difficulty=0.3))
        s.add(_make_concept("ml:1:b", kg_id, "B", difficulty=0.7))
        s.add(_make_concept("ml:1:c", kg_id, "C", difficulty=0.5))
        s.commit()
    return tmp_db, kg_id


def test_pick_review_mode_by_mastery() -> None:
    from servers.tutoring_mcp.review_scheduler import pick_review_mode

    assert pick_review_mode(mastery=0.85, has_recent_errors=False) == "quick_quiz"
    assert pick_review_mode(mastery=0.55, has_recent_errors=False) == "concept_map"
    assert pick_review_mode(mastery=0.25, has_recent_errors=False) == "teach_back"
    # 有错误时优先 error_revisit
    assert pick_review_mode(mastery=0.7, has_recent_errors=True) == "error_revisit"


def test_schedule_review_plan_no_due_concepts(db_with_kg) -> None:
    """新用户没有任何复习历史 → 返回空 plan。"""
    from servers.tutoring_mcp.review_scheduler import schedule_review_plan

    db, _ = db_with_kg
    plan = schedule_review_plan(
        db=db, user_id="yhn", subject_id="ml", available_minutes=60,
    )
    assert plan.user_id == "yhn"
    assert plan.subject_id == "ml"
    assert plan.sections == []
    assert plan.total_estimated_min == 0


def test_schedule_review_plan_picks_overdue(db_with_kg) -> None:
    """有 due reviews 时优先收集。"""
    from servers.tutoring_mcp.memory_store import MemoryStore
    from servers.tutoring_mcp.review_scheduler import schedule_review_plan

    db, _ = db_with_kg
    mem = MemoryStore(db)
    # 让 a 和 b 都已 overdue：7 天前复习，accuracy 0.5（λ 拟合不出但默认 0.3 就让 next_at = 4 天后，已 overdue）
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    mem.record_review(
        user_id="yhn", concept_id="ml:1:a", subject_id="ml",
        accuracy=0.5, review_mode="quick_quiz", review_date=seven_days_ago,
    )
    mem.record_review(
        user_id="yhn", concept_id="ml:1:b", subject_id="ml",
        accuracy=0.5, review_mode="quick_quiz", review_date=seven_days_ago,
    )

    plan = schedule_review_plan(
        db=db, user_id="yhn", subject_id="ml", available_minutes=60,
    )
    section_ids = [s.concept_id for s in plan.sections]
    assert "ml:1:a" in section_ids
    assert "ml:1:b" in section_ids
    assert plan.total_estimated_min > 0


def test_schedule_review_plan_respects_time_budget(db_with_kg) -> None:
    """available_minutes 限制总耗时不超额。"""
    from servers.tutoring_mcp.memory_store import MemoryStore
    from servers.tutoring_mcp.review_scheduler import schedule_review_plan

    db, _ = db_with_kg
    mem = MemoryStore(db)
    long_ago = datetime.utcnow() - timedelta(days=14)
    for cid in ["ml:1:a", "ml:1:b", "ml:1:c"]:
        mem.record_review(
            user_id="yhn", concept_id=cid, subject_id="ml",
            accuracy=0.3, review_mode="quick_quiz", review_date=long_ago,
        )

    # 给个很小的 budget
    plan = schedule_review_plan(
        db=db, user_id="yhn", subject_id="ml", available_minutes=8,
    )
    assert plan.total_estimated_min <= 8
    # 至少取了 1 个
    assert len(plan.sections) >= 1


def test_priority_orders_higher_urgency_first(tmp_db: RelationalStore) -> None:
    """难度相同时，更久未复习的概念排前面（隔离 overdue 单一因子）。"""
    from servers.tutoring_mcp.memory_store import MemoryStore
    from servers.tutoring_mcp.review_scheduler import schedule_review_plan
    from shared.models import Corpus

    kg_id = "kg-iso"
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ml", user_id="yhn", display_name="ML"))
        s.add(Corpus(id="c1", subject_id="ml", user_id="yhn", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id=kg_id, subject_id="ml", corpus_id="c1",
            version="v1", node_count=2, edge_count=0, manifest_json={},
        ))
        # 难度一致 → 排序由 overdue 主导
        s.add(_make_concept("ml:1:a", kg_id, "A", difficulty=0.5))
        s.add(_make_concept("ml:1:b", kg_id, "B", difficulty=0.5))
        s.commit()

    mem = MemoryStore(tmp_db)
    very_old = datetime.utcnow() - timedelta(days=30)
    less_old = datetime.utcnow() - timedelta(days=5)
    mem.record_review(
        user_id="yhn", concept_id="ml:1:a", subject_id="ml",
        accuracy=0.5, review_mode="quick_quiz", review_date=very_old,
    )
    mem.record_review(
        user_id="yhn", concept_id="ml:1:b", subject_id="ml",
        accuracy=0.5, review_mode="quick_quiz", review_date=less_old,
    )
    plan = schedule_review_plan(
        db=tmp_db, user_id="yhn", subject_id="ml", available_minutes=60,
    )
    ids = [s.concept_id for s in plan.sections]
    assert ids.index("ml:1:a") < ids.index("ml:1:b")


def test_section_review_mode_reflects_bkt_mastery(db_with_kg) -> None:
    """有 BKT 高 mastery → quick_quiz；低 mastery → teach_back。"""
    from servers.tutoring_mcp.bkt_store import BKTStore
    from servers.tutoring_mcp.memory_store import MemoryStore
    from servers.tutoring_mcp.review_scheduler import schedule_review_plan

    db, _ = db_with_kg
    mem = MemoryStore(db)
    bkt = BKTStore(db)
    long_ago = datetime.utcnow() - timedelta(days=14)
    # 让 a 是已掌握，b 是新手
    bkt.save("yhn", _bkt_with_mastery("ml:1:a", 0.9))
    bkt.save("yhn", _bkt_with_mastery("ml:1:b", 0.2))
    mem.record_review(
        user_id="yhn", concept_id="ml:1:a", subject_id="ml",
        accuracy=0.9, review_mode="quick_quiz", review_date=long_ago,
    )
    mem.record_review(
        user_id="yhn", concept_id="ml:1:b", subject_id="ml",
        accuracy=0.3, review_mode="teach_back", review_date=long_ago,
    )
    plan = schedule_review_plan(
        db=db, user_id="yhn", subject_id="ml", available_minutes=60,
    )
    by_id = {s.concept_id: s for s in plan.sections}
    if "ml:1:a" in by_id:
        assert by_id["ml:1:a"].review_mode == "quick_quiz"
    if "ml:1:b" in by_id:
        assert by_id["ml:1:b"].review_mode == "teach_back"


def _bkt_with_mastery(concept_id: str, mastery: float) -> BKTParams:  # noqa: F821 — 函数体内局部 import 的前置引用
    from shared.schemas import BKTParams
    return BKTParams(concept_id=concept_id, p_mastery=mastery, n_observations=5)
