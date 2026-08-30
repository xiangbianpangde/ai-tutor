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


# ------------------------------------------------------------------ #
# 今日复习队列（M-011 遗忘曲线 → 行动列表）
# ------------------------------------------------------------------ #
@router.get("/users/{user_id}/review-due",
            summary="今日复习队列：next_review_at 已到期的概念（欠复习倒序）")
async def review_due(request: Request, user_id: str, subject_id: str | None = None) -> dict:
    """基于 forgetting_curves 的到期概念列表；subjects 可限定科目。

    每个条目附概念可读名（concepts 表回填）。未来可在此接
    MemoryStore.get_due_reviews() 的持久化查询——遗忘曲线表是唯一真相源。
    """
    store = request.app.state.store
    if store is None:
        from shared.errors import TutorError

        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")

    from datetime import datetime
    from servers.tutoring_mcp.memory_store import MemoryStore

    mem = MemoryStore(store)
    due = mem.get_due_reviews(user_id=user_id, subject_id=subject_id)

    from shared.models import ConceptRow

    items = []
    with store.session() as s:
        for d in due:
            name_row = (
                s.query(ConceptRow.name_primary)
                .filter(ConceptRow.base_id == d.concept_id)
                .first()
            )
            label = name_row[0] if name_row and name_row[0] else d.concept_id
            items.append({
                "concept_id": d.concept_id,
                "label": label,
                "subject_id": d.subject_id,
                "next_review_at": d.next_review_at.isoformat(),
                "overdue_days": round(max(0.0, d.days_overdue), 2),
                "lambda_param": round(d.lambda_param, 4),
                "n_data_points": d.n_data_points,
            })
    return ok({"user_id": user_id, "items": items})


@router.post("/users/{user_id}/review/record",
             summary="记录一次真实复习（写 review_history + 重拟合遗忘曲线）")
async def record_review(
    request: Request,
    user_id: str,
    concept_id: str = Body(..., embed=True),
    subject_id: str = Body(..., embed=True),
    accuracy: float = Body(..., embed=True),
    review_mode: str = Body("quick_quiz", embed=True),
) -> dict:
    """上报复习结果：accuracy ∈ [0,1]，后端据此推进 next_review_at 与 streak。"""
    store = request.app.state.store
    if store is None:
        from shared.errors import TutorError

        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")
    if not 0.0 <= accuracy <= 1.0:
        from shared.errors import TutorError

        raise TutorError("REVIEW_INVALID_ACCURACY", "accuracy 必须在 [0,1]")

    from datetime import datetime
    from servers.tutoring_mcp.memory_store import MemoryStore

    mem = MemoryStore(store)
    curve = mem.record_review(
        user_id=user_id,
        concept_id=concept_id,
        subject_id=subject_id,
        accuracy=accuracy,
        review_mode=review_mode,
        review_date=datetime.utcnow(),
    )
    return ok({
        "curvature": {
            "lambda_param": round(getattr(curve, "lambda_param", 0.0), 4),
            "next_review_at": getattr(curve, "next_review_at", None).isoformat()
            if getattr(curve, "next_review_at", None) else None,
            "review_streak": getattr(curve, "review_streak", 0),
        }
    })


# ------------------------------------------------------------------ #
# 多 Session 学习计划（learning_plans 表 + 实时 BKT 进度）
# ------------------------------------------------------------------ #
@router.get("/users/{user_id}/subjects/{subject_id}/learning-plan",
            summary="跨会话学习计划：惰性建计划 + 实时 BKT 掌握度进度")
async def learning_plan(request: Request, user_id: str, subject_id: str) -> dict:
    """读取（必要时构建并持久化）学习计划，并叠加实时掌握度进度。

    数据源：learning_plans 表（按 user+subject 唯一）；构建用
    servers.tutoring_mcp.server._get_or_build_plan（KG 拓扑序 → 章节 Phase 分组）。
    进度用 BKT 实时计算，计划本身只存概念 id 分组，不会"过期"。
    """
    from servers.tutoring_mcp.server import _get_or_build_plan, _progress_for
    from shared.errors import TutorError

    store = request.app.state.store
    if store is None:
        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")

    from shared.models import Subject

    with store.session() as s:
        subj = s.get(Subject, subject_id)
        if subj is None or subj.user_id != user_id:
            raise TutorError("SUBJECT_NOT_FOUND", f"subject_id={subject_id} 不存在或不属于该用户")
        kg_id = subj.kg_id
        if not kg_id:
            raise TutorError("KG_NOT_BUILT", hint=f"subject={subject_id} 未关联 KG")

    plan = _get_or_build_plan(store, user_id, subject_id, kg_id)
    progress = _progress_for(store, user_id, subject_id, kg_id)
    return ok({
        "plan": plan.model_dump(mode="json"),
        "progress": progress.model_dump(mode="json"),
    })


# ------------------------------------------------------------------ #
# 会话历史回放（跨会话判分详情 + 概览，复盘"我之前怎么错的"）
# ------------------------------------------------------------------ #
@router.get("/users/{user_id}/session-history",
            summary="会话历史回放：跨会话判分详情 + 概览统计")
async def session_history(request: Request, user_id: str) -> dict:
    """聚合该用户所有会话的判分回放（recent_history 全量，SQLite 持久）。

    每条记录：会话 id / 概念名 / 正确性 / 时间 / 答案原文 / 自我纠正标记。
    概览：会话数 / 总判分 / correct_rate / 各正确性计数。按时间倒序。
    """
    import json

    store = request.app.state.store
    if store is None:
        from shared.errors import TutorError

        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")

    from shared.models import ConceptRow, SessionRow

    sessions = []
    entries = []
    with store.session() as s:
        rows = (
            s.query(SessionRow)
            .filter_by(user_id=user_id)
            .order_by(SessionRow.started_at.desc())
            .all()
        )
        for row in rows:
            raw = row.context_json or "{}"
            try:
                ctx = json.loads(raw) if isinstance(raw, str) else raw
            except (ValueError, TypeError):
                ctx = {}
            history = ctx.get("recent_history") or []
            sessions.append({
                "session_id": row.id,
                "subject_id": row.subject_id,
                "status": row.status,
                "started_at": (
                    row.started_at.isoformat() if row.started_at else None
                ),
                "history_count": len(history),
            })
            for entry in history:
                cid = entry.get("concept_id") or ""
                name_row = (
                    s.query(ConceptRow.name_primary)
                    .filter(ConceptRow.base_id == cid)
                    .first()
                )
                entries.append({
                    "session_id": row.id,
                    "subject_id": row.subject_id,
                    "concept_id": cid,
                    "concept_name": name_row[0] if name_row and name_row[0] else cid,
                    "correctness": entry.get("correctness"),
                    "timestamp": entry.get("timestamp"),
                    "answer": entry.get("answer"),
                    "was_self_corrected": bool(entry.get("was_self_corrected")),
                })

    entries.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    total = len(entries)
    counts = {"correct": 0, "partial": 0, "incorrect": 0}
    for e in entries:
        c = e.get("correctness")
        if c in counts:
            counts[c] += 1
    overview = {
        "sessions": len(sessions),
        "attempts": total,
        "correct": counts["correct"],
        "partial": counts["partial"],
        "incorrect": counts["incorrect"],
        "correct_rate": round(counts["correct"] / total, 3) if total else 0.0,
    }
    return ok({"user_id": user_id, "overview": overview,
               "sessions": sessions, "entries": entries})
