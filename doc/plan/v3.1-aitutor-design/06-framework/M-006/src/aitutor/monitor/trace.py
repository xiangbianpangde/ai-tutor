"""monitor.trace - trace_id 生成与传播（ContextVar + 32hex）

> 对应模块: M-006
> 关联接口: IC-002（学习回合 trace_id 必填）/ IC-004（数据入库 trace_id 必填）/ IC-007（长期记忆 trace_id 必填）/ IC-008（WS 推送 trace_id 必填）
> 关联选型: TS-009 OpenTelemetry
> 来源标注: [DD-001:MD-M-006] + [DD-001:FS-M-006] + [AR:TS-009] + [AR:SEC-010]
"""
from __future__ import annotations

# ========== 1. 标准库 ==========
import contextlib
import contextvars
import re
import secrets
import time
from contextvars import ContextVar
from typing import Iterator, Optional

# ========== 2. 第三方库 ==========
# （本文件不依赖第三方库）

# ========== 3. 本地模块（仅限 M-006 内部） ==========
from aitutor.monitor.logger import get_logger

_logger = get_logger(__name__)

# ----------------------------------------------------------------------------
# 常量（CS 命名规范：UPPER_SNAKE_CASE）
# ----------------------------------------------------------------------------
_TRACE_ID_LEN: int = 32
_SPAN_ID_LEN: int = 16
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")

# 进程级 ContextVar：跨协程传递 trace_id
_trace_id_var: ContextVar[Optional[str]] = ContextVar("aitutor_trace_id", default=None)
_span_id_var: ContextVar[Optional[str]] = ContextVar("aitutor_span_id", default=None)


# ----------------------------------------------------------------------------
# 函数注释
# ----------------------------------------------------------------------------
def new_trace_id() -> str:
    """[函数名] new_trace_id
    [职责] 生成 32hex 全局唯一追踪 ID
    [关联接口契约] IC-002/IC-004/IC-007/IC-008
    [参数说明] 无
    [返回值]
      类型: str
      描述: 32 位小写 hex 字符串
      特殊值: 无
    [错误码]
      错误码1: 无（secrets 永不抛错）
    [前置条件] 无
    [后置条件] 与进程内任何已有 trace_id 冲突概率 < 2^-128
    [并发安全] 是
    [幂等性] 否（每次返回不同 ID）
    [性能约束] O(1)
    [示例]
      tid = new_trace_id()  # -> "a3f4...32chars"
    [来源标注] [DD-001:MD-M-006 函数签名 new_trace_id] + [AR:TS-009 trace_id 规范]
    """
    # secrets.token_hex(16) -> 32hex 强随机
    return secrets.token_hex(_TRACE_ID_LEN // 2)


def new_span_id() -> str:
    """[函数名] new_span_id
    [职责] 生成 16hex span_id
    [参数说明] 无
    [返回值] 类型: str 描述: 16 位小写 hex
    [并发安全] 是
    [幂等性] 否
    [性能约束] O(1)
    [来源标注] [DD-M推断:依据=OTel span_id 16hex 规范]
    """
    return secrets.token_hex(_SPAN_ID_LEN // 2)


def bind_trace_id(trace_id: str) -> contextvars.Token:
    """[函数名] bind_trace_id
    [职责] 将 trace_id 绑定到当前 ContextVar（返回 Token 用于 reset）
    [关联接口契约] IC-002/IC-004/IC-007/IC-008
    [参数说明]
      参数1: trace_id [str] [必填] [32hex 字符串] [长度=32 且仅 hex]
    [返回值]
      类型: contextvars.Token
      描述: 用于 reset_trace_id(token) 还原
    [错误码]
      错误码1: E00601 含义: trace_id 格式非法 触发: 不符合 32hex  处理: 自动生成新 ID + WARN
    [前置条件] 无
    [后置条件] 当前协程的 current_trace_id() == trace_id
    [并发安全] 是（ContextVar 协程隔离）
    [幂等性] 否（多次绑定会覆盖）
    [性能约束] O(1)
    [示例]
      token = bind_trace_id(tid)
      try: ...
      finally: reset_trace_id(token)
    [来源标注] [DD-001:MD-M-006 函数签名 bind_trace_id] + [DD-M推断:依据=ContextVar 最佳实践]
    """
    if not _is_valid_trace_id(trace_id):
        _logger.warn(
            "bind_trace_id_invalid",
            given_len=len(trace_id) if trace_id else 0,
        )
        trace_id = new_trace_id()
    return _trace_id_var.set(trace_id)


def reset_trace_id(token: contextvars.Token) -> None:
    """[函数名] reset_trace_id
    [职责] 还原 ContextVar 到 bind 之前
    [参数说明]
      参数1: token [contextvars.Token] [必填] [bind_trace_id 返回值]
    [返回值] None
    [并发安全] 是
    [幂等性] 否
    [来源标注] [DD-M推断:依据=ContextVar reset 模式]
    """
    _trace_id_var.reset(token)


def current_trace_id() -> Optional[str]:
    """[函数名] current_trace_id
    [职责] 获取当前协程的 trace_id
    [参数说明] 无
    [返回值]
      类型: Optional[str]
      描述: 当前 ContextVar 中的 trace_id；未绑定返回 None
    [错误码] 无
    [前置条件] 无
    [后置条件] 无
    [并发安全] 是
    [幂等性] 是
    [性能约束] O(1)
    [来源标注] [DD-M推断:依据=ContextVar get 模式]
    """
    return _trace_id_var.get()


@contextlib.contextmanager
def trace_scope(trace_id: Optional[str] = None) -> Iterator[str]:
    """[函数名] trace_scope
    [职责] 上下文管理器：with 块内自动绑定 / 还原 trace_id
    [参数说明]
      参数1: trace_id [Optional[str]] [可选] [32hex；None 时自动生成] [长度=32]
    [返回值]
      类型: Iterator[str]
      描述: yield 当前生效的 trace_id
    [错误码]
      错误码1: E00601 含义: 非法 trace_id  处理: 自动生成新 ID + WARN
    [前置条件] 无
    [后置条件] with 块结束自动 reset
    [并发安全] 是
    [幂等性] 否
    [性能约束] O(1)
    [示例]
      with trace_scope() as tid:
          publish_event("foo", {})  # 事件带 tid
    [来源标注] [DD-M推断:依据=ContextVar contextmanager 模式]
    """
    tid = trace_id or new_trace_id()
    token = bind_trace_id(tid)
    try:
        yield tid
    finally:
        reset_trace_id(token)


def _is_valid_trace_id(trace_id: str) -> bool:
    """[函数名] _is_valid_trace_id
    [职责] 校验 trace_id 格式（32hex）
    [参数说明]
      参数1: trace_id [str] [必填] [待校验]
    [返回值] 类型: bool 描述: True 合法；False 非法
    [并发安全] 是
    [幂等性] 是
    [性能约束] O(N) N=字符串长度
    [来源标注] [DD-M推断:依据=32hex 格式]
    """
    if not isinstance(trace_id, str):
        return False
    if len(trace_id) != _TRACE_ID_LEN:
        return False
    return bool(_HEX_RE.match(trace_id))


# ---- 类型导出 ----
__all__ = [
    "new_trace_id",
    "new_span_id",
    "bind_trace_id",
    "reset_trace_id",
    "current_trace_id",
    "trace_scope",
    "TraceContext",
]


# ----------------------------------------------------------------------------
# 类注释
# ----------------------------------------------------------------------------
class TraceContext:
    """[类名] TraceContext
    [职责] trace/span 上下文封装（start / end / inject / extract）
    [关联设计规范] MD-M-006
    [属性]
      属性1: trace_id [str] 32hex 追踪 ID
      属性2: span_id [str] 16hex 跨度 ID
      属性3: parent_span_id [Optional[str]] 父 span_id
      属性4: start_ts_ms [int] 起始时间戳（毫秒）
    [方法列表]
      方法1: start() -> None - 启动 span 并记录开始时间
      方法2: end() -> int - 结束 span 并返回耗时（毫秒）
      方法3: inject() -> dict - 序列化为跨进程头
      方法4: extract(headers: dict) -> TraceContext - 从头解析（classmethod）
    [状态机] NEW -> STARTED -> ENDED
    [异常处理]
      异常1: 无显式异常，非法 trace_id 在 bind 阶段处理
    [来源标注] [DD-001:MD-M-006 类设计 TraceContext] + [DD-M推断:依据=OTel 语义]
    """

    def __init__(
        self,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
    ) -> None:
        self.trace_id: str = trace_id or new_trace_id()
        self.span_id: str = span_id or new_span_id()
        self.parent_span_id: str | None = parent_span_id
        self.start_ts_ms: int = 0
        self.end_ts_ms: int = 0

    def start(self) -> None:
        """[函数名] start
        [职责] 标记 span 开始（记录 start_ts_ms）
        [参数说明] 无
        [返回值] None
        [并发安全] 是
        [幂等性] 否（覆盖 start_ts_ms）
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 方法 start]
        """
        self.start_ts_ms = int(time.time() * 1000)

    def end(self) -> int:
        """[函数名] end
        [职责] 标记 span 结束并返回耗时
        [参数说明] 无
        [返回值]
          类型: int
          描述: 耗时（毫秒）
          特殊值: 若未 start 则返回 0
        [并发安全] 是
        [幂等性] 否
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 方法 end]
        """
        self.end_ts_ms = int(time.time() * 1000)
        if self.start_ts_ms == 0:
            return 0
        return self.end_ts_ms - self.start_ts_ms

    def inject(self) -> dict[str, str]:
        """[函数名] inject
        [职责] 序列化为跨进程传播头（dict）
        [参数说明] 无
        [返回值] 类型: dict 描述: 包含 trace_id/span_id/parent_span_id
        [并发安全] 是
        [幂等性] 是
        [性能约束] O(1)
        [示例]
          headers = ctx.inject()
          # {"x-aitutor-trace-id": "...", "x-aitutor-span-id": "..."}
        [来源标注] [DD-001:MD-M-006 方法 inject] + [DD-M推断:依据=W3C traceparent 简化]
        """
        return {
            "x-aitutor-trace-id": self.trace_id,
            "x-aitutor-span-id": self.span_id,
            "x-aitutor-parent-span-id": self.parent_span_id or "",
        }

    @classmethod
    def extract(cls, headers: dict[str, str]) -> "TraceContext":
        """[函数名] extract
        [职责] 从传播头解析出 TraceContext
        [关联接口契约] IC-002（学习回合跨进程传播）
        [参数说明]
          参数1: headers [dict] [必填] [跨进程头] [键名小写]
        [返回值]
          类型: TraceContext
          描述: 解析得到的上下文
          特殊值: 头缺失时自动生成新 trace_id
        [错误码]
          错误码1: E00601 含义: 头格式非法  处理: 降级生成新 trace_id
        [前置条件] 无
        [后置条件] 拿到合法 TraceContext
        [并发安全] 是
        [幂等性] 是
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 方法 extract] + [DD-M推断:依据=extract 规范]
        """
        normalized = {k.lower(): v for k, v in headers.items()}
        trace_id = normalized.get("x-aitutor-trace-id")
        if not _is_valid_trace_id(trace_id or ""):
            trace_id = new_trace_id()
        return cls(
            trace_id=trace_id,
            span_id=normalized.get("x-aitutor-span-id") or new_span_id(),
            parent_span_id=normalized.get("x-aitutor-parent-span-id") or None,
        )


# 抑制 time 导入告警（用于时间戳）
_ = time
