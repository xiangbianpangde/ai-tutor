"""系统主动发起的两类教学动作工厂。

与策略状态机产出的动作不同，这两类由引擎在 respond 中按学情条件主动插入：

- show_counter_example: 学生犯「概念混淆 / 过度泛化」类错误，且该概念带有反例时，
  用反例点明边界（"看起来像 X，其实不是，因为……"）。
- pace_feedback: 认知负荷刚跨过过载阈值（上升沿）时，主动告知"我们放慢一点"，
  把节奏调整这件事说给学生听（PGFGA：让学生感到被看见，而非被默默降速）。

break_suggestion 由 gain_loop_monitor.repair 产出，不在此处。
"""
from __future__ import annotations

from typing import Literal

from shared.schemas import Concept, TeachingAction

# 适合用反例澄清边界的错误类型（看似属于该概念，实则越界）。
COUNTER_EXAMPLE_ERROR_TYPES: frozenset[str] = frozenset({
    "concept_confusion", "overgeneralization",
})


def make_show_counter_example(concept: Concept) -> TeachingAction | None:
    """用概念的第一个反例构造 show_counter_example 动作；无反例则返回 None。"""
    if not concept.counter_examples:
        return None
    name = concept.names[0]
    ce = concept.counter_examples[0]
    content = (
        f"看一个反例：{ce.text}\n"
        f"它乍看像是「{name}」，但其实不是——边界正落在这里，"
        f"这也是最容易混淆的地方。"
    )
    return TeachingAction(
        type="show_counter_example",
        content=content,
        estimated_duration_min=2,
        metadata={"concept_id": concept.id, "trigger": "misconception"},
    )


_PACE_FEEDBACK_TEMPLATES: dict[str, str] = {
    "slow_down": (
        "我注意到这一段信息量上来了——我们放慢一点，把它夯实了再走。"
        "不急，按你的节奏来。"
    ),
    "speed_up": (
        "你这几步走得很稳，我们可以稍微加快一点，挑战点更高的。"
    ),
}


def make_pace_feedback(
    *, direction: Literal["slow_down", "speed_up"], reason: str = ""
) -> TeachingAction:
    """构造 pace_feedback 动作：把节奏调整明确说给学生听。"""
    content = _PACE_FEEDBACK_TEMPLATES.get(direction, _PACE_FEEDBACK_TEMPLATES["slow_down"])
    return TeachingAction(
        type="pace_feedback",
        content=content,
        estimated_duration_min=1,
        metadata={"direction": direction, "reason": reason, "pgfga": "pace_transparency"},
    )


def make_break_suggestion(*, streak_min: float) -> TeachingAction:
    """构造连续学习时长触发的休息建议（#10）。

    与 gain_loop_monitor.repair 的回路修复不同：这里按墙钟连续时长主动触发，
    不需要学生答错任何题。metadata.trigger 用于引擎识别来源并记录提醒时间。
    """
    return TeachingAction(
        type="break_suggestion",
        content=(
            f"你已经连续学了约 {round(streak_min)} 分钟——建议休息 5–10 分钟再继续。"
            f"间隔休息比连续硬撑记得更牢，回来后我们从这里接着走。"
        ),
        estimated_duration_min=1,
        metadata={"trigger": "study_streak", "streak_min": round(streak_min, 1)},
    )
