"""间隔复习 (Spaced Repetition) — 精简版策略。

不是真正的状态机，更像"复习模式选择器"。本切片只实现按学生当前 mastery
选 review_mode（quick_quiz / concept_map / teach_back / error_revisit）。

后续切片接 L3 的 ForgettingCurve / ReviewScheduler 做真实间隔调度。
"""
from __future__ import annotations

from shared.schemas import TeachingAction

from .base import Strategy


class SpacedRepetitionStrategy(Strategy):
    name = "spaced_repetition"
    TERMINAL_STATES = frozenset({"DONE"})
    STATE_FIELDS = ("review_mode",)

    def start(self, *, target, mastery_map, params):
        self.target = target
        self.params = params or {}
        # 根据 mastery_map 中本概念的掌握度决定 review_mode
        cur_mastery = (mastery_map or {}).get(target.id if target else "", 0.5)
        if cur_mastery > 0.7:
            self.state = "QUICK_QUIZ"
        elif cur_mastery > 0.4:
            self.state = "CONCEPT_MAP"
        else:
            self.state = "TEACH_BACK"
        self.review_mode = self.state.lower()

    def get_action(self) -> TeachingAction:
        t = self.target
        if t is None:
            return TeachingAction(type="explain", content="（未启动）", estimated_duration_min=0)
        name = t.names[0]
        if self.state == "QUICK_QUIZ":
            return TeachingAction(
                type="ask_question",
                content=f"快速复习 {name}：30 秒内回答关键定义。",
                estimated_duration_min=1,
                metadata={"review_mode": "quick_quiz"},
            )
        if self.state == "CONCEPT_MAP":
            return TeachingAction(
                type="ask_question",
                content=f"画一下 {name} 与它前置概念的关系。",
                estimated_duration_min=5,
                metadata={"review_mode": "concept_map"},
            )
        if self.state == "TEACH_BACK":
            return TeachingAction(
                type="request_explanation",
                content=f"把 {name} 再讲一遍，给零基础的人。",
                estimated_duration_min=5,
                metadata={"review_mode": "teach_back"},
            )
        if self.state == "ERROR_REVISIT":
            return TeachingAction(
                type="give_exercise",
                content=f"重做你上次在 {name} 上答错的题（变体）。",
                estimated_duration_min=5,
                metadata={"review_mode": "error_revisit"},
            )
        return TeachingAction(type="explain", content="（待启动）", estimated_duration_min=0)

    def transition(self, *, event, payload):
        if event == "answered":
            corr = (payload or {}).get("correctness", "incorrect")
            if corr == "correct":
                # 复习答对 → 本概念复习完成
                self.state = "DONE"
            else:
                # 答错降级到更深入的复习
                self.state = "TEACH_BACK"
