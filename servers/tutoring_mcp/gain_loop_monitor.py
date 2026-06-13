"""PGFGA 增益回路监视 + 4 种修复 action。

合同来源: ai-tutor-system-design/specs/pgfga-integration.md §5

检测优先级（先到先决）：
1. avoidance_pattern    最近 3+ 次跳过当前 / 主动放弃
2. student_withdrawal   withdrawal_pattern + emotional_flatness（答短 + 无情绪）
3. surface_responses    help_seeking_spike + withdrawal（求表面帮助）
4. emotional_flattening 仅 emotional_flatness（沉默但还在答）

修复 action 都走 NonJudgmentFirewall — PGFGA 三铁律：不否定 / 不说教 / 不评判。
"""
from __future__ import annotations

from typing import Literal

from shared.schemas import FlowSignals, GainLoopBreak, TeachingAction

GainLoopBreakType = Literal[
    "student_withdrawal", "emotional_flattening",
    "surface_responses", "avoidance_pattern",
]


def detect_break(
    *,
    signals: FlowSignals,
    recent_skipped_count: int = 0,
) -> GainLoopBreak | None:
    """返回检测到的回路断裂（按优先级）或 None。"""
    # 1. 主动放弃 — 跳过太多
    if recent_skipped_count >= 3:
        return GainLoopBreak(
            type="avoidance_pattern",
            evidence=[f"recent skipped concepts: {recent_skipped_count}"],
            repair_action_hint="reframe_topic",
        )

    # 2. 学生退场 — 退场比表面求助更紧迫（spec 优先级 #2，docstring 顶部已说明）
    # 强信号：withdrawal_pattern + emotional_flatness（答短 + 沉默）
    # 弱信号：仅 withdrawal_pattern 且没有 help_seeking（不是在求助、就是默默放弃）
    if signals.withdrawal_pattern and (
        signals.emotional_flatness or not signals.help_seeking_spike
    ):
        evidence = ["withdrawal_pattern"]
        if signals.emotional_flatness:
            evidence.append("emotional_flatness")
        return GainLoopBreak(
            type="student_withdrawal",
            evidence=evidence,
            repair_action_hint="rebuild_safety",
        )

    # 3. 表面应付 — 短答 + 频繁求助（在前面 withdrawal+emotional_flatness 之后兜）
    if signals.help_seeking_spike and signals.withdrawal_pattern:
        return GainLoopBreak(
            type="surface_responses",
            evidence=["help_seeking_spike + withdrawal_pattern"],
            repair_action_hint="lower_bar",
        )

    # 4. 情绪平 — 单一信号
    has_positive = any([
        signals.answer_length_growth, signals.depth_increasing,
        signals.initiative_taking, signals.inter_turn_speed_up,
        signals.self_correction_quality, signals.hesitation_decreasing,
    ])
    if signals.emotional_flatness and not has_positive:
        return GainLoopBreak(
            type="emotional_flattening",
            evidence=["emotional_flatness sustained, no positive markers"],
            repair_action_hint="check_in",
        )

    return None


_REPAIR_TEMPLATES: dict[str, str] = {
    "student_withdrawal": (
        "我感觉我们走得有点匆忙了。你不需要一次答对——告诉我你的想法，"
        "哪怕只是半成品也行。我们一起把它捋清楚。"
    ),
    "emotional_flattening": (
        "我注意到你今天感觉状态不太一样。要不要休息一下，"
        "或者换一种讲法？你来定节奏。"
    ),
    "surface_responses": (
        "我们一起慢下来。先把这一个概念吃透——不急，你想到什么都可以说。"
    ),
    "avoidance_pattern": (
        "这几个概念可能让你觉得有点远。我们换一个你感兴趣的切入点试试，"
        "或者从一个你最想懂的问题开始？"
    ),
}

_SAFE_DEFAULT = (
    "我们停一下。你想聊点什么？或者休息一会儿再继续？"
)


def repair(*, break_type: str) -> TeachingAction:
    """对应 break_type 生成修复 TeachingAction。

    未知 break_type → 安全默认。
    """
    content = _REPAIR_TEMPLATES.get(break_type, _SAFE_DEFAULT)
    return TeachingAction(
        type="break_suggestion",
        content=content,
        estimated_duration_min=2,
        metadata={"break_type": break_type, "pgfga": "gain_loop_repair"},
    )
