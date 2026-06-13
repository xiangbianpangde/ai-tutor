"""tutoring 引擎 router（前缀 /api/tutoring）。

C1：/health。C2：GET /sessions（多会话列表，M-004）。后续波次迁入 cold-start /
progress / checkpoint / insight / review-plan（REST）+ /ws/tutoring/{session_id}（WebSocket）。
"""
from __future__ import annotations

from fastapi import Query, Request

from ..responses import ok
from ._common import engine_router

router = engine_router("tutoring")


@router.get("/sessions", summary="列出用户的所有会话（M-004 spec 03 场景1）")
async def list_sessions(request: Request, user_id: str = Query(...)) -> dict:
    sessions = request.app.state.sessions
    if sessions is None:
        return ok([])
    return ok(sessions.list_sessions(user_id))
