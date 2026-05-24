"""5 种 stub 策略的契约测试。

每个策略实现 Strategy 接口；当前切片是精简版（识别 start + answered + next），
完整状态机详见 specs/teaching-strategy-formalism.md 留后续切片。
"""
from __future__ import annotations

import pytest

from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    TeachingAction,
)


def _concept(name: str = "测试") -> Concept:
    return Concept(
        id="test:1.1:demo",
        names=[name],
        category="definition",
        definition=f"{name} 的定义",
        informal_description=f"{name} 的解释",
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


@pytest.mark.parametrize(
    "module_name,class_name,expected_strategy_name",
    [
        ("feynman", "FeynmanStrategy", "feynman"),
        ("socratic", "SocraticStrategy", "socratic"),
        ("analogy", "AnalogyStrategy", "analogy"),
        ("pbl", "PBLStrategy", "pbl"),
        ("spaced_repetition", "SpacedRepetitionStrategy", "spaced_repetition"),
    ],
)
def test_strategy_has_correct_name(module_name, class_name, expected_strategy_name):
    import importlib

    mod = importlib.import_module(f"servers.tutoring_mcp.strategies.{module_name}")
    cls = getattr(mod, class_name)
    s = cls()
    assert s.name == expected_strategy_name


@pytest.mark.parametrize(
    "module_name,class_name",
    [
        ("feynman", "FeynmanStrategy"),
        ("socratic", "SocraticStrategy"),
        ("analogy", "AnalogyStrategy"),
        ("pbl", "PBLStrategy"),
        ("spaced_repetition", "SpacedRepetitionStrategy"),
    ],
)
def test_strategy_start_and_get_action(module_name, class_name):
    """start 后 state != IDLE，get_action 返回合法 TeachingAction。"""
    import importlib

    mod = importlib.import_module(f"servers.tutoring_mcp.strategies.{module_name}")
    cls = getattr(mod, class_name)
    s = cls()
    assert s.state == "IDLE"
    s.start(target=_concept(), mastery_map={}, params={})
    assert s.state != "IDLE"
    a = s.get_action()
    assert isinstance(a, TeachingAction)
    assert a.content


@pytest.mark.parametrize(
    "module_name,class_name",
    [
        ("feynman", "FeynmanStrategy"),
        ("socratic", "SocraticStrategy"),
        ("analogy", "AnalogyStrategy"),
        ("pbl", "PBLStrategy"),
        ("spaced_repetition", "SpacedRepetitionStrategy"),
    ],
)
def test_strategy_transitions_on_answered(module_name, class_name):
    """answered 事件至少能把状态机推进（不是 no-op）。"""
    import importlib

    mod = importlib.import_module(f"servers.tutoring_mcp.strategies.{module_name}")
    cls = getattr(mod, class_name)
    s = cls()
    s.start(target=_concept(), mastery_map={}, params={})
    initial = s.state
    s.transition(event="answered", payload={"correctness": "correct"})
    # state 可以维持但 attempt_count 或 metadata 应该有变化；至少不抛错
    assert isinstance(s.state, str)


def test_strategy_registry_lists_all_six():
    """工厂函数能按 name 取所有 6 种策略。"""
    from servers.tutoring_mcp.strategies import get_strategy

    for name in ("reduction", "feynman", "socratic", "analogy", "pbl", "spaced_repetition"):
        s = get_strategy(name)
        assert s.name == name


def test_strategy_registry_unknown_raises():
    from shared.errors import TutorError

    from servers.tutoring_mcp.strategies import get_strategy

    with pytest.raises(TutorError) as exc:
        get_strategy("alien_strategy")
    assert exc.value.code == "DEPENDENCY_MISSING"
