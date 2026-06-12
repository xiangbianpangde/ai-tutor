"""降阶法 (Reduction of Order) 教学策略 — 完整状态机。

合同来源: ai-tutor-system-design/specs/teaching-strategy-formalism.md §1

状态机:
    IDLE → PLAN → INTRO → EXPLAIN → CHECK → {PRACTICE | NEXT | FLAG_DIFFICULT}
    PRACTICE → {NEXT | EXPLAIN}
    FLAG_DIFFICULT → switch_strategy（外部决定）

事件:
    start                         → IDLE → INTRO
    intro_done                    → INTRO → EXPLAIN
    explain_done                  → EXPLAIN → CHECK
    answered{correctness}         → CHECK → {PRACTICE | EXPLAIN | FLAG_DIFFICULT}
    practice_done{accuracy}       → PRACTICE → {NEXT | EXPLAIN}
    next                          → NEXT → IDLE（外部传新 target）

attempt_count 表示当前 concept 的失败尝试数；超过 max_attempts 触发 FLAG_DIFFICULT。
"""
from __future__ import annotations

from typing import Any

from shared.schemas import TeachingAction

from .base import Strategy


class ReductionStrategy(Strategy):
    name = "reduction"
    TERMINAL_STATES = frozenset({"NEXT"})

    DEFAULT_MAX_ATTEMPTS = 2  # 第 N 次 incorrect 后 FLAG_DIFFICULT

    def start(
        self,
        *,
        target,
        mastery_map: dict[str, float],
        params: dict[str, Any],
    ) -> None:
        self.target = target
        self.mastery_map = mastery_map
        self.params = params or {}
        self.attempt_count = 0
        # 路径规划留给 strategy_selector / engine（spine 切片不真实排）
        self.state = "INTRO"

    def get_action(self) -> TeachingAction:
        t = self.target
        if t is None:
            return TeachingAction(
                type="explain",
                content="（策略未启动，请先 start()）",
                estimated_duration_min=0,
            )
        name = t.names[0]
        if self.state == "INTRO":
            return TeachingAction(
                type="explain",
                content=f"我们现在来看 {name}。{t.informal_description or t.definition}",
                estimated_duration_min=3,
            )
        if self.state == "EXPLAIN":
            return TeachingAction(
                type="show_example",
                content=f"{name} 的核心定义：{t.definition}",
                estimated_duration_min=5,
                metadata={"attempt": self.attempt_count},
            )
        if self.state == "CHECK":
            return TeachingAction(
                type="ask_question",
                content=f"用你自己的话说说 {name} 是什么？",
                estimated_duration_min=3,
            )
        if self.state == "PRACTICE":
            return TeachingAction(
                type="give_exercise",
                content=f"做一道关于 {name} 的练习：根据定义判断下面的例子是否属于该概念。",
                estimated_duration_min=5,
            )
        if self.state == "FLAG_DIFFICULT":
            return TeachingAction(
                type="break_suggestion",
                content=f"我们在 {name} 上卡了几次。建议换一种方式（例如类比 / 苏格拉底提问），或先放一放休息一下。",
                estimated_duration_min=1,
            )
        if self.state == "NEXT":
            return TeachingAction(
                type="reflection",
                content=f"{name} 这一步告一段落。准备进入下一个概念。",
                estimated_duration_min=1,
            )
        # IDLE / PLAN / 兜底
        return TeachingAction(
            type="explain",
            content="（策略待启动）",
            estimated_duration_min=0,
        )

    def advance_event(self) -> str | None:
        # 讲解/展示/练习态由非答题事件推进；CHECK 等学生作答（走 respond）
        return {
            "INTRO": "intro_done",
            "EXPLAIN": "explain_done",
            "PRACTICE": "practice_done",
        }.get(self.state)

    def transition(self, *, event: str, payload: dict[str, Any]) -> None:
        # 显式映射；未识别事件 → no-op（保持当前状态，调用方可看日志）
        if self.state == "INTRO" and event == "intro_done":
            self.state = "EXPLAIN"
            return
        if self.state == "EXPLAIN" and event == "explain_done":
            self.state = "CHECK"
            return
        if self.state == "CHECK" and event == "answered":
            corr = (payload or {}).get("correctness", "incorrect")
            if corr == "correct":
                self.state = "PRACTICE"
                self.attempt_count = 0
                return
            if corr == "partial":
                self.state = "EXPLAIN"
                self.attempt_count += 1
                return
            # incorrect
            self.attempt_count += 1
            max_attempts = int(
                self.params.get("max_attempts", self.DEFAULT_MAX_ATTEMPTS)
            )
            if self.attempt_count >= max_attempts:
                self.state = "FLAG_DIFFICULT"
            else:
                self.state = "EXPLAIN"
            return
        if self.state == "PRACTICE" and event in ("practice_done", "answered"):
            # respond 统一发 "answered"（带 correctness），旧的 "practice_done"（带
            # accuracy）保留兼容。修复 #16/#20：此前 PRACTICE 只认 practice_done，
            # 对练习作答永远推不动状态机 → 实测无限 give_exercise 死循环。
            if event == "answered":
                corr = (payload or {}).get("correctness", "incorrect")
                acc = {"correct": 1.0, "partial": 0.6, "incorrect": 0.0}.get(corr, 0.0)
            else:
                acc = float((payload or {}).get("accuracy", 0.0))
            if acc >= 0.5:
                self.state = "NEXT"
            else:
                self.state = "EXPLAIN"
                self.attempt_count += 1
            return
        if self.state == "NEXT" and event in ("next", "start_next_concept"):
            # 外部应传新 target 后再调 start()
            self.state = "IDLE"
            return
        # 未匹配 → 不变；这是 strategy 的"宽容"语义


# 向后兼容旧名
class ReductionStub(ReductionStrategy):
    """旧名保留。新代码请用 ReductionStrategy。"""
