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


# ------------------------------------------------------------------ #
# 薄弱概念诊断（前端「薄弱诊断」面板数据源）
# ------------------------------------------------------------------ #
_WEAK_THRESHOLD = 0.5            # 低于此 →薄弱
_CONSOLIDATION_THRESHOLD = 0.8   # 低于此 →巩固中；达到 →已掌握


def _band(mastery: float) -> str:
    if mastery < _WEAK_THRESHOLD:
        return "weak"
    if mastery < _CONSOLIDATION_THRESHOLD:
        return "consolidating"
    return "mastered"


@router.get("/users/{user_id}/weak-concepts",
            summary="薄弱概念诊断：BKT 掌握度 + 近期判分历史聚合")
async def weak_concepts(request: Request, user_id: str) -> dict:
    """按用户聚合 BKT 掌握度与各会话近期判分历史，最薄弱的排最前。

    数据源：
    - ``bkt_params``：每概念 p_mastery / n_observations（跨会话持久）。
    - ``sessions.context_json.recent_history``：答题明细（正确性 / 时间戳 /
      自我纠正标记），只统计该用户自己的会话。
    概念可读名来自 concepts 表（同一 base 概念可能对应多行，取首个非空名）。
    """
    import json

    store = request.app.state.store
    if store is None:
        from shared.errors import TutorError

        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")

    from shared.models import BKTParamRow, ConceptRow, SessionRow

    concepts: dict[str, dict] = {}
    attempts: list[dict] = []
    with store.session() as s:
        for row in s.query(BKTParamRow).filter_by(user_id=user_id).all():
            concepts[row.concept_id] = {
                "concept_id": row.concept_id,
                "label": row.concept_id,
                "mastery": round(float(row.p_mastery), 4),
                "observations": int(row.n_observations),
                "last_updated": (
                    row.last_updated.isoformat() if row.last_updated else None
                ),
            }
        for concept_id in concepts:
            name_row = (
                s.query(ConceptRow.name_primary)
                .filter(ConceptRow.base_id == concept_id)
                .first()
            )
            if name_row and name_row[0]:
                concepts[concept_id]["label"] = name_row[0]

        for row in s.query(SessionRow).filter_by(user_id=user_id).all():
            raw = row.context_json or "{}"
            if isinstance(raw, str):
                try:
                    ctx = json.loads(raw)
                except (ValueError, TypeError):
                    continue
            else:
                ctx = raw  # JSON 列反序列化后已是 dict
            for entry in ctx.get("recent_history") or []:
                attempts.append({
                    "session_id": row.id,
                    "concept_id": entry.get("concept_id"),
                    "correctness": entry.get("correctness"),
                    "timestamp": entry.get("timestamp"),
                    "was_self_corrected": bool(entry.get("was_self_corrected")),
                    "answer": entry.get("answer"),
                })

    items = []
    for concept in concepts.values():
        cid = concept["concept_id"]
        mine = [a for a in attempts if a.get("concept_id") == cid]
        wrong = [
            a for a in mine if a.get("correctness") in ("partial", "incorrect")
        ]
        recent_wrong = sorted(
            wrong, key=lambda a: a.get("timestamp") or "", reverse=True
        )
        items.append({
            **concept,
            "band": _band(concept["mastery"]),
            "attempts": len(mine),
            "wrong_attempts": len(wrong),
            "last_wrong_at": recent_wrong[0].get("timestamp") if recent_wrong else None,
        })
    items.sort(key=lambda item: (item["mastery"], -item["wrong_attempts"]))

    overview = {
        "concepts": len(items),
        "mastered": sum(1 for i in items if i["band"] == "mastered"),
        "consolidating": sum(1 for i in items if i["band"] == "consolidating"),
        "weak": sum(1 for i in items if i["band"] == "weak"),
        "attempts": sum(i["attempts"] for i in items),
        "wrong_attempts": sum(i["wrong_attempts"] for i in items),
    }
    return ok({"user_id": user_id, "overview": overview, "items": items})
