"""meta router（前缀 /api/meta）—— 系统级只读信息（缓存统计等）。"""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..responses import ok

router = APIRouter(tags=["meta"])


@router.get("/cache/stats", summary="LLM 缓存命中统计")
async def cache_stats(request: Request) -> dict:
    cache = request.app.state.cache
    if cache is None:
        return ok({"hits": 0, "misses": 0, "hit_rate": 0.0, "saved_tokens": 0, "entries": 0})
    return ok(cache.stats())
