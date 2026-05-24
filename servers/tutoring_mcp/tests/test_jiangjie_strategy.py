"""降阶法策略 (JiangjieStrategy) 测试。

规格来源: ai-tutor-system-design/specs/jiangjie-strategy.md

状态机:
    IDLE → GOAL → REDUCE → COMPLEMENT → RECONSTRUCT → REVIEW → NEXT
                                            ↑              |
                                            └─── fail ─────┘
    任意推进状态 attempt 超限 → FLAG_DIFFICULT

降阶法与 ReductionStrategy 是两种独立策略，不是升级关系。
"""
from __future__ import annotations

import pytest

from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    TeachingAction,
)
from servers.tutoring_mcp.strategies import get_strategy, list_strategies
from servers.tutoring_mcp.strategies.jiangjie import JiangjieStrategy


def _concept(name: str = "偏导数") -> Concept:
    return Concept(
        id="math:1.1:partial_derivative",
        names=[name],
        category="definition",
        definition=f"{name} 是函数对其中一个变量的变化率",
        informal_description=f"{name} 衡量曲面在某方向有多陡",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.6, domain="calculus"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=1, prereq_max_depth=1,
            formula_density=0.5, coupling=0.3,
            cognitive_load_estimate=0.5, typical_learning_time_min=30,
        ),
        common_misconceptions=[
            "偏导数和其他变量没关系",
            "偏导存在就一定连续",
            "混合偏导恒相等",
        ],
        confidence=0.85,
    )


def _start(strategy: JiangjieStrategy, **params) -> None:
    strategy.start(target=_concept(), mastery_map={}, params=params)


# --------------------------------------------------------------------------- #
# 基础契约
# --------------------------------------------------------------------------- #


def test_name_and_registry():
    s = JiangjieStrategy()
    assert s.name == "jiangjie"
    assert "jiangjie" in list_strategies()
    assert isinstance(get_strategy("jiangjie"), JiangjieStrategy)


def test_start_enters_goal():
    s = JiangjieStrategy()
    _start(s, sub_step_count=3, error_count=4)
    assert s.state == "GOAL"
    act = s.get_action()
    assert isinstance(act, TeachingAction)
    assert act.type == "explain"


def test_get_action_before_start_is_safe():
    s = JiangjieStrategy()
    act = s.get_action()
    assert isinstance(act, TeachingAction)


# --------------------------------------------------------------------------- #
# 完整正向流程
# --------------------------------------------------------------------------- #


def test_full_happy_path():
    s = JiangjieStrategy()
    _start(s, sub_step_count=3, error_count=4)

    # GOAL → REDUCE
    s.transition(event="goal_understood", payload={})
    assert s.state == "REDUCE"
    assert s._atom_index == 0

    # 3 个原子问题全答对 → COMPLEMENT
    for i in range(3):
        assert s.state == "REDUCE"
        s.transition(event="answered", payload={"correctness": "correct"})
    assert s.state == "COMPLEMENT"
    assert s._error_index == 0

    # 4 个补集错误逐一排除 → RECONSTRUCT
    for i in range(4):
        assert s.state == "COMPLEMENT"
        s.transition(event="answered", payload={"correctness": "correct"})
    assert s.state == "RECONSTRUCT"

    # 4 个骨架引导问题 → REVIEW
    for i in range(4):
        assert s.state == "RECONSTRUCT"
        s.transition(event="answered", payload={"correctness": "correct", "answer": f"part{i}"})
    assert s.state == "REVIEW"

    # REVIEW 通过 → NEXT
    s.transition(event="answered", payload={"correctness": "correct"})
    assert s.state == "NEXT"

    # NEXT → IDLE
    s.transition(event="next", payload={})
    assert s.state == "IDLE"


# --------------------------------------------------------------------------- #
# REDUCE 答错不推进
# --------------------------------------------------------------------------- #


def test_reduce_incorrect_does_not_advance():
    s = JiangjieStrategy()
    _start(s, sub_step_count=3, error_count=4)
    s.transition(event="goal_understood", payload={})
    assert s._atom_index == 0
    s.transition(event="answered", payload={"correctness": "incorrect"})
    assert s._atom_index == 0  # 不变
    assert s.state == "REDUCE"


def test_reduce_partial_advances_and_marks_weak():
    s = JiangjieStrategy()
    _start(s, sub_step_count=3, error_count=4)
    s.transition(event="goal_understood", payload={})
    s.transition(event="answered", payload={"correctness": "partial"})
    assert s._atom_index == 1
    assert 0 in s.weak_atoms


# --------------------------------------------------------------------------- #
# COMPLEMENT 答错也推进（补集教学）
# --------------------------------------------------------------------------- #


def test_complement_incorrect_still_advances():
    s = JiangjieStrategy()
    _start(s, sub_step_count=1, error_count=3)
    s.transition(event="goal_understood", payload={})
    s.transition(event="answered", payload={"correctness": "correct"})
    assert s.state == "COMPLEMENT"
    # 答错也推进（让学生知道为什么错就算完成）
    s.transition(event="answered", payload={"correctness": "incorrect"})
    assert s._error_index == 1
    assert s.state == "COMPLEMENT"


# --------------------------------------------------------------------------- #
# REVIEW 失败回退到 RECONSTRUCT
# --------------------------------------------------------------------------- #


def _advance_to_review(s: JiangjieStrategy) -> None:
    s.transition(event="goal_understood", payload={})
    while s.state == "REDUCE":
        s.transition(event="answered", payload={"correctness": "correct"})
    while s.state == "COMPLEMENT":
        s.transition(event="answered", payload={"correctness": "correct"})
    while s.state == "RECONSTRUCT":
        s.transition(event="answered", payload={"correctness": "correct", "answer": "x"})
    assert s.state == "REVIEW"


def test_review_fail_returns_to_reconstruct():
    s = JiangjieStrategy()
    _start(s, sub_step_count=2, error_count=2)
    _advance_to_review(s)
    s.transition(event="answered", payload={"correctness": "incorrect"})
    assert s.state == "RECONSTRUCT"
    assert s._skeleton_index == 0  # 重置以便重建


# --------------------------------------------------------------------------- #
# FLAG_DIFFICULT
# --------------------------------------------------------------------------- #


def test_reduce_repeated_failure_flags_difficult():
    s = JiangjieStrategy()
    _start(s, sub_step_count=3, error_count=4, max_attempts=3)
    s.transition(event="goal_understood", payload={})
    for _ in range(3):
        s.transition(event="answered", payload={"correctness": "incorrect"})
    assert s.state == "FLAG_DIFFICULT"
    act = s.get_action()
    assert act.type == "break_suggestion"


def test_review_repeated_failure_flags_difficult():
    s = JiangjieStrategy()
    _start(s, sub_step_count=1, error_count=1, max_attempts=2)
    _advance_to_review(s)
    for _ in range(2):
        if s.state == "RECONSTRUCT":
            while s.state == "RECONSTRUCT":
                s.transition(event="answered", payload={"correctness": "correct", "answer": "x"})
        s.transition(event="answered", payload={"correctness": "incorrect"})
    assert s.state == "FLAG_DIFFICULT"


# --------------------------------------------------------------------------- #
# 知识骨架产出
# --------------------------------------------------------------------------- #


def test_reconstruct_produces_skeleton():
    s = JiangjieStrategy()
    _start(s, sub_step_count=1, error_count=1)
    s.transition(event="goal_understood", payload={})
    s.transition(event="answered", payload={"correctness": "correct"})
    s.transition(event="answered", payload={"correctness": "correct"})
    assert s.state == "RECONSTRUCT"
    answers = ["前提X", "逻辑Y", "结论Z", "易错点W"]
    for a in answers:
        s.transition(event="answered", payload={"correctness": "correct", "answer": a})
    skel = s.skeleton
    assert skel["premise"] == "前提X"
    assert skel["logic"] == "逻辑Y"
    assert skel["conclusion"] == "结论Z"
    assert skel["pitfalls"] == "易错点W"


# --------------------------------------------------------------------------- #
# 脚手架 / 难度 影响动作文本
# --------------------------------------------------------------------------- #


def test_scaffold_level_affects_goal_action():
    high = JiangjieStrategy()
    _start(high, scaffold_level=3)
    low = JiangjieStrategy()
    _start(low, scaffold_level=0)
    assert len(high.get_action().content) > len(low.get_action().content)


def test_reduce_action_shows_progress():
    s = JiangjieStrategy()
    _start(s, sub_step_count=4, error_count=4)
    s.transition(event="goal_understood", payload={})
    act = s.get_action()
    assert act.type == "ask_question"
    assert "1/4" in act.content


def test_complement_action_uses_misconceptions():
    s = JiangjieStrategy()
    _start(s, sub_step_count=1, error_count=3)
    s.transition(event="goal_understood", payload={})
    s.transition(event="answered", payload={"correctness": "correct"})
    act = s.get_action()
    assert act.type == "ask_question"
    # 第一个补集错误来自 concept.common_misconceptions
    assert "偏导数和其他变量没关系" in act.content


def test_review_difficulty_reflected_in_metadata():
    easy = JiangjieStrategy()
    _start(easy, sub_step_count=1, error_count=1, difficulty_multiplier=0.6)
    _advance_to_review(easy)
    act = easy.get_action()
    assert act.type == "give_exercise"
    assert act.metadata.get("difficulty_multiplier") == 0.6


def test_unknown_event_is_noop():
    s = JiangjieStrategy()
    _start(s, sub_step_count=3, error_count=4)
    s.transition(event="goal_understood", payload={})
    s.transition(event="bogus_event", payload={})
    assert s.state == "REDUCE"
    assert s._atom_index == 0
