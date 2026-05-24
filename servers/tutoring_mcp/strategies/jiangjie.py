"""降阶法 (Jiangjie / Reduction-of-dimension) 教学策略 — 完整状态机。

规格来源: ai-tutor-system-design/specs/jiangjie-strategy.md
理论来源: doc/降阶学习法.md

降阶法**不是** ReductionStrategy 的升级版，而是一种独立的教学方法论：
    ReductionStrategy: 从定义出发 → 讲解 → 检测 → 练习
    JiangjieStrategy : 从目标出发 → 拆成原子问题 → 补集排除 → 骨架重构

状态机:
    IDLE → GOAL → REDUCE → COMPLEMENT → RECONSTRUCT → REVIEW → NEXT
                                            ↑              |
                                            └─── fail ─────┘
    任意推进状态 attempt_count ≥ max_attempts → FLAG_DIFFICULT

事件:
    start                    → IDLE → GOAL（在 start() 里完成）
    goal_understood          → GOAL → REDUCE
    answered{correctness}    → REDUCE / COMPLEMENT / RECONSTRUCT / REVIEW 推进
    reconstructed            → RECONSTRUCT → REVIEW（显式跳转，等价于答完 4 个引导问题）
    next / start_next_concept→ NEXT → IDLE

教学参数（由 FlowRegulator.recommend_pace() 经 PaceConfig.to_dict() 传入 params）:
    sub_step_count        原子问题数（REDUCE 阶段）
    error_count           补集枚举错误数（COMPLEMENT 阶段）
    confirm_each_step      是否每步追问确认
    scaffold_level         脚手架级别 0-3（影响 GOAL 动作详略）
    difficulty_multiplier  复习题难度系数（REVIEW 阶段，透传到 metadata）
    max_attempts           同一状态最大重试次数
"""
from __future__ import annotations

from typing import Any

from shared.schemas import TeachingAction

from .base import Strategy

# RECONSTRUCT 阶段的 4 个骨架引导问题（无需 LLM，结构化引导学生自述）
_SKELETON_PARTS = ("premise", "logic", "conclusion", "pitfalls")
_SKELETON_PROMPTS = (
    "这个结论成立的前提条件是什么？",
    "推理的核心逻辑，三两句话说清楚。",
    "最终的结论是什么？",
    "最容易在哪里犯错？",
)


class JiangjieStrategy(Strategy):
    """降阶学习法状态机。"""

    name = "jiangjie"
    TERMINAL_STATES = frozenset({"NEXT"})
    STATE_FIELDS = (
        "_atom_index", "_error_index", "_skeleton_index", "_review_fail_count",
        "weak_atoms", "skeleton",
        "sub_step_count", "error_count", "confirm_each_step",
        "scaffold_level", "difficulty_multiplier", "max_attempts",
    )

    DEFAULT_SUB_STEP_COUNT = 5
    DEFAULT_ERROR_COUNT = 7
    DEFAULT_MAX_ATTEMPTS = 3

    def start(
        self,
        *,
        target,
        mastery_map: dict[str, float],
        params: dict[str, Any],
    ) -> None:
        self.target = target
        self.mastery_map = mastery_map or {}
        self.params = params or {}

        self.sub_step_count = max(1, int(self.params.get("sub_step_count", self.DEFAULT_SUB_STEP_COUNT)))
        self.error_count = max(1, int(self.params.get("error_count", self.DEFAULT_ERROR_COUNT)))
        self.confirm_each_step = bool(self.params.get("confirm_each_step", True))
        self.scaffold_level = int(self.params.get("scaffold_level", 1))
        self.difficulty_multiplier = float(self.params.get("difficulty_multiplier", 1.0))
        self.max_attempts = max(1, int(self.params.get("max_attempts", self.DEFAULT_MAX_ATTEMPTS)))

        # 内部计数器
        self._atom_index = 0
        self._error_index = 0
        self._skeleton_index = 0
        self.attempt_count = 0
        self._review_fail_count = 0  # 跨 RECONSTRUCT 重试累计的 REVIEW 失败数

        # 产出物
        self.weak_atoms: set[int] = set()      # 被标记为 partial 的原子问题序号
        self.skeleton: dict[str, str] = {}      # 知识骨架（前提/逻辑/结论/易错点）

        self.state = "GOAL"

    # ------------------------------------------------------------------ #
    # get_action
    # ------------------------------------------------------------------ #

    def get_action(self) -> TeachingAction:
        t = self.target
        if t is None:
            return TeachingAction(
                type="explain",
                content="（降阶法未启动，请先 start()）",
                estimated_duration_min=0,
            )
        name = t.names[0]

        if self.state == "GOAL":
            return self._goal_action(t, name)
        if self.state == "REDUCE":
            return self._reduce_action(name)
        if self.state == "COMPLEMENT":
            return self._complement_action(t, name)
        if self.state == "RECONSTRUCT":
            return self._reconstruct_action(name)
        if self.state == "REVIEW":
            return self._review_action(name)
        if self.state == "NEXT":
            return TeachingAction(
                type="reflection",
                content=f"【{name}】的知识骨架已建立。准备进入下一个概念。",
                estimated_duration_min=1,
                metadata={"skeleton": dict(self.skeleton)},
            )
        if self.state == "FLAG_DIFFICULT":
            return TeachingAction(
                type="break_suggestion",
                content=(
                    f"我们在【{name}】上卡了几次。降阶法暂时推进不下去，"
                    f"建议换一种策略（如类比桥接 / 苏格拉底提问），或先休息一下。"
                ),
                estimated_duration_min=1,
            )
        # IDLE / 兜底
        return TeachingAction(type="explain", content="（降阶法待启动）", estimated_duration_min=0)

    def _goal_action(self, t, name: str) -> TeachingAction:
        goal = t.informal_description or t.definition
        if self.scaffold_level >= 3:
            content = (
                f"接下来我们用降阶法学【{name}】。\n"
                f"学完这个，你就能：{goal}。\n"
                f"为什么重要：它是后续概念的基础。\n"
                f"前置要求：先确认你掌握了它的前置知识，需要我快速回顾吗？"
            )
            dur = 4
        elif self.scaffold_level >= 1:
            content = f"我们用降阶法学【{name}】。目标：{goal}。准备好了吗？"
            dur = 2
        else:
            content = f"【{name}】：{t.definition}。开始。"
            dur = 1
        return TeachingAction(type="explain", content=content, estimated_duration_min=dur)

    def _reduce_action(self, name: str) -> TeachingAction:
        n = self.sub_step_count
        i = self._atom_index
        question = self._atom_question(name, i)
        content = f"原子问题 {i + 1}/{n}：{question}"
        if self.confirm_each_step:
            content += "（一句话回答，答完我会和你确认）"
        return TeachingAction(
            type="ask_question",
            content=content,
            estimated_duration_min=2,
            metadata={"atom_index": i, "weak": i in self.weak_atoms},
        )

    def _complement_action(self, t, name: str) -> TeachingAction:
        m = self.error_count
        i = self._error_index
        misconception = self._misconception(t, i)
        content = (
            f"❌ 误解 {i + 1}/{m}：「{misconception}」\n"
            f"这个理解为什么是错的？"
        )
        return TeachingAction(
            type="ask_question",
            content=content,
            estimated_duration_min=2,
            metadata={"error_index": i},
        )

    def _reconstruct_action(self, name: str) -> TeachingAction:
        i = min(self._skeleton_index, len(_SKELETON_PROMPTS) - 1)
        prompt = _SKELETON_PROMPTS[i]
        content = f"现在自己重构【{name}】的知识骨架。引导 {i + 1}/4：{prompt}"
        return TeachingAction(
            type="request_explanation",
            content=content,
            estimated_duration_min=2,
            metadata={"skeleton_part": _SKELETON_PARTS[i]},
        )

    def _review_action(self, name: str) -> TeachingAction:
        d = self.difficulty_multiplier
        if d <= 0.7:
            kind = "直接套用定义/公式的基础题"
        elif d >= 1.3:
            kind = "需要多步推理 + 概念联系的挑战题"
        else:
            kind = "需要两步推理的标准题"
        return TeachingAction(
            type="give_exercise",
            content=f"当堂验证【{name}】：做一道{kind}，检验你刚建立的骨架。",
            estimated_duration_min=5,
            metadata={"difficulty_multiplier": d},
        )

    # ------------------------------------------------------------------ #
    # 内容生成辅助（无 LLM 时的结构化模板；接入 LLM 后可在此替换）
    # ------------------------------------------------------------------ #

    def _atom_question(self, name: str, index: int) -> str:
        templates = [
            f"{name}解决什么问题？",
            f"{name}的核心符号/记法怎么读，各部分代表什么？",
            f"运用{name}时，关键的前提或约定是什么？",
            f"{name}和它最接近的概念，本质区别是什么？",
            f"{name}最典型的一个应用场景是什么？",
        ]
        if index < len(templates):
            return templates[index]
        return f"关于{name}的第 {index + 1} 个关键点，用一句话说清楚。"

    def _misconception(self, t, index: int) -> str:
        known = list(getattr(t, "common_misconceptions", []) or [])
        if index < len(known):
            return known[index]
        name = t.names[0]
        generics = [
            f"{name}在任何情况下都成立，没有前提条件。",
            f"{name}和它的近义概念可以混用。",
            f"记住{name}的公式就等于理解了它。",
            f"{name}只有一种应用方式。",
        ]
        return generics[(index - len(known)) % len(generics)]

    # ------------------------------------------------------------------ #
    # transition
    # ------------------------------------------------------------------ #

    def advance_event(self) -> str | None:
        # GOAL 是纯讲解（说明学完能做什么），由 goal_understood 推进；
        # REDUCE/COMPLEMENT/RECONSTRUCT/REVIEW 都等学生作答（走 respond）
        return "goal_understood" if self.state == "GOAL" else None

    def transition(self, *, event: str, payload: dict[str, Any]) -> None:
        payload = payload or {}

        if self.state == "GOAL" and event == "goal_understood":
            self.state = "REDUCE"
            self._atom_index = 0
            self.attempt_count = 0
            return

        if self.state == "REDUCE" and event == "answered":
            self._reduce_answered(payload)
            return

        if self.state == "COMPLEMENT" and event == "answered":
            self._complement_answered(payload)
            return

        if self.state == "RECONSTRUCT":
            if event == "reconstructed":
                self.state = "REVIEW"
                self.attempt_count = 0
                return
            if event == "answered":
                self._reconstruct_answered(payload)
                return

        if self.state == "REVIEW" and event == "answered":
            self._review_answered(payload)
            return

        if self.state == "NEXT" and event in ("next", "start_next_concept"):
            self.state = "IDLE"
            return

        # 未匹配事件 → no-op（宽容语义，与 ReductionStrategy 一致）

    def _reduce_answered(self, payload: dict[str, Any]) -> None:
        corr = payload.get("correctness", "incorrect")
        if corr == "correct":
            self._atom_index += 1
            self.attempt_count = 0
        elif corr == "partial":
            self.weak_atoms.add(self._atom_index)
            self._atom_index += 1
            self.attempt_count = 0
        else:  # incorrect — 不推进，重新问
            self.attempt_count += 1
            if self.attempt_count >= self.max_attempts:
                self.state = "FLAG_DIFFICULT"
            return
        if self._atom_index >= self.sub_step_count:
            self.state = "COMPLEMENT"
            self._error_index = 0
            self.attempt_count = 0

    def _complement_answered(self, payload: dict[str, Any]) -> None:
        # 补集教学：答对答错都推进（答错时调用方应已展示错因解析）
        self._error_index += 1
        if self._error_index >= self.error_count:
            self.state = "RECONSTRUCT"
            self._skeleton_index = 0
            self.attempt_count = 0

    def _reconstruct_answered(self, payload: dict[str, Any]) -> None:
        # 记录学生对当前骨架部分的回答
        part = _SKELETON_PARTS[min(self._skeleton_index, len(_SKELETON_PARTS) - 1)]
        answer = payload.get("answer") or payload.get("text") or ""
        if answer:
            self.skeleton[part] = answer
        self._skeleton_index += 1
        if self._skeleton_index >= len(_SKELETON_PARTS):
            self.state = "REVIEW"
            self.attempt_count = 0

    def _review_answered(self, payload: dict[str, Any]) -> None:
        corr = payload.get("correctness", "incorrect")
        if corr == "correct":
            self.state = "NEXT"
            self.attempt_count = 0
        else:
            # 验证失败：回到 RECONSTRUCT 修正骨架；累计失败触发 FLAG_DIFFICULT。
            # 用专用计数器，因为往返 RECONSTRUCT 不应清零这次"卡住"的尝试。
            self._review_fail_count += 1
            if self._review_fail_count >= self.max_attempts:
                self.state = "FLAG_DIFFICULT"
            else:
                self.state = "RECONSTRUCT"
                self._skeleton_index = 0
