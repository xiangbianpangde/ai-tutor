"""tasks router（前缀 /api/tasks）—— 后台任务状态/进度轮询（M-007）。"""
from __future__ import annotations

from fastapi import APIRouter, Request

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
