"""类比桥接 — 精简版状态机。

完整见 specs/teaching-strategy-formalism.md §5。本切片实现:
    IDLE → ESTABLISH_SOURCE → DRAW_ANALOGY → APPLY_ANALOGY → IDENTIFY_LIMITS → TRANSITION

强调: 类比失效点必须标记（IDENTIFY_LIMITS 状态）。
"""
from __future__ import annotations

from shared.schemas import TeachingAction

from .base import Strategy


class AnalogyStrategy(Strategy):
    name = "analogy"
    TERMINAL_STATES = frozenset({"TRANSITION"})

    def start(self, *, target, mastery_map, params):
        self.target = target
        self.params = params or {}
        self.state = "ESTABLISH_SOURCE"

    def get_action(self) -> TeachingAction:
        t = self.target
        if t is None:
            return TeachingAction(type="explain", content="（未启动）", estimated_duration_min=0)
        name = t.names[0]
        if self.state == "ESTABLISH_SOURCE":
            return TeachingAction(
                type="explain",
                content=f"在讲 {name} 之前，我们先看一个你熟悉的类似情景。",
                estimated_duration_min=4,
            )
        if self.state == "DRAW_ANALOGY":
            return TeachingAction(
                type="explain",
                content=f"想象那个熟悉情景就像 {name}：结构对应、行为相似。",
                estimated_duration_min=4,
            )
        if self.state == "APPLY_ANALOGY":
            return TeachingAction(
                type="show_example",
                content=f"用这个类比解释 {name} 的一个具体例子。",
                estimated_duration_min=5,
            )
        if self.state == "IDENTIFY_LIMITS":
            return TeachingAction(
                type="explain",
                content=f"重要：类比不是恒等。{name} 在以下方面与原情景不同……",
                estimated_duration_min=3,
            )
        if self.state == "TRANSITION":
            return TeachingAction(
                type="explain",
                content=f"现在抛开类比，看 {name} 自身的精确定义：{t.definition}",
                estimated_duration_min=3,
            )
        return TeachingAction(type="explain", content="（待启动）", estimated_duration_min=0)

    def transition(self, *, event, payload):
        # 线性推进：每次 answered 推一步
        order = [
            "ESTABLISH_SOURCE", "DRAW_ANALOGY", "APPLY_ANALOGY",
            "IDENTIFY_LIMITS", "TRANSITION",
        ]
        if event == "answered" and self.state in order:
            i = order.index(self.state)
            if i + 1 < len(order):
                self.state = order[i + 1]
