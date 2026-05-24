"""项目驱动法 (PBL) — 精简版状态机。

完整见 specs/teaching-strategy-formalism.md §4。本切片实现:
    IDLE → ASSIGN → PLAN_REVIEW → MILESTONE_CHECK → FINAL_REVIEW

后续切片可加: scaffolding_level、多个 milestone 串联、自动产物评估。
"""
from __future__ import annotations

from shared.schemas import TeachingAction

from .base import Strategy


class PBLStrategy(Strategy):
    name = "pbl"
    TERMINAL_STATES = frozenset({"FINAL_REVIEW"})
    STATE_FIELDS = ("milestones_done",)

    def start(self, *, target, mastery_map, params):
        self.target = target
        self.params = params or {}
        self.milestones_done = 0
        self.state = "ASSIGN"

    def get_action(self) -> TeachingAction:
        t = self.target
        if t is None:
            return TeachingAction(type="explain", content="（未启动）", estimated_duration_min=0)
        name = t.names[0]
        if self.state == "ASSIGN":
            return TeachingAction(
                type="give_exercise",
                content=f"做一个用到 {name} 的小项目：试着设计一个简单的应用。",
                estimated_duration_min=20,
            )
        if self.state == "PLAN_REVIEW":
            return TeachingAction(
                type="ask_question",
                content="给我看看你的方案大纲。我们一起看看是否抓住了核心。",
                estimated_duration_min=5,
            )
        if self.state == "MILESTONE_CHECK":
            return TeachingAction(
                type="checkpoint",
                content=f"第 {self.milestones_done + 1} 个 milestone：展示你目前的进展。",
                estimated_duration_min=5,
            )
        if self.state == "FINAL_REVIEW":
            return TeachingAction(
                type="reflection",
                content=f"项目完成。回头看，{name} 在你的方案里起了什么作用？",
                estimated_duration_min=5,
            )
        return TeachingAction(type="explain", content="（待启动）", estimated_duration_min=0)

    def transition(self, *, event, payload):
        if self.state == "ASSIGN" and event == "answered":
            self.state = "PLAN_REVIEW"
            return
        if self.state == "PLAN_REVIEW" and event == "answered":
            corr = (payload or {}).get("correctness", "incorrect")
            if corr == "correct":
                self.state = "MILESTONE_CHECK"
            else:
                self.state = "ASSIGN"  # 重新设计
            return
        if self.state == "MILESTONE_CHECK" and event == "answered":
            self.milestones_done += 1
            target_milestones = int(self.params.get("milestones", 2))
            if self.milestones_done >= target_milestones:
                self.state = "FINAL_REVIEW"
            return
