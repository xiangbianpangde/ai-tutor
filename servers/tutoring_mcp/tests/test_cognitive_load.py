"""认知负荷在线估计 (P1 #6) 测试。

estimate_load：确定性加权公式（内在难度 + 表现 + 连续受挫 + 工作记忆压力）+ EMA 平滑。
此前 ctx.meta.current_cognitive_load 恒 0.0，导致 strategy_selector 的负荷分支和
flow_regulator 的负荷修正永不触发。
"""
from __future__ import annotations

import pytest

from servers.tutoring_mcp.cognitive_load import compute_text_signals, estimate_load


def _load(**kw):
    base = dict(
        intrinsic=0.3, recent_accuracy=0.8, struggle_count=0,
        working_memory_span=5, prereq_count=1, prev_load=0.0,
    )
    base.update(kw)
    return estimate_load(**base)


def test_in_range():
    for acc in (0.0, 0.5, 1.0):
        for st in (0, 3, 10):
            v = _load(recent_accuracy=acc, struggle_count=st, intrinsic=0.9)
            assert 0.0 <= v <= 1.0


def test_higher_intrinsic_raises_load():
    assert _load(intrinsic=0.9) > _load(intrinsic=0.1)


def test_lower_accuracy_raises_load():
    assert _load(recent_accuracy=0.1) > _load(recent_accuracy=0.95)


def test_more_struggle_raises_load():
    assert _load(struggle_count=4) > _load(struggle_count=0)


def test_working_memory_pressure():
    """前置数远超工作记忆容量 → 负荷更高。"""
    assert _load(prereq_count=10, working_memory_span=3) > _load(prereq_count=1, working_memory_span=7)


def test_none_accuracy_is_neutral():
    """无答题数据时（recent_accuracy=None）按中性处理，不崩。"""
    v = _load(recent_accuracy=None)
    assert 0.0 <= v <= 1.0


def test_ema_smoothing_blends_prev():
    """有 prev_load 时做 EMA 平滑：结果在 raw 与 prev 之间，不跳变。"""
    raw = _load(intrinsic=0.9, recent_accuracy=0.1, struggle_count=4, prev_load=0.0)
    # 同样的高负荷输入，但 prev_load 很低 → 平滑后应低于纯 raw
    smoothed = _load(intrinsic=0.9, recent_accuracy=0.1, struggle_count=4, prev_load=0.05)
    assert smoothed < raw
    assert smoothed > 0.05


def test_struggling_student_can_cross_overload_threshold():
    """难概念 + 持续答错 + 多次受挫 → 负荷能升到 overload(>0.75) 区间（经几轮 EMA）。"""
    load = 0.0
    for _ in range(5):
        load = estimate_load(
            intrinsic=0.85, recent_accuracy=0.0, struggle_count=4,
            working_memory_span=4, prereq_count=6, prev_load=load,
        )
    assert load > 0.75


def test_easy_confident_student_low_load():
    load = 0.0
    for _ in range(5):
        load = estimate_load(
            intrinsic=0.15, recent_accuracy=1.0, struggle_count=0,
            working_memory_span=7, prereq_count=0, prev_load=load,
        )
    assert load < 0.3


# ----------------------- 文本信号 (1.6) ----------------------- #

def test_text_pressure_none_is_backward_compatible():
    """不传 text_pressure 与传 None/0 结果一致（向后兼容）。"""
    base = dict(intrinsic=0.5, recent_accuracy=0.5, struggle_count=1,
                working_memory_span=5, prereq_count=2)
    assert estimate_load(**base) == estimate_load(**base, text_pressure=None)
    assert estimate_load(**base) == estimate_load(**base, text_pressure=0.0)


def test_text_pressure_raises_load():
    base = dict(intrinsic=0.5, recent_accuracy=0.5, struggle_count=1,
                working_memory_span=5, prereq_count=2)
    assert estimate_load(**base, text_pressure=0.9) > estimate_load(**base, text_pressure=0.0)


def test_empty_and_single_answer_zero_signals():
    assert compute_text_signals(recent_answers=[]).text_pressure == 0.0
    s = compute_text_signals(recent_answers=["一条答案"])
    assert s.answer_length_variance == 0.0  # 单条无法算波动


def test_uniform_answers_low_variance():
    """长度一致、无求助 → 文本压力接近 0（保证既有均匀答案场景不被误抬负荷）。"""
    s = compute_text_signals(recent_answers=["答案ABCD", "答案EFGH", "答案IJKL"])
    assert s.answer_length_variance == pytest.approx(0.0, abs=0.05)
    assert s.question_rephrasing_rate == 0.0
    assert s.text_pressure == pytest.approx(0.0, abs=0.05)


def test_erratic_lengths_raise_variance():
    s = compute_text_signals(recent_answers=["对", "我觉得这个概念可能是说在某种条件下会成立但我不确定具体是怎样的", "嗯"])
    assert s.answer_length_variance > 0.4
    assert s.text_pressure > 0.2


def test_rephrasing_requests_detected():
    s = compute_text_signals(recent_answers=["能换个说法吗", "没听懂", "再讲一遍"])
    assert s.question_rephrasing_rate == pytest.approx(1.0)
    assert s.text_pressure > 0.4
