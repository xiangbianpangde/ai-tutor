"""tutoring 引擎 router（前缀 /api/tutoring）。

C1：/health。C2：GET /sessions（多会话列表，M-004）。
C3：M-009 教学编排——POST /sessions/start + .../respond + .../next-action + .../transition。
后续波次迁入 cold-start / progress / checkpoint / insight / review-plan（REST）+
/ws/tutoring/{session_id}（WebSocket）。
"""
from __future__ import annotations

from fastapi import Body, Query, Request

from ..memory import LongTermMemory
from ..responses import ok
from ..strategy import FeynmanScorer, StageCalibrator, get_default_scheduler
from ..strategy.fsrs import Card, Rating
from ..teaching import TeachingOrchestrator
from ._common import engine_router

router = engine_router("tutoring")


def _memory(request: Request) -> LongTermMemory:
    """取/建长期记忆 Façade（缓存于 app.state，落同库 long_term_facts 表）。"""
    from shared.errors import TutorError

    existing = getattr(request.app.state, "memory", None)
    if existing is not None:
        return existing
    store = request.app.state.store
    if store is None:
        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")
    mem = LongTermMemory(store)
    request.app.state.memory = mem
    return mem


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


# ----------------------------- C4 策略升级端点 ----------------------------- #

@router.post("/feynman/score", summary="费曼讲解评分（M-010，#12）")
async def feynman_score(
    request: Request,
    explanation: str = Body(..., embed=True),
    concept_name: str = Body(..., embed=True),
    definition: str = Body(..., embed=True),
) -> dict:
    """评学生对某概念的费曼式讲解：覆盖率/缺口/是否背书。回退启发式诚实不过度授信。"""
    scorer = FeynmanScorer(llm_judge=getattr(request.app.state, "feynman_judge", None))
    res = scorer.score(explanation=explanation, concept_name=concept_name, definition=definition)
    return ok(res.to_dict())


@router.post("/review/schedule", summary="FSRS-5 间隔重复调度（M-011，遗忘曲线）")
async def review_schedule(
    request: Request,
    rating: int = Body(..., embed=True),
    card: dict | None = Body(None, embed=True),
) -> dict:
    """对一张卡施加评分（1忘/2难/3良/4易），返回更新卡 + 下次间隔。card 省略=新卡首评。"""
    from datetime import datetime

    c = Card()
    if card:
        due = card.get("due")
        last = card.get("last_review")
        c = Card(
            stability=card.get("stability"),
            difficulty=card.get("difficulty"),
            due=datetime.fromisoformat(due) if due else None,
            last_review=datetime.fromisoformat(last) if last else None,
            reps=card.get("reps", 0),
            lapses=card.get("lapses", 0),
            state=card.get("state", "new"),
        )
    result = get_default_scheduler().review(c, Rating(rating))
    return ok(result.to_dict())


@router.post("/stage/calibrate", summary="阶段校准（M-012，滑动窗口+滞回防抖，#16）")
async def stage_calibrate(
    request: Request,
    scores: list[float] = Body(..., embed=True),
    current_stage: int = Body(0, embed=True),
) -> dict:
    """喂近期表现分序列，返回升/降/保持建议（连续达标才动档，防过渡太猛）。"""
    cal = StageCalibrator()
    for s in scores:
        cal.record(s)
    return ok(cal.recommend(current_stage))


@router.post("/memory/facts", summary="存一条长期事实（M-013，#18 抗长期幻觉）")
async def save_fact(
    request: Request,
    user_id: str = Body(..., embed=True),
    subject_id: str = Body(..., embed=True),
    content: str = Body(..., embed=True),
    source: str | None = Body(None, embed=True),
) -> dict:
    fid = _memory(request).save_fact(user_id=user_id, subject_id=subject_id,
                                     content=content, source=source)
    return ok({"fact_id": fid})


@router.get("/memory/facts", summary="检索长期事实（M-013，接地回答）")
async def query_facts(
    request: Request,
    user_id: str = Query(...),
    subject_id: str = Query(...),
    query: str | None = Query(None),
    limit: int = Query(10),
) -> dict:
    return ok(_memory(request).query_facts(user_id=user_id, subject_id=subject_id,
                                           query=query, limit=limit))
