"""新增两类系统主动动作（show_counter_example / pace_feedback）+ 选择逻辑测试。

break_suggestion 已由 gain_loop_monitor 覆盖，这里只测新增的两类与三级优先选择。
"""
from __future__ import annotations

from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    ErrorAnalysis,
    Example,
    GainLoopBreak,
    SourceRef,
)


def _concept(*, with_counter: bool) -> Concept:
    return Concept(
        id="t:1:limit",
        names=["极限"],
        category="definition",
        definition="函数在某点的极限",
        informal_description="无限逼近",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.7, domain="math"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=1, prereq_max_depth=1, formula_density=0.5,
            coupling=0.3, cognitive_load_estimate=0.6, typical_learning_time_min=30,
        ),
        counter_examples=(
            [Example(text="1/n 在 n→∞ 时不是发散", type="counterexample")]
            if with_counter else []
        ),
        confidence=0.8,
        sources=[SourceRef(type="textbook", ref="x.md")],
    )


# ----------------------------- 工厂 ----------------------------- #

def test_make_show_counter_example_uses_first_counter() -> None:
    from servers.tutoring_mcp.teaching_actions import make_show_counter_example

    act = make_show_counter_example(_concept(with_counter=True))
    assert act is not None
    assert act.type == "show_counter_example"
    assert "1/n" in act.content
    assert act.metadata["trigger"] == "misconception"


def test_make_show_counter_example_none_without_counters() -> None:
    from servers.tutoring_mcp.teaching_actions import make_show_counter_example

    assert make_show_counter_example(_concept(with_counter=False)) is None


def test_make_pace_feedback_directions() -> None:
    from servers.tutoring_mcp.teaching_actions import make_pace_feedback

    slow = make_pace_feedback(direction="slow_down", reason="overload")
    fast = make_pace_feedback(direction="speed_up")
    assert slow.type == "pace_feedback" and slow.metadata["direction"] == "slow_down"
    assert fast.metadata["direction"] == "speed_up"
    assert slow.content != fast.content


# ----------------------- select_system_action ----------------------- #

def _break() -> GainLoopBreak:
    return GainLoopBreak(
        type="student_withdrawal", evidence=["x"], repair_action_hint="rebuild_safety"
    )


def _err(t: str) -> ErrorAnalysis:
    return ErrorAnalysis(type=t)  # type: ignore[arg-type]


def test_break_has_highest_priority() -> None:
    """即便同时过载 + 误解，回路断裂修复仍优先。"""
    from servers.tutoring_mcp.engine import select_system_action

    act = select_system_action(
        brk=_break(), prev_load=0.1, new_load=0.9,
        error_analysis=_err("concept_confusion"), concept=_concept(with_counter=True),
    )
    assert act is not None and act.type == "break_suggestion"


def test_pace_feedback_on_overload_rising_edge() -> None:
    from servers.tutoring_mcp.engine import select_system_action

    act = select_system_action(
        brk=None, prev_load=0.6, new_load=0.8,
        error_analysis=_err("concept_confusion"), concept=_concept(with_counter=True),
    )
    assert act is not None and act.type == "pace_feedback"


def test_no_pace_feedback_when_already_overloaded() -> None:
    """已经在过载区间（非上升沿）→ 不重复 pace_feedback，落到反例分支。"""
    from servers.tutoring_mcp.engine import select_system_action

    act = select_system_action(
        brk=None, prev_load=0.8, new_load=0.85,
        error_analysis=_err("concept_confusion"), concept=_concept(with_counter=True),
    )
    assert act is not None and act.type == "show_counter_example"


def test_counter_example_on_misconception_with_counters() -> None:
    from servers.tutoring_mcp.engine import select_system_action

    act = select_system_action(
        brk=None, prev_load=0.2, new_load=0.3,
        error_analysis=_err("overgeneralization"), concept=_concept(with_counter=True),
    )
    assert act is not None and act.type == "show_counter_example"


def test_no_counter_example_without_counters() -> None:
    from servers.tutoring_mcp.engine import select_system_action

    act = select_system_action(
        brk=None, prev_load=0.2, new_load=0.3,
        error_analysis=_err("concept_confusion"), concept=_concept(with_counter=False),
    )
    assert act is None


def test_no_counter_example_for_non_misconception_error() -> None:
    from servers.tutoring_mcp.engine import select_system_action

    act = select_system_action(
        brk=None, prev_load=0.2, new_load=0.3,
        error_analysis=_err("arithmetic_mistake"), concept=_concept(with_counter=True),
    )
    assert act is None


def test_none_when_all_calm() -> None:
    from servers.tutoring_mcp.engine import select_system_action

    act = select_system_action(
        brk=None, prev_load=0.2, new_load=0.25,
        error_analysis=None, concept=_concept(with_counter=True),
    )
    assert act is None
