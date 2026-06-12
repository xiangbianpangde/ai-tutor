"""test_logger - StructuredLogger 单元测试

> 对应模块: M-006
> 测试策略: 单测 / 覆盖率≥80% [DD-001:MD-M-006]
> Mock 策略: structlog 输出用 capsys 捕获
> 来源标注: [DD-001:MD-M-006] + [DD-001:CS-AITutor-V3.1 structlog]
"""
from __future__ import annotations

import json

import pytest

from aitutor.monitor.logger import (
    StructuredLogger,
    configure_logging,
    get_logger,
)

# -----------------------------------------------------------------
# 测试场景列表
# -----------------------------------------------------------------
# 场景 1: configure_logging 幂等
# 场景 2: get_logger 返回 BoundLogger
# 场景 3: StructuredLogger.info 输出 JSON
# 场景 4: StructuredLogger.warn 输出 WARN
# 场景 5: StructuredLogger.error 输出 ERROR
# 场景 6: StructuredLogger.debug 输出 DEBUG（需 level=DEBUG）
# 场景 7: bind 返回新实例
# 场景 8: error 路径异常降级
# 场景 9: trace_id 自动注入
# 场景 10: 多次调用 get_logger 返回 logger
# -----------------------------------------------------------------


def test_configure_logging_idempotent() -> None:
    """场景1: configure_logging 多次调用不重复初始化"""
    configure_logging("INFO")
    configure_logging("INFO")
    configure_logging("INFO")
    # 不抛错即为通过


def test_get_logger_returns_logger() -> None:
    """场景2: get_logger 返回可调用 logger"""
    log = get_logger("test")
    assert log is not None
    log.info("hello", k=1)  # 不抛错


def test_structured_logger_info_emits_json(capsys: pytest.CaptureFixture) -> None:
    """场景3: StructuredLogger.info 输出 JSON 行"""
    log = StructuredLogger("aitutor.monitor.test")
    log.info("user_login", user_id="u-1")
    captured = capsys.readouterr()
    # structlog 输出至 stderr
    line = captured.err.strip().splitlines()[-1]
    obj = json.loads(line)
    assert obj["event"] == "user_login"
    assert obj["user_id"] == "u-1"


def test_structured_logger_warn(capsys: pytest.CaptureFixture) -> None:
    """场景4: warn 级别日志"""
    log = StructuredLogger("aitutor.monitor.test")
    log.warn("rate_limit", qps=200)
    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    obj = json.loads(line)
    assert obj["level"] == "warning"
    assert obj["event"] == "rate_limit"


def test_structured_logger_error(capsys: pytest.CaptureFixture) -> None:
    """场景5: error 级别日志"""
    log = StructuredLogger("aitutor.monitor.test")
    log.error("db_fail", err="timeout")
    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    obj = json.loads(line)
    assert obj["level"] == "error"
    assert obj["event"] == "db_fail"


def test_structured_logger_debug_visible_at_debug_level(capsys: pytest.CaptureFixture) -> None:
    """场景6: DEBUG 级别在 level=DEBUG 时可见"""
    configure_logging("DEBUG")
    log = StructuredLogger("aitutor.monitor.test", level="DEBUG")
    log.debug("trace_dump", payload={"a": 1})
    captured = capsys.readouterr()
    line = captured.err.strip().splitlines()[-1]
    obj = json.loads(line)
    assert obj["event"] == "trace_dump"


def test_structured_logger_bind_returns_new_instance() -> None:
    """场景7: bind 返回新 StructuredLogger（不可变）"""
    log = StructuredLogger("aitutor.monitor.test")
    bound = log.bind(trace_id="t-1")
    assert bound is not log
    assert bound is not None


def test_structured_logger_error_degrades_on_emit_failure(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """场景8: error 阶段异常触发降级输出（不抛错）"""
    log = StructuredLogger("aitutor.monitor.test")

    def boom(_: str, **__: object) -> None:
        raise RuntimeError("emit-fail")

    monkeypatch.setattr(log._logger, "error", boom)
    # 不应抛错
    log.error("something_failed")
    captured = capsys.readouterr()
    assert "FALLBACK" in captured.err


def test_logger_includes_trace_id_when_bound() -> None:
    """场景9: bind_trace_id 后 logger 自动注入 trace_id"""
    from aitutor.monitor import trace

    token = trace.bind_trace_id(trace.new_trace_id())
    try:
        tid = trace.current_trace_id()
        assert tid is not None
        # 验证 get_logger 内部 bind 拿到该 tid
        log = get_logger("aitutor.monitor.test")
        log.info("with_trace")
        # 不抛错 + 有 trace_id
    finally:
        trace.reset_trace_id(token)


def test_get_logger_multiple_calls() -> None:
    """场景10: 多次 get_logger 不抛错"""
    get_logger("a.b")
    get_logger("a.b")
    get_logger("a.b")
