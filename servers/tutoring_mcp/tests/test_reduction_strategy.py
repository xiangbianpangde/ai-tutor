"""Reduction 完整状态机契约测试。

合同来源: ai-tutor-system-design/specs/teaching-strategy-formalism.md §1

状态机:
  IDLE → PLAN → INTRO → EXPLAIN → CHECK → (PRACTICE | NEXT | FLAG_DIFFICULT)
  PRACTICE → (NEXT | EXPLAIN)
  FLAG_DIFFICULT → switch_strategy

事件:
- start                      → IDLE → INTRO
- intro_done                  → INTRO → EXPLAIN
- explain_done                → EXPLAIN → CHECK
- answered(correctness=correct)   → CHECK → PRACTICE
- answered(correctness=partial)   → CHECK → EXPLAIN（再讲一次）
- answered(correctness=incorrect) → CHECK → EXPLAIN（attempt+1）或 FLAG_DIFFICULT（attempt 满）
- practice_done(accuracy>0.8) → PRACTICE → NEXT
- practice_done(accuracy<0.5) → PRACTICE → EXPLAIN
- next                        → NEXT → INTRO (下一概念，外部决定)
"""
from __future__ import annotations

from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    TeachingAction,
)


def _concept(name: str = "测试概念", cid: str = "test:1.1:demo") -> Concept:
    return Concept(
        id=cid,
        names=[name],
        category="definition",
        definition=f"{name} 的定义",
        informal_description=f"{name} 通俗解释",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.5, domain="d"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0,
            formula_density=0.1, coupling=0.1,
            cognitive_load_estimate=0.3, typical_learning_time_min=15,
        ),
        confidence=0.85,
    )


def test_start_transitions_to_intro() -> None:
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    assert s.state == "IDLE"
    s.start(target=_concept(), mastery_map={}, params={})
    assert s.state == "INTRO"


def test_intro_explain_check_linear_path() -> None:
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    s.start(target=_concept(), mastery_map={}, params={})
    assert s.state == "INTRO"
    s.transition(event="intro_done", payload={})
    assert s.state == "EXPLAIN"
    s.transition(event="explain_done", payload={})
    assert s.state == "CHECK"


def test_answered_correct_goes_to_practice() -> None:
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    s.start(target=_concept(), mastery_map={}, params={})
    s.transition(event="intro_done", payload={})
    s.transition(event="explain_done", payload={})
    assert s.state == "CHECK"
    s.transition(event="answered", payload={"correctness": "correct"})
    assert s.state == "PRACTICE"


def test_answered_partial_revisits_explain() -> None:
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    s.start(target=_concept(), mastery_map={}, params={})
    s.transition(event="intro_done", payload={})
    s.transition(event="explain_done", payload={})
    s.transition(event="answered", payload={"correctness": "partial"})
    assert s.state == "EXPLAIN"


def test_repeated_incorrect_flags_difficult() -> None:
    """连续两次 incorrect 应触发 FLAG_DIFFICULT。"""
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    s.start(target=_concept(), mastery_map={}, params={})
    s.transition(event="intro_done", payload={})
    s.transition(event="explain_done", payload={})
    # 第一次 incorrect → 回 EXPLAIN，attempt+1
    s.transition(event="answered", payload={"correctness": "incorrect"})
    assert s.state == "EXPLAIN"
    assert s.attempt_count == 1
    # 重新走到 CHECK
    s.transition(event="explain_done", payload={})
    # 第二次 incorrect → FLAG_DIFFICULT
    s.transition(event="answered", payload={"correctness": "incorrect"})
    assert s.state == "FLAG_DIFFICULT"


def test_practice_high_accuracy_goes_next() -> None:
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    s.start(target=_concept(), mastery_map={}, params={})
    s.transition(event="intro_done", payload={})
    s.transition(event="explain_done", payload={})
    s.transition(event="answered", payload={"correctness": "correct"})
    s.transition(event="practice_done", payload={"accuracy": 0.9})
    assert s.state == "NEXT"


def test_practice_low_accuracy_back_to_explain() -> None:
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    s.start(target=_concept(), mastery_map={}, params={})
    s.transition(event="intro_done", payload={})
    s.transition(event="explain_done", payload={})
    s.transition(event="answered", payload={"correctness": "correct"})
    s.transition(event="practice_done", payload={"accuracy": 0.3})
    assert s.state == "EXPLAIN"


def test_actions_differ_per_state() -> None:
    """不同 state 返回不同 TeachingAction.type。"""
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    s.start(target=_concept(), mastery_map={}, params={})
    intro_action = s.get_action()
    assert intro_action.type == "explain"

    s.transition(event="intro_done", payload={})
    explain_action = s.get_action()
    assert explain_action.type in {"explain", "show_example"}

    s.transition(event="explain_done", payload={})
    check_action = s.get_action()
    assert check_action.type == "ask_question"


def test_state_alias_stub_for_back_compat() -> None:
    """保留 ReductionStub 别名让旧测试不破。"""
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy, ReductionStub

    assert ReductionStub is ReductionStrategy or issubclass(ReductionStub, ReductionStrategy)


def test_get_action_before_start_safe() -> None:
    """未 start 时 get_action 不抛错，返回提示性 action。"""
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    a = s.get_action()
    assert isinstance(a, TeachingAction)


# ------------- FIX-E：PRACTICE 接受 answered（#16/#20 死循环回归） ------------- #
# respond 统一发 "answered"，旧实现 PRACTICE 只认 "practice_done"——对练习作答
# 永远推不动状态机，ACP 实测连续 14 步 give_exercise。


def _practice_strategy():
    from servers.tutoring_mcp.strategies.reduction import ReductionStrategy

    s = ReductionStrategy()
    s.start(target=_concept(), mastery_map={}, params={})
    s.state = "PRACTICE"
    return s


def test_practice_answered_correct_goes_next() -> None:
    s = _practice_strategy()
    s.transition(event="answered", payload={"correctness": "correct"})
    assert s.state == "NEXT"


def test_practice_answered_partial_goes_next() -> None:
    s = _practice_strategy()
    s.transition(event="answered", payload={"correctness": "partial"})
    assert s.state == "NEXT"


def test_practice_answered_incorrect_back_to_explain() -> None:
    s = _practice_strategy()
    s.transition(event="answered", payload={"correctness": "incorrect"})
    assert s.state == "EXPLAIN"
    assert s.attempt_count == 1


def test_practice_done_legacy_event_still_works() -> None:
    s = _practice_strategy()
    s.transition(event="practice_done", payload={"accuracy": 0.9})
    assert s.state == "NEXT"
