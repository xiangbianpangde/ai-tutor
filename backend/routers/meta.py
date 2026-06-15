"""meta router（前缀 /api/meta）—— 系统级只读信息（缓存统计 / 事件 / 红线编排）。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Request

from ..redline import RedlineOrchestrator
from ..responses import ok

router = APIRouter(tags=["meta"])


@router.get("/cache/stats", summary="LLM 缓存命中统计")
async def cache_stats(request: Request) -> dict:
    cache = request.app.state.cache
    if cache is None:
        return ok({"hits": 0, "misses": 0, "hit_rate": 0.0, "saved_tokens": 0, "entries": 0})
    return ok(cache.stats())


@router.get("/events", summary="最近事件（事件总线环形缓冲，M-006）")
async def recent_events(request: Request, limit: int = 50) -> dict:
    recorder = getattr(request.app.state, "event_recorder", None)
    return ok(recorder.recent(limit) if recorder is not None else [])


@router.post("/redline", summary="跑红线编排（ruff/import-linter…聚合，M-016）")
async def run_redline(request: Request, fail_fast: bool = Body(False, embed=True)) -> dict:
    """依次跑红线工具并聚合。runner 可经 app.state.redline_runner 注入（测试不真 shell out）。"""
    runner = getattr(request.app.state, "redline_runner", None)
    orch = RedlineOrchestrator(runner=runner)
    return ok(orch.run(fail_fast=fail_fast))
