"""PGFGA 心流信号提取（纯函数）。

输入: 最近 N 轮 TurnRecord 字典列表（含 answer/correctness/timestamp 等）
输出: FlowSignals（10 个布尔）

启发式（不需要 LLM）；后续切片可加 LLM 语义补强。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.schemas import FlowSignals

_CAUSAL_WORDS = ("因为", "所以", "原因是", "导致", "因此", "对比", "区别是")
_INITIATIVE_WORDS = ("我能", "我想", "能不能让我", "可不可以", "我来试")
_HESITATION_WORDS = ("嗯...", "嗯…", "可能是", "也许", "不确定", "我猜")
_HELP_WORDS = ("怎么办", "什么意思", "不懂", "不会", "帮我")
_EMOTION_MARKERS = ("？", "?", "啊", "哦", "我觉得", "好奇", "为什么", "！")


def _is_short(answer: str, max_len: int = 5) -> bool:
    return len((answer or "").strip()) <= max_len


def compute_flow_signals(*, history: list[dict[str, Any]]) -> FlowSignals:
    if not history:
        return FlowSignals()
    cur = history[-1]
    cur_ans = (cur.get("answer") or "").strip()
    prev = history[:-1]

    # ---- answer_length_growth ----
    answer_length_growth = False
    if len(prev) >= 1 and cur_ans:
        prev_lens = [len((t.get("answer") or "").strip()) for t in prev[-4:]]
        avg_prev = sum(prev_lens) / max(len(prev_lens), 1)
        answer_length_growth = len(cur_ans) > 1.3 * max(avg_prev, 1)

    # ---- depth_increasing ----
    depth_increasing = any(w in cur_ans for w in _CAUSAL_WORDS)

    # ---- initiative_taking ----
    initiative_taking = (
        bool(cur.get("has_initiative_marker"))
        or any(w in cur_ans for w in _INITIATIVE_WORDS)
    )

    # ---- hesitation_decreasing ----
    hesitation_decreasing = False
    if prev:
        prev_has_hes = any(
            any(w in (t.get("answer") or "") for w in _HESITATION_WORDS)
            for t in prev
        )
        cur_has_hes = any(w in cur_ans for w in _HESITATION_WORDS)
        hesitation_decreasing = prev_has_hes and not cur_has_hes

    # ---- inter_turn_speed_up ----
    inter_turn_speed_up = False
    if len(history) >= 3:
        intervals = []
        for i in range(1, len(history)):
            a = history[i].get("timestamp")
            b = history[i - 1].get("timestamp")
            if isinstance(a, datetime) and isinstance(b, datetime):
                intervals.append((a - b).total_seconds())
        if len(intervals) >= 2:
            cur_int = intervals[-1]
            prev_avg = sum(intervals[:-1]) / len(intervals[:-1])
            if prev_avg > 0:
                inter_turn_speed_up = cur_int < 0.8 * prev_avg

    # ---- self_correction_quality ----
    self_correction_quality = (
        bool(cur.get("was_self_corrected"))
        and cur.get("correctness") == "correct"
    )

    # ---- withdrawal_pattern: 连续 3 轮极短 ----
    withdrawal_pattern = False
    if len(history) >= 3:
        last3 = history[-3:]
        withdrawal_pattern = all(_is_short(t.get("answer") or "") for t in last3)

    # ---- help_seeking_spike: 最近 2 轮含求助词 ----
    help_seeking_spike = False
    if len(history) >= 2:
        recent2 = history[-2:]
        help_count = sum(
            any(w in (t.get("answer") or "") for w in _HELP_WORDS)
            for t in recent2
        )
        help_seeking_spike = help_count >= 2

    # ---- answer_regression: 最近 2 轮 incorrect ----
    answer_regression = False
    if len(history) >= 2:
        last2 = history[-2:]
        answer_regression = all(t.get("correctness") == "incorrect" for t in last2)

    # ---- emotional_flatness: 最近 5 轮都没情绪标记 ----
    emotional_flatness = False
    if len(history) >= 5:
        last5 = history[-5:]
        emotional_flatness = all(
            not any(m in (t.get("answer") or "") for m in _EMOTION_MARKERS)
            for t in last5
        )

    return FlowSignals(
        answer_length_growth=answer_length_growth,
        depth_increasing=depth_increasing,
        initiative_taking=initiative_taking,
        hesitation_decreasing=hesitation_decreasing,
        inter_turn_speed_up=inter_turn_speed_up,
        self_correction_quality=self_correction_quality,
        withdrawal_pattern=withdrawal_pattern,
        help_seeking_spike=help_seeking_spike,
        answer_regression=answer_regression,
        emotional_flatness=emotional_flatness,
    )
