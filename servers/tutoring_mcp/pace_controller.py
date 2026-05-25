"""PaceController — 统一的节奏控制门面。

设计 §3.3 规划了独立的 PaceController，但实现中节奏决策分散在三处：
- flow_regulator.FlowRegulator : FlowLevel + 负荷 + 正确率 → PaceConfig（参数表）
- strategy_selector            : 过载阈值 0.75 门控策略选择
- engine                       : 过载「上升沿」触发 pace_feedback

本类把这些收拢到一个入口，并把过载阈值收成**单一来源** OVERLOAD_THRESHOLD，
避免 0.75 在多处各写一份、日后悄悄漂移。

注意：纯结构性收拢，不改变任何行为——recommend_pace 仍委托 FlowRegulator，
阈值数值与各处原值一致。
"""
from __future__ import annotations

from shared.schemas import FlowLevel

from .flow_regulator import FlowRegulator, PaceConfig, get_regulator

# 认知负荷过载阈值 —— 全系统唯一来源（strategy_selector / engine 都引用此处）。
OVERLOAD_THRESHOLD: float = 0.75


class PaceController:
    """节奏控制门面：组合 FlowRegulator + 过载判定 + pace_feedback 触发判定。

    无状态（FlowRegulator 也无状态），可作模块级单例。
    """

    def __init__(self, regulator: FlowRegulator | None = None) -> None:
        self._regulator = regulator or get_regulator()

    def recommend_pace(
        self,
        *,
        flow_level: FlowLevel | int,
        cognitive_load: float = 0.0,
        recent_accuracy: float | None = None,
    ) -> PaceConfig:
        """FlowLevel(+负荷+正确率) → PaceConfig。委托 FlowRegulator，行为不变。"""
        return self._regulator.recommend_pace(
            flow_level=flow_level,
            cognitive_load=cognitive_load,
            recent_accuracy=recent_accuracy,
        )

    @staticmethod
    def is_overloaded(cognitive_load: float) -> bool:
        """当前负荷是否处于过载区间（> 阈值）。"""
        return cognitive_load > OVERLOAD_THRESHOLD

    @staticmethod
    def crossed_into_overload(prev_load: float, new_load: float) -> bool:
        """认知负荷「上升沿」跨过过载阈值——pace_feedback 的触发条件。

        仅在「之前未过载、本轮过载」时为真，避免持续过载期间反复打断。
        """
        return prev_load < OVERLOAD_THRESHOLD <= new_load


_controller: PaceController | None = None


def get_pace_controller() -> PaceController:
    global _controller
    if _controller is None:
        _controller = PaceController()
    return _controller
