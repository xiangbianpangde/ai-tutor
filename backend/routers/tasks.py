"""tasks router（前缀 /api/tasks）—— 后台任务状态/进度轮询（M-007）。"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from ..core import TutorError
from ..responses import ok

router = APIRouter(tags=["tasks"])


@router.get("/{task_id}", summary="查询后台任务状态/进度/结果")
async def get_task(task_id: str, request: Request) -> dict:
    manager = request.app.state.tasks
    record = manager.get(task_id) if manager is not None else None
    if record is None:
        raise TutorError("TASK_NOT_FOUND", "任务不存在", hint=task_id)
    return ok(record)


@router.get("", summary="任务中心：最近任务列表（含进度，任务中心页数据源）")
async def list_tasks(request: Request, limit: int = Query(20, ge=1, le=100)) -> dict:
    """读取 tasks 表最近 N 条（全部用户）；进度用于任务中心进度条。"""
    engine = request.app.state.store.engine
    sql = (
        "SELECT task_id, kind, state, progress, message, "
        "created_at, updated_at FROM tasks ORDER BY created_at DESC LIMIT :bnd"
    )
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(sql, {"bnd": limit}).fetchall()
    items = [
        {
            "task_id": r[0],
            "kind": r[1],
            "state": r[2],
            "progress": float(r[3] or 0.0),
            "message": (r[4] or "")[:120],
            "created_at": r[5],
            "updated_at": r[6],
        }
        for r in rows
    ]
    return ok({"items": items})
