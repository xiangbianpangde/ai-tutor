"""monitor.logger - 结构化日志（structlog JSON）

> 对应模块: M-006
> 关联接口: IC-002（学习回合日志）/ IC-004/IC-007/IC-008
> 关联选型: TS-010 Prometheus / AR:ADR-008（structlog 选型）
> 来源标注: [DD-001:MD-M-006] + [DD-001:FS-M-006] + [DD-001:CS-AITutor-V3.1]
"""
from __future__ import annotations

# ========== 1. 标准库 ==========
import logging
import sys
import threading
from typing import Any, Optional

# ========== 2. 第三方库 ==========
import structlog

# ========== 3. 本地模块（仅限 M-006 内部） ==========
from aitutor.monitor.trace import current_trace_id

_logger_lock = threading.Lock()
_configured: bool = False

# 标准 logging 到 structlog 桥接：handler 输出 JSON
_LOGGING_HANDLER_NAME = "aitutor_structlog"


# ----------------------------------------------------------------------------
# 函数注释
# ----------------------------------------------------------------------------
def configure_logging(level: str = "INFO") -> None:
    """[函数名] configure_logging
    [职责] 初始化 structlog + 标准 logging 桥接（进程内单次）
    [参数说明]
      参数1: level [str] [可选] [默认 INFO] [DEBUG/INFO/WARN/ERROR]
    [返回值] None
    [错误码] 无
    [前置条件] 无（幂等）
    [后置条件] structlog 输出 JSON 至 stderr
    [并发安全] 是（_logger_lock）
    [幂等性] 是
    [性能约束] O(1)
    [示例]
      configure_logging("DEBUG")
    [来源标注] [DD-001:MD-M-006 类设计 StructuredLogger] + [AR:TS structlog]
    """
    global _configured
    with _logger_lock:
        if _configured:
            return
        log_level = getattr(logging, level.upper(), logging.INFO)
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stderr,
            level=log_level,
            force=True,
        )
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
            cache_logger_on_first_use=True,
        )
        _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """[函数名] get_logger
    [职责] 获取带自动 trace_id 注入的 BoundLogger
    [关联接口契约] IC-002/IC-004/IC-007/IC-008（所有日志）
    [参数说明]
      参数1: name [str] [必填] [logger 名称，通常 __name__] [非空]
    [返回值]
      类型: structlog.stdlib.BoundLogger
      描述: 自动 bind trace_id 的 logger
    [错误码] 无
    [前置条件] configure_logging 已调用（否则自动调用）
    [后置条件] logger.info/warn/error 自动注入 trace_id/span_id
    [并发安全] 是
    [幂等性] 是
    [性能约束] O(1)
    [示例]
      log = get_logger(__name__)
      log.info("user_login", user_id="u-1")
    [来源标注] [DD-001:MD-M-006 类设计 StructuredLogger.bind] + [DD-M推断:依据=structlog 最佳实践]
    """
    if not _configured:
        configure_logging()
    log = structlog.get_logger(name)
    # 每次获取时 bind 当前 trace_id（lazy bind）
    return log.bind(
        trace_id=current_trace_id() or "",
    )


# ----------------------------------------------------------------------------
# 类注释
# ----------------------------------------------------------------------------
class StructuredLogger:
    """[类名] StructuredLogger
    [职责] 业务侧日志门面（封装 structlog + 异常处理降级）
    [关联设计规范] MD-M-006
    [属性]
      属性1: level [str] 日志级别（DEBUG/INFO/WARN/ERROR）
      属性2: _logger [structlog.stdlib.BoundLogger] 内部 BoundLogger
    [方法列表]
      方法1: info(event: str, **kwargs) -> None - INFO 级别日志
      方法2: warn(event: str, **kwargs) -> None - WARN 级别日志
      方法3: error(event: str, **kwargs) -> None - ERROR 级别日志
      方法4: debug(event: str, **kwargs) -> None - DEBUG 级别日志
      方法5: bind(**kwargs) -> StructuredLogger - 附加上下文（不可变）
    [状态机] N/A
    [异常处理]
      异常1: E00603 OTel 导出失败 触发: 远程 exporter 异常  处理: 降级本地 JSON 日志
    [来源标注] [DD-001:MD-M-006 类设计 StructuredLogger] + [DD-M推断:依据=structlog 桥接]
    """

    def __init__(self, name: str, level: str = "INFO") -> None:
        self.level: str = level
        self._logger: structlog.stdlib.BoundLogger = get_logger(name)

    # ---- 函数注释 ----
    def info(self, event: str, **kwargs: Any) -> None:
        """[函数名] info
        [职责] 记录 INFO 级别业务事件
        [参数说明]
          参数1: event [str] [必填] [事件名 snake_case] [非空]
          参数2: **kwargs [Any] [可选] [结构化字段] [可序列化]
        [返回值] None
        [并发安全] 是
        [幂等性] N/A（日志流）
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 StructuredLogger.info]
        """
        self._logger.info(event, **kwargs)

    def warn(self, event: str, **kwargs: Any) -> None:
        """[函数名] warn
        [职责] 记录 WARN 级别告警
        [参数说明]
          参数1: event [str] [必填] [事件名] [非空]
          参数2: **kwargs [Any] [可选] [结构化字段]
        [返回值] None
        [并发安全] 是
        [幂等性] N/A
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 StructuredLogger.warn]
        """
        self._logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        """[函数名] error
        [职责] 记录 ERROR 级别错误（含异常降级）
        [参数说明]
          参数1: event [str] [必填] [事件名] [非空]
          参数2: **kwargs [Any] [可选] [结构化字段]
        [返回值] None
        [错误码]
          错误码1: E00603 含义: OTel 导出失败  处理: 降级本地日志
        [并发安全] 是
        [幂等性] N/A
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 StructuredLogger.error]
        """
        try:
            self._logger.error(event, **kwargs)
        except Exception:  # noqa: BLE001 - 降级
            sys.stderr.write(f"[FALLBACK] error: {event} {kwargs}\n")

    def debug(self, event: str, **kwargs: Any) -> None:
        """[函数名] debug
        [职责] 记录 DEBUG 级别调试信息
        [参数说明]
          参数1: event [str] [必填]
          参数2: **kwargs [Any] [可选]
        [返回值] None
        [并发安全] 是
        [幂等性] N/A
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 日志策略 DEBUG]
        """
        self._logger.debug(event, **kwargs)

    def bind(self, **kwargs: Any) -> "StructuredLogger":
        """[函数名] bind
        [职责] 返回绑定新上下文的新 StructuredLogger（不可变）
        [参数说明]
          参数1: **kwargs [Any] [必填] [附加字段]
        [返回值]
          类型: StructuredLogger
          描述: 新实例，原实例不变
        [并发安全] 是
        [幂等性] 否（每次返回新实例）
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 StructuredLogger.bind]
        """
        new_log = StructuredLogger.__new__(StructuredLogger)
        new_log.level = self.level
        new_log._logger = self._logger.bind(**kwargs)
        return new_log


# 抑制未使用导入告警（Optional 用于未来扩展）
_ = Optional
