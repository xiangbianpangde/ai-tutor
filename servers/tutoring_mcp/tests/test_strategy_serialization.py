"""策略状态序列化 + 完成检测契约测试（P1 #4 引擎集成的基础）。

引擎每次调用都从 ctx 重建策略实例，因此带内部计数器的策略（jiangjie/feynman/
socratic/pbl）必须能 export_state → 存 ctx → restore_state 无损还原。
否则它们的进度（_atom_index / question_depth / milestones_done…）每轮归零。
"""
from __future__ import annotations

import pytest

from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
)
from servers.tutoring_mcp.strategies import get_strategy, list_strategies


def _concept() -> Concept:
    return Concept(
        id="sub:1.1:c",
        names=["概念"],
        category="definition",
        definition="定义",
        informal_description="解释",
        classification=ConceptClassification(bloom_level="understand", abstract_level=0.5, domain="d"),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0, formula_density=0.1, coupling=0.1,
            cognitive_load_estimate=0.3, typical_learning_time_min=15,
        ),
        common_misconceptions=["误解A", "误解B"],
        confidence=0.85,
    )


ALL = ["reduction", "jiangjie", "feynman", "socratic", "analogy", "pbl", "spaced_repetition"]


@pytest.mark.parametrize("name", ALL)
def test_is_complete_false_at_start(name):
    s = get_strategy(name)
    s.start(target=_concept(), mastery_map={}, params={})
    assert s.is_complete() is False


@pytest.mark.parametrize("name", ALL)
def test_export_restore_roundtrip_preserves_state(name):
    s = get_strategy(name)
    s.start(target=_concept(), mastery_map={}, params={"sub_step_count": 3, "error_count": 4})
    # 推进几步
    for _ in range(3):
        s.transition(event="answered", payload={"correctness": "correct"})
    snapshot = s.export_state()
    assert isinstance(snapshot, dict)
    assert snapshot["state"] == s.state

    # 重建并还原
    s2 = get_strategy(name)
    s2.start(target=_concept(), mastery_map={}, params={"sub_step_count": 3, "error_count": 4})
    s2.restore_state(snapshot)
    assert s2.state == s.state
    assert s2.export_state() == snapshot


def test_jiangjie_internal_counters_survive_roundtrip():
    s = get_strategy("jiangjie")
    s.start(target=_concept(), mastery_map={}, params={"sub_step_count": 4, "error_count": 5})
    s.transition(event="goal_understood", payload={})
    s.transition(event="answered", payload={"correctness": "partial"})  # _atom_index=1, weak={0}
    snap = s.export_state()
    assert snap["_atom_index"] == 1
    assert 0 in snap["weak_atoms"]

    s2 = get_strategy("jiangjie")
    s2.start(target=_concept(), mastery_map={}, params={})
    s2.restore_state(snap)
    assert s2._atom_index == 1
    assert s2.weak_atoms == {0}
    assert s2.sub_step_count == 4  # pace 参数也还原
    assert s2.error_count == 5


def test_terminal_states_declared():
    expected = {
        "reduction": "NEXT", "jiangjie": "NEXT", "feynman": "PASS",
        "socratic": "REVEAL", "analogy": "TRANSITION", "pbl": "FINAL_REVIEW",
    }
    for name, term in expected.items():
        s = get_strategy(name)
        assert term in s.TERMINAL_STATES, f"{name} 缺终止态 {term}"


def test_spaced_repetition_completes_on_correct():
    s = get_strategy("spaced_repetition")
    s.start(target=_concept(), mastery_map={"sub:1.1:c": 0.75}, params={})
    assert not s.is_complete()
    s.transition(event="answered", payload={"correctness": "correct"})
    assert s.is_complete()
