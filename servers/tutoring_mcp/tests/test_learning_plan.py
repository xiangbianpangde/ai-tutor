"""多 Session 学习计划核心逻辑测试（P0 #3）。

build_plan：把拓扑序概念按顶层章节切成 Phase。
compute_progress：跨 Session 进度（已掌握/总数、当前 Phase、下一个该学的概念）。
"""
from __future__ import annotations

import pytest

from servers.tutoring_mcp import learning_plan as lp
from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    LearningPlan,
    LearningProgress,
)


def _c(cid: str, name: str, time_min: int = 30) -> Concept:
    return Concept(
        id=cid,
        names=[name],
        category="definition",
        definition=f"{name} 的定义",
        classification=ConceptClassification(bloom_level="understand", abstract_level=0.5, domain="d"),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0, formula_density=0.1, coupling=0.1,
            cognitive_load_estimate=0.3, typical_learning_time_min=time_min,
        ),
        confidence=0.85,
    )


def _ordered() -> list[Concept]:
    # 2 章：第 1 章（根 + 2 子）、第 2 章（根 + 1 子）
    return [
        _c("sub:1:ch1", "极限与连续", 20),
        _c("sub:1.1:lim", "数列极限", 30),
        _c("sub:1.2:cont", "连续性", 40),
        _c("sub:2:ch2", "导数", 20),
        _c("sub:2.1:def", "导数定义", 50),
    ]


# --------------------------------------------------------------------------- #
# build_plan
# --------------------------------------------------------------------------- #


def test_build_plan_groups_by_chapter():
    plan = lp.build_plan(user_id="u", subject_id="s", kg_id="kg", ordered_concepts=_ordered())
    assert isinstance(plan, LearningPlan)
    assert len(plan.phases) == 2
    assert plan.total_concepts == 5
    assert [p.phase for p in plan.phases] == [1, 2]
    assert plan.phases[0].concept_ids == ["sub:1:ch1", "sub:1.1:lim", "sub:1.2:cont"]
    assert plan.phases[1].concept_ids == ["sub:2:ch2", "sub:2.1:def"]


def test_phase_title_from_chapter_root():
    plan = lp.build_plan(user_id="u", subject_id="s", kg_id="kg", ordered_concepts=_ordered())
    assert plan.phases[0].title == "极限与连续"   # 章节根概念名
    assert plan.phases[1].title == "导数"


def test_phase_estimated_hours():
    plan = lp.build_plan(user_id="u", subject_id="s", kg_id="kg", ordered_concepts=_ordered())
    # 第 1 章 20+30+40=90min=1.5h；第 2 章 20+50=70min≈1.17h
    assert plan.phases[0].estimated_hours == pytest.approx(1.5, abs=0.01)
    assert plan.estimated_hours == pytest.approx((90 + 70) / 60.0, abs=0.01)


def test_build_plan_empty():
    plan = lp.build_plan(user_id="u", subject_id="s", kg_id="kg", ordered_concepts=[])
    assert plan.phases == []
    assert plan.total_concepts == 0


def test_build_plan_merges_non_contiguous_chapters():
    """拓扑序可能让同一章的概念不相邻（跨章前置）；每章仍应只对应一个 Phase。"""
    interleaved = [
        _c("sub:1:ch1", "第一章", 20),
        _c("sub:2:ch2", "第二章", 20),
        _c("sub:1.1:a", "1.1", 30),   # 第 1 章的概念又出现在第 2 章之后
        _c("sub:2.1:b", "2.1", 30),
    ]
    plan = lp.build_plan(user_id="u", subject_id="s", kg_id="kg", ordered_concepts=interleaved)
    assert len(plan.phases) == 2, "同一章不应被切成多个 Phase"
    p1 = next(p for p in plan.phases if p.title == "第一章")
    assert p1.concept_ids == ["sub:1:ch1", "sub:1.1:a"]
    assert p1.estimated_hours == pytest.approx(50 / 60.0, abs=0.01)


# --------------------------------------------------------------------------- #
# compute_progress
# --------------------------------------------------------------------------- #


def _plan() -> LearningPlan:
    return lp.build_plan(user_id="u", subject_id="s", kg_id="kg", ordered_concepts=_ordered())


def _names() -> dict[str, str]:
    return {c.id: c.names[0] for c in _ordered()}


def test_progress_fresh_all_pending():
    """全未掌握 → current_phase=1, next=第一个概念。"""
    prog = lp.compute_progress(plan=_plan(), mastery_of=lambda cid: 0.05, name_of=_names())
    assert isinstance(prog, LearningProgress)
    assert prog.concepts_total == 5
    assert prog.concepts_mastered == 0
    assert prog.current_phase == 1
    assert prog.next_concept_id == "sub:1:ch1"
    assert prog.next_concept_name == "极限与连续"
    assert not prog.completed
    assert [p.status for p in prog.phases] == ["in_progress", "pending"]


def test_progress_phase1_done():
    """第 1 章全掌握 → current_phase=2, next 进入第 2 章。"""
    mastered = {"sub:1:ch1", "sub:1.1:lim", "sub:1.2:cont"}
    prog = lp.compute_progress(
        plan=_plan(),
        mastery_of=lambda cid: 0.9 if cid in mastered else 0.05,
        name_of=_names(),
    )
    assert prog.concepts_mastered == 3
    assert prog.current_phase == 2
    assert prog.next_concept_id == "sub:2:ch2"
    assert [p.status for p in prog.phases] == ["done", "in_progress"]
    assert prog.phases[0].mastered_ratio == pytest.approx(1.0)


def test_progress_partial_phase_in_progress():
    """章内部分掌握 → 该 Phase in_progress，next 指向首个未掌握。"""
    mastered = {"sub:1:ch1"}
    prog = lp.compute_progress(
        plan=_plan(),
        mastery_of=lambda cid: 0.9 if cid in mastered else 0.05,
        name_of=_names(),
    )
    assert prog.current_phase == 1
    assert prog.next_concept_id == "sub:1.1:lim"
    assert prog.phases[0].status == "in_progress"
    assert prog.phases[0].concepts_mastered == 1


def test_progress_completed():
    prog = lp.compute_progress(plan=_plan(), mastery_of=lambda cid: 0.95, name_of=_names())
    assert prog.completed
    assert prog.current_phase is None
    assert prog.next_concept_id is None
    assert all(p.status == "done" for p in prog.phases)
    assert prog.overall_mastery_ratio == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# store
# --------------------------------------------------------------------------- #


def test_plan_store_roundtrip(tmp_db):
    from shared.models import Subject, User

    with tmp_db.session() as s:
        s.add(User(id="u"))
        s.add(Subject(id="s", user_id="u", display_name="x"))
        s.commit()

    store = lp.LearningPlanStore(tmp_db)
    assert store.load("u", "s") is None
    plan = _plan()
    store.save(plan)
    loaded = store.load("u", "s")
    assert loaded is not None
    assert loaded.total_concepts == 5
    assert [p.title for p in loaded.phases] == ["极限与连续", "导数"]
    # 二次 save 是 upsert，不产生多行
    store.save(plan)
    from shared.models import LearningPlanRow
    with tmp_db.session() as s:
        assert s.query(LearningPlanRow).count() == 1
