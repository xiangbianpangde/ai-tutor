"""PaceController 门面测试。

PaceController 是节奏决策的统一入口（收拢 flow_regulator + 过载阈值），
recommend_pace 行为应与底层 FlowRegulator 完全一致（纯委托）。
"""
from __future__ import annotations

from shared.schemas import FlowLevel


def test_overload_threshold_is_single_source() -> None:
    """strategy_selector 与 pace_controller 引用同一个过载阈值。"""
    from servers.tutoring_mcp import strategy_selector
    from servers.tutoring_mcp.pace_controller import OVERLOAD_THRESHOLD

    assert OVERLOAD_THRESHOLD == 0.75
    assert strategy_selector._OVERLOAD_THRESHOLD == OVERLOAD_THRESHOLD


def test_is_overloaded() -> None:
    from servers.tutoring_mcp.pace_controller import PaceController

    assert PaceController.is_overloaded(0.8) is True
    assert PaceController.is_overloaded(0.75) is False  # 阈值是严格大于
    assert PaceController.is_overloaded(0.5) is False


def test_crossed_into_overload_rising_edge_only() -> None:
    from servers.tutoring_mcp.pace_controller import PaceController

    assert PaceController.crossed_into_overload(0.6, 0.8) is True   # 上升沿
    assert PaceController.crossed_into_overload(0.8, 0.85) is False  # 已在过载区
    assert PaceController.crossed_into_overload(0.8, 0.6) is False   # 下降
    assert PaceController.crossed_into_overload(0.6, 0.7) is False   # 未跨过


def test_recommend_pace_delegates_to_regulator() -> None:
    """PaceController.recommend_pace 与 FlowRegulator.recommend_pace 输出一致。"""
    from servers.tutoring_mcp.flow_regulator import FlowRegulator
    from servers.tutoring_mcp.pace_controller import PaceController

    pc = PaceController()
    reg = FlowRegulator()
    for level in FlowLevel:
        a = pc.recommend_pace(flow_level=level, cognitive_load=0.8, recent_accuracy=0.2)
        b = reg.recommend_pace(flow_level=level, cognitive_load=0.8, recent_accuracy=0.2)
        assert a.to_dict() == b.to_dict()


def test_get_pace_controller_singleton() -> None:
    from servers.tutoring_mcp.pace_controller import get_pace_controller

    assert get_pace_controller() is get_pace_controller()
