"""tutoring 引擎 router（前缀 /api/tutoring）。

C1：/health。C2：GET /sessions（多会话列表，M-004）。
C3：M-009 教学编排——POST /sessions/start + .../respond + .../next-action + .../transition。
后续波次迁入 cold-start / progress / checkpoint / insight / review-plan（REST）+
/ws/tutoring/{session_id}（WebSocket）。
"""
from __future__ import annotations

from fastapi import Body, Query, Request

from ..responses import ok
from ..teaching import TeachingOrchestrator
from ._common import engine_router

router = engine_router("tutoring")


def _orchestrator(request: Request) -> TeachingOrchestrator:
    """取/建教学编排器（缓存于 app.state）。engine_factory 可经 app.state 注入（测试用 stub）。"""
    from shared.errors import TutorError

    existing = getattr(request.app.state, "teaching", None)
    if existing is not None:
        return existing
    store = request.app.state.store
    if store is None:
        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")
    orch = TeachingOrchestrator(
        store,
        llm=getattr(request.app.state, "tutor_llm", None),
        sessions=getattr(request.app.state, "sessions", None),
        events=getattr(request.app.state, "events", None),
        engine_factory=getattr(request.app.state, "teaching_engine_factory", None),
    )
    request.app.state.teaching = orch
    return orch


@router.get("/sessions", summary="列出用户的所有会话（M-004 spec 03 场景1）")
async def list_sessions(request: Request, user_id: str = Query(...)) -> dict:
    sessions = request.app.state.sessions
    if sessions is None:
        return ok([])
    return ok(sessions.list_sessions(user_id))


@router.post("/sessions/start", summary="开启新学习会话（M-009 教学编排）")
async def start_session(
    request: Request,
    user_id: str = Body(..., embed=True),
    subject_id: str = Body(..., embed=True),
    kg_id: str | None = Body(None, embed=True),
) -> dict:
    """定位首个概念 → 建会话 → 返回首个教学动作。"""
    orch = _orchestrator(request)
    return ok(await orch.start(user_id=user_id, subject_id=subject_id, kg_id=kg_id))


@router.get("/sessions/{session_id}/next-action", summary="要下一个教学动作（M-009）")
async def next_action(session_id: str, request: Request) -> dict:
    return ok(await _orchestrator(request).next_action(session_id))


@router.post("/sessions/{session_id}/respond", summary="学生作答 → 判分/反馈/策略推进（M-009）")
async def respond(
    session_id: str, request: Request, answer: str = Body(..., embed=True)
) -> dict:
    return ok(await _orchestrator(request).respond(session_id, answer))


@router.post("/sessions/{session_id}/advance", summary="讲解步骤后继续（M-009）")
async def advance(session_id: str, request: Request) -> dict:
    return ok(await _orchestrator(request).advance(session_id))


@router.post("/sessions/{session_id}/transition", summary="推进策略状态机事件（M-009）")
async def transition(
    session_id: str,
    request: Request,
    event: str = Body(..., embed=True),
    payload: dict | None = Body(None, embed=True),
) -> dict:
    return ok(await _orchestrator(request).transition(session_id, event=event, payload=payload))
