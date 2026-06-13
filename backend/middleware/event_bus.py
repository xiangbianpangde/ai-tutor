"""backend.middleware.event_bus —— 进程内事件总线（M-006，v3.1 新增模块）。

v2 原假设同步调用，#7 status 实时推送 / #11 监控埋点没有统一事件层。本层提供 pub/sub：
教学/任务/检索等关键动作 publish 事件，WebSocket 推送、监控记录各自 subscribe，互不耦合。

- 处理器可同步可异步（async def）；publish 是 async，逐个调用并 await 异步处理器。
- **错误隔离**：单个处理器抛错只记日志，不影响其他订阅者、不打断 publish。
"""
from __future__ import annotations

import inspect
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

WILDCARD = "*"

Handler = Callable[["Event"], Any]


@dataclass
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class EventBus:
    """订阅/发布。`subscribe` 返回取消订阅函数。`*` 订阅所有事件。"""

    def __init__(self, *, logger: Any = None) -> None:
        self._subs: dict[str, list[Handler]] = defaultdict(list)
        self._logger = logger

    def subscribe(self, event_type: str, handler: Handler) -> Callable[[], None]:
        self._subs[event_type].append(handler)

        def unsubscribe() -> None:
            handlers = self._subs.get(event_type)
            if handlers and handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    async def publish(self, event: Event) -> int:
        """投递给 type 订阅者 + 通配订阅者；返回成功投递数。"""
        handlers = list(self._subs.get(event.type, ())) + list(self._subs.get(WILDCARD, ()))
        delivered = 0
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
                delivered += 1
            except Exception as exc:  # 错误隔离：一个处理器挂不影响其他
                if self._logger is not None:
                    self._logger.warning("eventbus.handler_error", type=event.type, error=str(exc))
        return delivered

    def subscriber_count(self, event_type: str | None = None) -> int:
        if event_type is None:
            return sum(len(v) for v in self._subs.values())
        return len(self._subs.get(event_type, ()))


class EventRecorder:
    """订阅 `*`，把最近 N 条事件留在环形缓冲——供 /api/meta/events 调试与监控基线。"""

    def __init__(self, maxlen: int = 100) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=maxlen)

    def attach(self, bus: EventBus) -> Callable[[], None]:
        return bus.subscribe(WILDCARD, self._on_event)

    def _on_event(self, event: Event) -> None:
        self._events.append({"type": event.type, "payload": event.payload, "ts": event.ts})

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        items = list(self._events)
        return items[-limit:]
