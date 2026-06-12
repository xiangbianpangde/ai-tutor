"""test_trace - trace_id / TraceContext 单元测试

> 对应模块: M-006
> 测试策略: 单测 / 覆盖率≥80% [DD-001:MD-M-006]
> Mock 策略: 无外部依赖；时间戳用真实时钟
> 来源标注: [DD-001:MD-M-006] + [DD-001:IC-002 隐式 trace_id 必填]
"""
from __future__ import annotations

import re

import pytest

from aitutor.monitor.trace import (
    TraceContext,
    bind_trace_id,
    current_trace_id,
    new_span_id,
    new_trace_id,
    reset_trace_id,
    trace_scope,
)

# -----------------------------------------------------------------
# 测试场景列表
# -----------------------------------------------------------------
# 场景 1: new_trace_id 格式合规
# 场景 2: 两次 new_trace_id 不重复
# 场景 3: bind_trace_id + current_trace_id 一致
# 场景 4: reset_trace_id 还原
# 场景 5: bind 非法格式自动生成
# 场景 6: trace_scope 自动 reset
# 场景 7: TraceContext.start / end 返回耗时
# 场景 8: TraceContext.inject / extract 往返
# 场景 9: extract 缺失头时自动生成
# 场景 10: extract 非法 trace_id 自动生成
# -----------------------------------------------------------------


_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX16 = re.compile(r"^[0-9a-f]{16}$")


def test_new_trace_id_format() -> None:
    """场景1: new_trace_id 返回 32hex 小写"""
    tid = new_trace_id()
    assert _HEX32.match(tid), f"trace_id 格式错误: {tid}"


def test_new_trace_id_unique() -> None:
    """场景2: 两次 new_trace_id 不重复（高概率）"""
    a = new_trace_id()
    b = new_trace_id()
    assert a != b


def test_bind_and_current_round_trip() -> None:
    """场景3: bind_trace_id + current_trace_id 一致"""
    tid = new_trace_id()
    token = bind_trace_id(tid)
    try:
        assert current_trace_id() == tid
    finally:
        reset_trace_id(token)


def test_reset_trace_id_restores() -> None:
    """场景4: reset_trace_id 还原 ContextVar"""
    token = bind_trace_id(new_trace_id())
    assert current_trace_id() is not None
    reset_trace_id(token)
    assert current_trace_id() is None


def test_bind_invalid_trace_id_auto_generates() -> None:
    """场景5: 非法 trace_id 触发自动生成 + WARN"""
    token = bind_trace_id("not-hex")
    try:
        tid = current_trace_id()
        assert tid is not None
        assert _HEX32.match(tid)
    finally:
        reset_trace_id(token)


def test_trace_scope_auto_resets() -> None:
    """场景6: trace_scope 退出后自动 reset"""
    assert current_trace_id() is None
    with trace_scope() as tid:
        assert current_trace_id() == tid
        assert _HEX32.match(tid)
    assert current_trace_id() is None


def test_trace_context_start_end_duration() -> None:
    """场景7: TraceContext.start + end 返回非负耗时"""
    import time

    ctx = TraceContext()
    ctx.start()
    time.sleep(0.001)
    duration = ctx.end()
    assert duration >= 0


def test_trace_context_inject_extract_round_trip() -> None:
    """场景8: TraceContext.inject → extract 往返一致"""
    ctx = TraceContext()
    headers = ctx.inject()
    assert "x-aitutor-trace-id" in headers
    restored = TraceContext.extract(headers)
    assert restored.trace_id == ctx.trace_id
    assert restored.span_id == ctx.span_id


def test_trace_context_extract_missing_header() -> None:
    """场景9: extract 缺失头时自动生成"""
    ctx = TraceContext.extract({})
    assert _HEX32.match(ctx.trace_id)
    assert _HEX16.match(ctx.span_id)


def test_trace_context_extract_invalid_trace_id() -> None:
    """场景10: extract 非法 trace_id 自动生成"""
    ctx = TraceContext.extract({"x-aitutor-trace-id": "BAD"})
    assert _HEX32.match(ctx.trace_id)


# -----------------------------------------------------------------
# new_span_id 补充测试
# -----------------------------------------------------------------


def test_new_span_id_format() -> None:
    """场景补充: new_span_id 16hex"""
    sid = new_span_id()
    assert _HEX16.match(sid)
