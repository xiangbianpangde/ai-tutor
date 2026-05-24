"""FlowSignals 提取契约测试。

接口:
    compute_flow_signals(history: list[TurnRecord]) → FlowSignals

TurnRecord = {answer, correctness, timestamp, was_self_corrected, has_initiative_marker}

启发式（不需要 LLM）:
- answer_length_growth: len(latest) > 1.3 * avg(prev 4)
- depth_increasing: 当前含因果/对比词（因为/所以/对比/原因/导致）
- initiative_taking: 当前问句含"我能/我想/能不能让我"或主动提下一步
- hesitation_decreasing: 当前不含"嗯/可能/不确定/也许"，但前几轮含
- inter_turn_speed_up: 当前 turn 间隔 < 0.8 * 历史均值
- self_correction_quality: 当前 was_self_corrected=True 且 correctness=correct
- withdrawal_pattern: 连续 3 轮 answer 长度 ≤ 5
- help_seeking_spike: 最近 2 轮含"怎么办/什么意思/不懂"
- answer_regression: 最近 2 轮 correctness 都 incorrect 而之前都 correct
- emotional_flatness: 最近 5 轮都不含好奇标记（？/啊/哦/我觉得）
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest


def _turn(answer="x", correctness="correct", at=None,
          was_self_corrected=False, has_initiative_marker=False):
    return {
        "answer": answer,
        "correctness": correctness,
        "timestamp": at or datetime.utcnow(),
        "was_self_corrected": was_self_corrected,
        "has_initiative_marker": has_initiative_marker,
    }


def test_empty_history_returns_default_signals() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    sigs = compute_flow_signals(history=[])
    # 所有信号都 False
    assert not sigs.answer_length_growth
    assert not sigs.initiative_taking
    assert not sigs.withdrawal_pattern


def test_answer_length_growth_detected() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(answer="a"),                       # 1
        _turn(answer="ab"),                      # 2
        _turn(answer="abc"),                     # 3
        _turn(answer="abcd"),                    # 4
        _turn(answer="a much longer answer here"),  # 当前
    ]
    s = compute_flow_signals(history=hist)
    assert s.answer_length_growth is True


def test_depth_increasing_via_causal_words() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(answer="x"),
        _turn(answer="x"),
        _turn(answer="因为 X 所以 Y，原因是 ..."),
    ]
    assert compute_flow_signals(history=hist).depth_increasing is True


def test_initiative_via_markers() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(answer="一般回答"),
        _turn(answer="我想试试更难的题目可以吗？"),
    ]
    assert compute_flow_signals(history=hist).initiative_taking is True

    # 显式 has_initiative_marker 也算
    hist2 = [_turn(answer="x", has_initiative_marker=True)]
    assert compute_flow_signals(history=hist2).initiative_taking is True


def test_hesitation_decreasing() -> None:
    """前几轮有犹豫词，当前没有 → True。"""
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(answer="嗯...可能是这样"),
        _turn(answer="也许 X 吧，不确定"),
        _turn(answer="X 是 Y 的子集，且 Z 成立"),  # 干脆利落
    ]
    assert compute_flow_signals(history=hist).hesitation_decreasing is True


def test_inter_turn_speed_up() -> None:
    """当前 turn 间隔 < 0.8 * 历史均值。"""
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    base = datetime.utcnow()
    hist = [
        _turn(at=base + timedelta(seconds=0)),
        _turn(at=base + timedelta(seconds=30)),
        _turn(at=base + timedelta(seconds=60)),
        _turn(at=base + timedelta(seconds=90)),
        _turn(at=base + timedelta(seconds=95)),  # 当前 5s 后回答 → 快了
    ]
    assert compute_flow_signals(history=hist).inter_turn_speed_up is True


def test_self_correction_quality() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(),
        _turn(answer="等一下，我重新想想：应该是 Y", correctness="correct", was_self_corrected=True),
    ]
    assert compute_flow_signals(history=hist).self_correction_quality is True


def test_withdrawal_pattern_three_short_answers() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(answer="一般回答"),
        _turn(answer="嗯"),
        _turn(answer="不会"),
        _turn(answer="..."),
    ]
    assert compute_flow_signals(history=hist).withdrawal_pattern is True


def test_help_seeking_spike() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(answer="可以"),
        _turn(answer="这个怎么办？"),
        _turn(answer="什么意思？我不懂"),
    ]
    assert compute_flow_signals(history=hist).help_seeking_spike is True


def test_answer_regression_two_recent_incorrect() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(correctness="correct"),
        _turn(correctness="correct"),
        _turn(correctness="incorrect"),
        _turn(correctness="incorrect"),
    ]
    assert compute_flow_signals(history=hist).answer_regression is True


def test_emotional_flatness_no_markers_in_last_5() -> None:
    from servers.tutoring_mcp.flow_signals import compute_flow_signals

    hist = [
        _turn(answer="X 等于 Y"),
        _turn(answer="A is B"),
        _turn(answer="无"),
        _turn(answer="知道了"),
        _turn(answer="OK"),
    ]
    assert compute_flow_signals(history=hist).emotional_flatness is True

    # 反例：含问号或感叹
    hist2 = hist[:-1] + [_turn(answer="哦？这个有意思！为什么呢？")]
    assert compute_flow_signals(history=hist2).emotional_flatness is False
