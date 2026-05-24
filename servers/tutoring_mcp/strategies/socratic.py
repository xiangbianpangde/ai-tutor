"""苏格拉底法 — 精简版状态机。

完整见 specs/teaching-strategy-formalism.md §3。本切片实现:
    IDLE → QUESTION → WAIT_ANSWER → ANALYZE_ANSWER → {QUESTION | HINT | REVEAL}

后续切片可加: NUDGE、question_chain_depth 控制、hint_level 自动调整。
"""
from __future__ import annotations

from shared.schemas import TeachingAction

from .base import Strategy


class SocraticStrategy(Strategy):
    name = "socratic"
    TERMINAL_STATES = frozenset({"REVEAL"})
    STATE_FIELDS = ("question_depth",)

    def start(self, *, target, mastery_map, params):
        self.target = target
        self.params = params or {}
        self.attempt_count = 0
        self.question_depth = 0
        self.state = "QUESTION"

    def get_action(self) -> TeachingAction:
        t = self.target
        if t is None:
            return TeachingAction(type="explain", content="（未启动）", estimated_duration_min=0)
        name = t.names[0]
        if self.state == "QUESTION":
            return TeachingAction(
                type="ask_question",
                content=f"在你看来，{name} 解决了什么问题？",
                estimated_duration_min=3,
                metadata={"depth": self.question_depth},
            )
        if self.state == "HINT":
            return TeachingAction(
                type="provide_hint",
                content=f"提示：{t.informal_description or '注意 ' + name + ' 的定义边界'}",
                estimated_duration_min=2,
            )
        if self.state == "REVEAL":
            return TeachingAction(
                type="reveal_answer",
                content=f"{name}：{t.definition}",
                estimated_duration_min=3,
            )
        if self.state == "ANALYZE_ANSWER":
            return TeachingAction(
                type="explain",
                content="让我们看看你刚才的思路里哪一步抓住了关键。",
                estimated_duration_min=2,
            )
        return TeachingAction(type="explain", content="（待启动）", estimated_duration_min=0)

    def transition(self, *, event, payload):
        if self.state == "QUESTION" and event == "answered":
            self.state = "ANALYZE_ANSWER"
            return
        if self.state == "ANALYZE_ANSWER" and event == "answered":
            corr = (payload or {}).get("correctness", "incorrect")
            max_depth = int(self.params.get("question_chain_depth", 4))
            if corr == "correct":
                self.question_depth += 1
                if self.question_depth >= max_depth:
                    self.state = "REVEAL"
                else:
                    self.state = "QUESTION"
                return
            self.attempt_count += 1
            if self.attempt_count >= max_depth:
                self.state = "REVEAL"
            else:
                self.state = "HINT"
            return
        if self.state == "HINT" and event == "answered":
            self.state = "QUESTION"
            return
