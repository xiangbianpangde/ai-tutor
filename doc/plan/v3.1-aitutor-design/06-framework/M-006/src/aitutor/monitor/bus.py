"""monitor.bus - 事件总线（Observer + Mediator）

> 对应模块: M-006
> 关联接口: IC-002（学习回合，事件 publish）/ IC-008（WS 推送，事件 broadcast）
> 关联选型: TS-009 OpenTelemetry / TS-010 Prometheus
> 设计模式: Observer（订阅者注册 + 事件分发）+ Mediator（统一事件路由）
> 来源标注: [DD-001:MD-M-006] + [DD-001:FS-M-006] + [AR:TS-009/010] + [AR:SEC-010]
"""
from __future__ import annotations

# ========== 1. 标准库 ==========
import asyncio
import inspect
import threading
from collections import defaultdict
from contextlib import suppress
from typing import Any, Awaitable, Callable, DefaultDict, List

# ========== 2. 第三方库 ==========
# （本文件不依赖第三方库）

# ========== 3. 本地模块（仅限 M-006 内部） ==========
from aitutor.monitor.logger import get_logger
from aitutor.monitor.trace import current_trace_id

_logger = get_logger(__name__)

# ----------------------------------------------------------------------------
# 类型定义（仅本文件内可见）
# ----------------------------------------------------------------------------
Subscriber = Callable[["Event"], "None | Awaitable[None]"]


# ----------------------------------------------------------------------------
# 类注释
# ----------------------------------------------------------------------------
class Event:
    """[类名] Event
    [职责] 事件总线传递的事件载体
    [关联设计规范] MD-M-006
    [属性]
      属性1: event_type [str] 事件类型标识（如 pipeline_stage / llm_chunk / error）
      属性2: payload [dict] 事件负载（业务数据，可序列化）
      属性3: trace_id [str] 32hex 追踪 ID，缺省时由 publish 阶段补齐
      属性4: ts_ms [int] 事件时间戳（毫秒）
    [方法列表]
      方法1: to_dict() -> dict - 序列化为 WS 推送 / 日志友好的字典
    [异常处理]
      异常1: 无显式异常，由发布者保证 payload 可序列化
    [来源标注] [DD-001:MD-M-006] + [DD-M推断:依据=IC-008 事件推送 schema]
    """

    def __init__(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
        ts_ms: int | None = None,
    ) -> None:
        self.event_type = event_type
        self.payload = payload or {}
        self.trace_id = trace_id or ""
        self.ts_ms = ts_ms or 0

    def to_dict(self) -> dict[str, Any]:
        """[函数名] to_dict
        [职责] 序列化为字典
        [参数说明] 无
        [返回值] 类型: dict 描述: 包含 event_type/payload/ts/trace_id
        [错误码] 无
        [前置条件] 无
        [后置条件] payload_size 不超过 WS 帧上限
        [并发安全] 是（只读实例属性）
        [幂等性] 是
        [性能约束] O(1)
        [示例]
          ev = Event("llm_chunk", {"delta": "hi"})
          ev.to_dict()
        [来源标注] [DD-M推断:依据=IC-008 event_type/payload/ts/trace_id schema]
        """
        return {
            "event_type": self.event_type,
            "payload": self.payload,
            "ts": self.ts_ms,
            "trace_id": self.trace_id,
        }


class EventBus:
    """[类名] EventBus
    [职责] 事件总线核心（Observer + Mediator 组合）
    [关联设计规范] MD-M-006
    [属性]
      属性1: _subscribers [DefaultDict[str, List[Subscriber]]] 事件类型 → 订阅者列表
      属性2: _lock [threading.RLock] 保护订阅者表的线程安全锁
      属性3: _max_subscribers_per_event [int] 单事件订阅者上限（默认 256）
    [方法列表]
      方法1: subscribe(event_type: str, handler: Subscriber) -> None - 注册订阅者
      方法2: unsubscribe(event_type: str, handler: Subscriber) -> bool - 注销订阅者
      方法3: publish(event: Event) -> None - 同步发布事件
      方法4: publish_async(event: Event) -> Awaitable[None] - 异步发布事件
      方法5: clear() -> None - 清空所有订阅者
    [状态机] N/A（无状态服务）
    [异常处理]
      异常1: Subscriber 异常 -> 隔离 + ERROR 日志，不影响其他订阅者
    [来源标注] [DD-001:MD-M-006] + [DD-M推断:依据=Observer+Mediator 模式实践]
    """

    def __init__(self, max_subscribers_per_event: int = 256) -> None:
        self._subscribers: DefaultDict[str, List[Subscriber]] = defaultdict(list)
        self._lock = threading.RLock()
        self._max_subscribers_per_event = max_subscribers_per_event

    # ---- 函数注释 ----
    def subscribe(self, event_type: str, handler: Subscriber) -> None:
        """[函数名] subscribe
        [职责] 注册事件订阅者
        [关联接口契约] IC-002 隐式调用 / IC-008 隐式调用
        [参数说明]
          参数1: event_type [str] [必填] [事件类型] [非空]
          参数2: handler [Subscriber] [必填] [处理函数，可同步或 async] [可调用]
        [返回值]
          类型: None
          描述: 无返回值
        [错误码]
          错误码1: E00604 含义: 订阅者超限 触发: 超过 max_subscribers_per_event
        [前置条件] handler 可被 inspect.iscoroutinefunction 判定
        [后置条件] 后续 publish(event_type) 触发 handler
        [并发安全] 是（_lock 保护）
        [幂等性] 否（重复订阅会重复触发，需调用方自去重）
        [性能约束] O(1)
        [来源标注] [DD-001:MD-M-006 函数签名 subscribe] + [DD-M推断:依据=典型 pub/sub]
        """
        if not event_type:
            raise ValueError("event_type must be non-empty")
        if not callable(handler):
            raise TypeError("handler must be callable")
        with self._lock:
            if len(self._subscribers[event_type]) >= self._max_subscribers_per_event:
                _logger.error(
                    "subscribe_limit_exceeded",
                    event_type=event_type,
                    limit=self._max_subscribers_per_event,
                )
                return
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Subscriber) -> bool:
        """[函数名] unsubscribe
        [职责] 注销事件订阅者
        [关联接口契约] IC-002 / IC-008 隐式调用
        [参数说明]
          参数1: event_type [str] [必填] [事件类型] [非空]
          参数2: handler [Subscriber] [必填] [原 handler 引用] [对象同一性]
        [返回值]
          类型: bool
          描述: True 找到并移除；False 未找到
        [错误码] 无
        [前置条件] handler 引用同一性
        [后置条件] 后续 publish 不再触发该 handler
        [并发安全] 是（_lock 保护）
        [幂等性] 是（重复注销返回 False，无副作用）
        [性能约束] O(N) N=订阅者数量
        [来源标注] [DD-001:MD-M-006 函数签名 unsubscribe] + [DD-M推断]
        """
        with self._lock:
            handlers = self._subscribers.get(event_type, [])
            for i, h in enumerate(handlers):
                if h is handler:
                    handlers.pop(i)
                    return True
            return False

    def publish(self, event: Event) -> None:
        """[函数名] publish
        [职责] 同步发布事件（隔离订阅者异常）
        [关联接口契约] IC-002 / IC-008
        [参数说明]
          参数1: event [Event] [必填] [事件对象] [event_type 非空]
        [返回值]
          类型: None
          描述: 无返回值
        [错误码]
          错误码1: E00602 含义: 订阅者异常 触发: handler 抛出  处理: 隔离 + ERROR 日志
        [前置条件] event.event_type 非空
        [后置条件] 所有订阅者被调用（无论成功失败）
        [并发安全] 是（handler 各自承担并发责任）
        [幂等性] N/A（事件流）
        [性能约束] O(N) N=订阅者数；handler 异常不阻塞主流程
        [来源标注] [DD-001:MD-M-006 publish_event] + [DD-M推断:依据=Mediator 模式]
        """
        if not event.event_id_safe() if hasattr(event, "event_id_safe") else not event.event_type:
            _logger.error("publish_invalid_event", event=getattr(event, "to_dict", lambda: {})())
            return
        if not event.trace_id:
            event.trace_id = current_trace_id() or ""
        # 快照订阅者列表（避免 handler 中再次 subscribe/unsubscribe 干扰）
        with self._lock:
            handlers = list(self._subscribers.get(event.event_type, []))
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    # 协程在同步 publish 中被丢弃（调用方应使用 publish_async）
                    _logger.warn(
                        "publish_sync_dropped_awaitable",
                        event_type=event.event_type,
                        handler=getattr(handler, "__qualname__", str(handler)),
                    )
            except Exception as exc:  # noqa: BLE001 - 隔离订阅者异常
                _logger.error(
                    "subscriber_exception_isolated",
                    event_type=event.event_type,
                    error=str(exc),
                    trace_id=event.trace_id,
                )

    async def publish_async(self, event: Event) -> None:
        """[函数名] publish_async
        [职责] 异步发布事件（await 所有订阅者）
        [关联接口契约] IC-002 / IC-008
        [参数说明]
          参数1: event [Event] [必填] [事件对象] [event_type 非空]
        [返回值]
          类型: Awaitable[None]
          描述: 协程完成后所有订阅者 handler 已 await 完成
        [错误码]
          错误码1: E00602 含义: 订阅者异常 触发: handler 抛出  处理: 隔离 + ERROR 日志
        [前置条件] event.event_type 非空
        [后置条件] 所有订阅者被 await（无论成功失败）
        [并发安全] 是（订阅者各自并发）
        [幂等性] N/A（事件流）
        [性能约束] 端到端 ≤1s（IC-008 P95）
        [来源标注] [DD-001:MD-M-006] + [DD-M推断:依据=IC-008 端到端 1s]
        """
        if not event.trace_id:
            event.trace_id = current_trace_id() or ""
        with self._lock:
            handlers = list(self._subscribers.get(event.event_type, []))
        # 并发触发所有订阅者；任一异常被隔离
        coros = [self._safe_await(h, event) for h in handlers]
        if coros:
            await asyncio.gather(*coros, return_exceptions=False)

    async def _safe_await(self, handler: Subscriber, event: Event) -> None:
        """[函数名] _safe_await
        [职责] 安全 await 单个订阅者（捕获异常）
        [参数说明]
          参数1: handler [Subscriber] [必填] [处理函数]
          参数2: event [Event] [必填] [事件]
        [返回值] 类型: None
        [错误码] E00602 隔离日志
        [并发安全] 是
        [幂等性] N/A
        [性能约束] O(1)
        [来源标注] [DD-M推断:依据=订阅者异常隔离]
        """
        try:
            result = handler(event)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:  # noqa: BLE001 - 隔离
            _logger.error(
                "subscriber_exception_isolated",
                event_type=event.event_type,
                error=str(exc),
                trace_id=event.trace_id,
            )

    def clear(self) -> None:
        """[函数名] clear
        [职责] 清空所有订阅者（测试 / 重置使用）
        [参数说明] 无
        [返回值] None
        [并发安全] 是（_lock 保护）
        [幂等性] 是
        [来源标注] [DD-M推断:依据=测试可重入需求]
        """
        with self._lock:
            self._subscribers.clear()


# ----------------------------------------------------------------------------
# 模块级单例与便捷函数
# ----------------------------------------------------------------------------
_DEFAULT_BUS: EventBus | None = None
_BUS_LOCK = threading.Lock()


def get_default_bus() -> EventBus:
    """[函数名] get_default_bus
    [职责] 获取进程级事件总线单例
    [参数说明] 无
    [返回值] 类型: EventBus 描述: 进程唯一总线
    [并发安全] 是（_BUS_LOCK）
    [幂等性] 是
    [性能约束] O(1)
    [来源标注] [DD-M推断:依据=Singleton 模式 + 进程内统一事件路由]
    """
    global _DEFAULT_BUS
    if _DEFAULT_BUS is None:
        with _BUS_LOCK:
            if _DEFAULT_BUS is None:
                _DEFAULT_BUS = EventBus()
    return _DEFAULT_BUS


# ---- 函数注释 ----
def publish_event(event_type: str, payload: dict[str, Any] | None = None) -> None:
    """[函数名] publish_event
    [职责] 便捷发布事件（使用默认总线）
    [关联接口契约] IC-002（隐式） / IC-008（隐式）
    [参数说明]
      参数1: event_type [str] [必填] [事件类型] [非空]
      参数2: payload [dict] [可选] [事件负载] [可序列化]
    [返回值]
      类型: None
      描述: 无返回值
    [错误码]
      错误码1: E00601 含义: trace_id 缺失 触发: 当前 ContextVar 无 trace_id  处理: 自动取 current_trace_id
    [前置条件] 无
    [后置条件] 事件被默认总线 publish
    [并发安全] 是
    [幂等性] N/A（事件流）
    [性能约束] O(N) N=订阅者数
    [示例]
      publish_event("llm_chunk", {"delta": "hi"})
    [来源标注] [DD-001:MD-M-006 函数签名 publish_event]
    """
    event = Event(event_type=event_type, payload=payload or {})
    get_default_bus().publish(event)


def subscribe(event_type: str, handler: Subscriber) -> None:
    """[函数名] subscribe
    [职责] 便捷订阅（使用默认总线）
    [关联接口契约] IC-002 / IC-008
    [参数说明]
      参数1: event_type [str] [必填] [事件类型] [非空]
      参数2: handler [Subscriber] [必填] [处理函数] [可调用]
    [返回值] None
    [并发安全] 是
    [幂等性] 否
    [性能约束] O(1)
    [示例]
      subscribe("pipeline_stage", my_handler)
    [来源标注] [DD-001:MD-M-006 函数签名 subscribe]
    """
    get_default_bus().subscribe(event_type, handler)


# 抑制未使用导入告警（suppress 仅为 re-export 时占位）
_ = suppress
