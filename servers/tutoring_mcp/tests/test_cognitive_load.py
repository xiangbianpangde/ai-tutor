"""认知负荷在线估计 (P1 #6) 测试。

estimate_load：确定性加权公式（内在难度 + 表现 + 连续受挫 + 工作记忆压力）+ EMA 平滑。
此前 ctx.meta.current_cognitive_load 恒 0.0，导致 strategy_selector 的负荷分支和
flow_regulator 的负荷修正永不触发。
"""
from __future__ import annotations

import pytest

from servers.tutoring_mcp.cognitive_load import estimate_load


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
