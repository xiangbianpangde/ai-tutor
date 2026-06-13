"""backend.middleware EventBus / EventRecorder 测试（M-006）。"""
from __future__ import annotations

from backend.middleware import Event, EventBus, EventRecorder


async def test_subscribe_publish_sync_and_async():
    bus = EventBus()
    seen: list[str] = []

    def sync_handler(e: Event) -> None:
        seen.append(f"sync:{e.payload['v']}")

    async def async_handler(e: Event) -> None:
        seen.append(f"async:{e.payload['v']}")

    bus.subscribe("tick", sync_handler)
    bus.subscribe("tick", async_handler)
    delivered = await bus.publish(Event("tick", {"v": 1}))
    assert delivered == 2
    assert set(seen) == {"sync:1", "async:1"}


async def test_type_isolation_and_wildcard():
    bus = EventBus()
    ticks, alls = [], []
    bus.subscribe("tick", lambda e: ticks.append(e))
    bus.subscribe("*", lambda e: alls.append(e))
    await bus.publish(Event("tick"))
    await bus.publish(Event("other"))
    assert len(ticks) == 1  # 只收 tick
    assert len(alls) == 2  # 通配收全部


async def test_unsubscribe():
    bus = EventBus()
    got = []
    unsub = bus.subscribe("x", lambda e: got.append(e))
    await bus.publish(Event("x"))
    unsub()
    await bus.publish(Event("x"))
    assert len(got) == 1


async def test_handler_error_isolated():
    bus = EventBus()
    good = []

    def boom(e):
        raise RuntimeError("handler exploded")

    bus.subscribe("e", boom)
    bus.subscribe("e", lambda e: good.append(e))
    delivered = await bus.publish(Event("e"))  # 不抛
    assert delivered == 1  # 只成功投递好的那个
    assert len(good) == 1


async def test_recorder_ring_buffer():
    bus = EventBus()
    rec = EventRecorder(maxlen=3)
    rec.attach(bus)
    for i in range(5):
        await bus.publish(Event("n", {"i": i}))
    recent = rec.recent()
    assert len(recent) == 3  # 环形只留最后 3
    assert [r["payload"]["i"] for r in recent] == [2, 3, 4]
