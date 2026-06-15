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


@router.get("/health", summary="系统级聚合健康检查（M-001 收尾：各子系统就绪态）")
async def system_health(request: Request) -> dict:
    """聚合 DB/缓存/会话/任务/事件总线就绪态。任一关键子系统不可用 → ok=False。"""
    st = request.app.state
    subsystems = {
        "db": getattr(st, "store", None) is not None and getattr(st, "db_error", None) is None,
        "cache": getattr(st, "cache", None) is not None,
        "sessions": getattr(st, "sessions", None) is not None,
        "tasks": getattr(st, "tasks", None) is not None,
        "events": getattr(st, "events", None) is not None,
    }
    return ok({
        "ok": all(subsystems.values()),
        "version": st.config.app_version,
        "subsystems": subsystems,
        "db_error": getattr(st, "db_error", None),
    })


@router.post("/build", summary="Nuitka onedir 打包调度（M-015，#11）")
async def run_build(request: Request) -> dict:
    """跑打包 FSM（Nuitka→UPX→校验）。runner 可经 app.state.build_runner 注入（测试不真编译）。

    无注入 runner 时用真 subprocess——真编译 5-15min，生产/CI 用；默认不在请求线程真跑。
    """
    from ..build import BuildOrchestrator

    runner = getattr(request.app.state, "build_runner", None)
    return ok(BuildOrchestrator(runner=runner).run())
