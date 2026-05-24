"""Strategy 抽象基类契约测试。

合同来源: ai-tutor-system-design/specs/teaching-strategy-formalism.md

约束:
- Strategy 必须暴露 name + 当前状态机状态 + start/transition/get_action 三个抽象方法
- 一个最小可实例化的 ReductionStub 验证抽象类约束不会过严
- 抽象类本身不能实例化
"""
from __future__ import annotations

import pytest

from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    TeachingAction,
    TeachingContext,
)


def _concept() -> Concept:
    return Concept(
        id="x:1.1:a",
        names=["A"],
        category="definition",
        definition="x",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.5, domain="d"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0,
            prereq_max_depth=0,
            formula_density=0.1,
            coupling=0.1,
            cognitive_load_estimate=0.1,
            typical_learning_time_min=10,
        ),
        confidence=0.9,
    )


def test_strategy_base_is_abstract() -> None:
    from servers.tutoring_mcp.strategies.base import Strategy

    with pytest.raises(TypeError):
        Strategy()  # type: ignore[abstract]


def test_subclass_must_implement_three_methods() -> None:
    from servers.tutoring_mcp.strategies.base import Strategy

    class Partial(Strategy):
        name = "partial"

        # 缺 start/transition/get_action

    with pytest.raises(TypeError):
        Partial()  # type: ignore[abstract]


def test_reduction_stub_minimal_lifecycle() -> None:
    """最小可工作的 ReductionStub: IDLE → PLAN → EXPLAIN → NEXT，可调用三个方法。"""
    from servers.tutoring_mcp.strategies.reduction import ReductionStub

    target = _concept()
    s = ReductionStub()
    assert s.name == "reduction"
    assert s.state == "IDLE"

    s.start(target=target, mastery_map={}, params={})
    assert s.state in ("PLAN", "INTRO", "EXPLAIN")

    action = s.get_action()
    assert isinstance(action, TeachingAction)

    s.transition(event="explain_done", payload={})
    # 转移到下一状态（不抛即可）


def test_strategy_protocol_supports_typing() -> None:
    """Strategy 类型可以作为参数标注（隐式 Protocol 兼容）。"""
    from servers.tutoring_mcp.strategies.base import Strategy
    from servers.tutoring_mcp.strategies.reduction import ReductionStub

    def take_strategy(s: Strategy) -> str:
        return s.name

    assert take_strategy(ReductionStub()) == "reduction"
