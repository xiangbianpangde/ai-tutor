"""费曼法 (Feynman Technique) — 精简版状态机。

完整状态机见 specs/teaching-strategy-formalism.md §2。本切片实现:
    IDLE → PROMPT → WAIT_EXPLAIN → EVALUATE → {PASS | GUIDED_CORRECTION | SIMPLIFY}

后续切片可加: MODEL 阶段、fidelity 自动评分、simplify_trigger。
"""
from __future__ import annotations

from shared.schemas import TeachingAction

from .base import Strategy


class FeynmanStrategy(Strategy):
    name = "feynman"
    TERMINAL_STATES = frozenset({"PASS"})

    def start(self, *, target, mastery_map, params):
        self.target = target
        self.params = params or {}
        self.attempt_count = 0
        self.state = "PROMPT"

    def get_action(self) -> TeachingAction:
        t = self.target
        if t is None:
            return TeachingAction(type="explain", content="（未启动）", estimated_duration_min=0)
        name = t.names[0]
        if self.state == "PROMPT":
            return TeachingAction(
                type="request_explanation",
                content=f"请用你自己的话，把 {name} 讲给一个零基础的人听。",
                estimated_duration_min=5,
            )
        if self.state == "EVALUATE":
            return TeachingAction(
                type="explain",
                content=f"看看你刚才对 {name} 的解释里，最准确的部分是什么。",
                estimated_duration_min=3,
            )
        if self.state == "GUIDED_CORRECTION":
            return TeachingAction(
                type="provide_hint",
                content=f"试着加入这个细节再讲一遍 {name}。",
                estimated_duration_min=3,
            )
        if self.state == "SIMPLIFY":
            return TeachingAction(
                type="explain",
                content=f"我们换更朴素的语言。{t.informal_description or t.definition}",
                estimated_duration_min=3,
            )
        if self.state == "PASS":
            return TeachingAction(
                type="reflection",
                content=f"你能把 {name} 讲清楚了。这一步过了。",
                estimated_duration_min=1,
            )
        return TeachingAction(type="explain", content="（待启动）", estimated_duration_min=0)

    def transition(self, *, event, payload):
        if self.state == "PROMPT" and event in ("answered", "explanation_received"):
            self.state = "EVALUATE"
            return
        if self.state == "EVALUATE" and event == "answered":
            corr = (payload or {}).get("correctness", "incorrect")
            if corr == "correct":
                self.state = "PASS"
                return
            self.attempt_count += 1
            max_attempts = int(self.params.get("max_attempts", 3))
            if self.attempt_count >= max_attempts:
                self.state = "SIMPLIFY"
            else:
                self.state = "GUIDED_CORRECTION"
            return
        if self.state == "GUIDED_CORRECTION" and event == "answered":
            self.state = "PROMPT"
            return
        if self.state == "SIMPLIFY" and event == "answered":
            self.state = "PROMPT"
            self.attempt_count = 0
            return
