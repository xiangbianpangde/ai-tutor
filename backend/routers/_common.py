"""backend.routers._common —— 各引擎 router 的共用装配。"""
from __future__ import annotations

from fastapi import APIRouter, Request


def engine_router(engine: str) -> APIRouter:
    """建一个引擎 router，预置 ``GET /health``（挂载前缀 ``/api/{engine}``）。

    后续波次在返回的 router 上继续追加该引擎的 REST/WS endpoint。
    """
    router = APIRouter(tags=[engine])

    @router.get("/health", summary=f"{engine} 引擎健康检查")
    async def health(request: Request) -> dict:
        config = request.app.state.config
        return {"ok": True, "version": config.app_version, "engine": engine}

    return router
