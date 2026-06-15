"""backend.routers.ws —— WebSocket 实时推送（#7 status 实时更新 / spec 04 功能4）。

订阅 M-006 EventBus 的全部事件（通配 `*`），经 asyncio.Queue 解耦后推给前端。教学/任务/
RAG 等动作 publish 事件，本端点转发——前端学习中心据此实时更新，无需轮询。

解耦设计：EventBus.publish 内联调订阅处理器；这里处理器只把事件塞进队列（不阻塞 publish），
WS 发送循环独立从队列取并 send_json。客户端断开 → finally 取消订阅，不泄露。
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """全局事件流。连接即推 `ws.connected`，随后实时转发 EventBus 所有事件。"""
    await websocket.accept()
    bus = getattr(websocket.app.state, "events", None)
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def _handler(event: Any) -> None:
        await queue.put({"type": event.type, "payload": event.payload, "ts": event.ts})

    unsubscribe = bus.subscribe("*", _handler) if bus is not None else (lambda: None)
    await websocket.send_json({"type": "ws.connected", "payload": {"bus": bus is not None}})

    # 后台读客户端消息以感知断开（心跳/ping 可选）
    async def _drain_incoming() -> None:
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            await queue.put({"type": "__close__", "payload": {}})

    drain = asyncio.create_task(_drain_incoming())
    try:
        while True:
            msg = await queue.get()
            if msg.get("type") == "__close__":
                break
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe()
        drain.cancel()
