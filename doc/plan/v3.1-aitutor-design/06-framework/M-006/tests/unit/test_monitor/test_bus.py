"""test_bus - EventBus 单元测试

> 对应模块: M-006
> 测试策略: 单测（10 用例）/ 覆盖率≥80% [DD-001:MD-M-006]
> Mock 策略: handler 用 lambda / async 协程；默认总线用 monkeypatch
> 来源标注: [DD-001:MD-M-006] + [DD-001:CS-AITutor-V3.1]
"""
from __future__ import annotations

import asyncio
import pytest

from aitutor.monitor.bus import (
    Event,
    EventBus,
    get_default_bus,
    publish_event,
    subscribe,
)

# -----------------------------------------------------------------
# 测试场景列表（覆盖 IC-002 / IC-008 隐式契约）
# -----------------------------------------------------------------
# 场景 1: 正常订阅 + 同步 publish
#   - 断言: handler 被调用 1 次，收到 Event 实例
#   - Mock: 无
#
# 场景 2: 异步 publish
#   - 断言: 异步 handler 被 await 完成
#   - Mock: 无
#
# 场景 3: 多个订阅者全部触发
#   - 断言: 3 个 handler 全部被调用
#   - Mock: 无
#
# 场景 4: 订阅者异常隔离
#   - 断言: handler A 异常不影响 handler B
#   - Mock: 无
#
# 场景 5: 事件类型隔离
#   - 断言: subscribe("a") 不接收 publish("b")
#   - Mock: 无
#
# 场景 6: unsubscribe 移除
#   - 断言: unsubscribe 后 handler 不再触发
#   - Mock: 无
#
# 场景 7: publish 自动补 trace_id
#   - 断言: event.trace_id 非空
#   - Mock: 无
#
# 场景 8: 订阅者超限拒绝
#   - 断言: max=1 时第 2 个 subscribe 被拒绝
#   - Mock: 无
#
# 场景 9: 非法 event_type 校验
#   - 断言: subscribe("") 抛 ValueError
#   - Mock: 无
#
# 场景 10: clear() 清空订阅者
#   - 断言: clear 后 publish 0 触发
#   - Mock: 无
# -----------------------------------------------------------------


def test_subscribe_and_publish_sync() -> None:
    """场景1: 同步 subscribe + publish 触发 handler"""
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe("evt_a", lambda e: received.append(e))
    ev = Event(event_type="evt_a", payload={"k": 1})
    bus.publish(ev)
    assert len(received) == 1
    assert received[0].event_type == "evt_a"
    assert received[0].payload == {"k": 1}


@pytest.mark.asyncio
async def test_publish_async_awaits_handlers() -> None:
    """场景2: publish_async 等待所有异步 handler"""
    bus = EventBus()
    received: list[Event] = []

    async def handler(e: Event) -> None:
        await asyncio.sleep(0)
        received.append(e)

    bus.subscribe("evt_async", handler)
    await bus.publish_async(Event(event_type="evt_async"))
    assert len(received) == 1


def test_multiple_subscribers_all_triggered() -> None:
    """场景3: 多个订阅者全部触发"""
    bus = EventBus()
    counts = {"a": 0, "b": 0, "c": 0}
    bus.subscribe("evt", lambda e: counts.__setitem__("a", counts["a"] + 1))
    bus.subscribe("evt", lambda e: counts.__setitem__("b", counts["b"] + 1))
    bus.subscribe("evt", lambda e: counts.__setitem__("c", counts["c"] + 1))
    bus.publish(Event(event_type="evt"))
    assert counts == {"a": 1, "b": 1, "c": 1}


def test_subscriber_exception_isolated() -> None:
    """场景4: handler 异常被隔离，不影响其他 handler"""
    bus = EventBus()
    received: list[Event] = []

    def bad(_: Event) -> None:
        raise RuntimeError("boom")

    bus.subscribe("evt", bad)
    bus.subscribe("evt", lambda e: received.append(e))
    bus.publish(Event(event_type="evt"))  # 不应抛错
    assert len(received) == 1


def test_event_type_isolation() -> None:
    """场景5: 不同 event_type 互不干扰"""
    bus = EventBus()
    a: list[Event] = []
    b: list[Event] = []
    bus.subscribe("a", lambda e: a.append(e))
    bus.subscribe("b", lambda e: b.append(e))
    bus.publish(Event(event_type="a"))
    assert len(a) == 1 and len(b) == 0


def test_unsubscribe_removes_handler() -> None:
    """场景6: unsubscribe 之后 handler 不再触发"""
    bus = EventBus()
    received: list[Event] = []
    handler = lambda e: received.append(e)
    bus.subscribe("evt", handler)
    bus.publish(Event(event_type="evt"))
    assert bus.unsubscribe("evt", handler) is True
    bus.publish(Event(event_type="evt"))
    assert len(received) == 1  # 第二次未触发


def test_publish_auto_fills_trace_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """场景7: publish 自动补 trace_id（来自 ContextVar）"""
    from aitutor.monitor import trace

    token = trace.bind_trace_id(trace.new_trace_id())
    try:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe("evt", lambda e: received.append(e))
        ev = Event(event_type="evt")
        assert ev.trace_id == ""  # 初始为空
        bus.publish(ev)
        assert received[0].trace_id != ""
    finally:
        trace.reset_trace_id(token)


def test_subscribe_limit_enforced() -> None:
    """场景8: 订阅者超限拒绝"""
    bus = EventBus(max_subscribers_per_event=1)
    bus.subscribe("evt", lambda e: None)
    bus.subscribe("evt", lambda e: None)  # 第二个被拒绝
    assert len(bus._subscribers["evt"]) == 1


def test_subscribe_rejects_empty_event_type() -> None:
    """场景9: 空 event_type 抛 ValueError"""
    bus = EventBus()
    with pytest.raises(ValueError):
        bus.subscribe("", lambda e: None)


def test_clear_empties_subscribers() -> None:
    """场景10: clear() 清空所有订阅者"""
    bus = EventBus()
    received: list[Event] = []
    bus.subscribe("a", lambda e: received.append(e))
    bus.subscribe("b", lambda e: received.append(e))
    bus.clear()
    bus.publish(Event(event_type="a"))
    bus.publish(Event(event_type="b"))
    assert len(received) == 0


# -----------------------------------------------------------------
# 默认总线便捷函数测试
# -----------------------------------------------------------------


def test_default_bus_singleton() -> None:
    """场景补充: get_default_bus 返回单例"""
    a = get_default_bus()
    b = get_default_bus()
    assert a is b


def test_publish_event_module_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    """场景补充: publish_event 便捷函数"""
    received: list[Event] = []

    def handler(e: Event) -> None:
        received.append(e)

    # 隔离默认总线：clear 后注册
    get_default_bus().clear()
    subscribe("helper_evt", handler)
    publish_event("helper_evt", {"x": 1})
    assert len(received) == 1
    assert received[0].payload == {"x": 1}
    # 清理
    get_default_bus().clear()
