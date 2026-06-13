"""状态面板的只读数据层。

从同一 SQLite 拼出面板所需状态——**只读**，不写任何生产数据、不调用 MCP tool。
复用 learning_plan.compute_progress 算 48h Phase 进度；计划若未持久化则在内存里临时构建
（不落库）。掌握度分桶阈值与系统一致（mastered ≥ 0.8）。
"""
from __future__ import annotations

from typing import Any

from servers.tutoring_mcp.cold_start import MASTERY_SKIP_THRESHOLD
from servers.tutoring_mcp.learning_plan import (
    LearningPlanStore,
    build_plan,
    compute_progress,
)
from shared.models import BKTParamRow, ConceptRow, SessionRow, Subject
from shared.schemas import Concept, SessionContext
from shared.storage import RelationalStore

_MASTERED = MASTERY_SKIP_THRESHOLD  # 0.8
_LEARNING = 0.4
_DEFAULT_MASTERY = 0.05


def _chapter_key(concept_id: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in concept_id.split(":")[1].split("."))
    except (IndexError, ValueError):
        return (10**9,)


def _latest_session(db: RelationalStore) -> dict | None:
    with db.session() as s:
        row = (
            s.query(SessionRow)
            .order_by(SessionRow.started_at.desc())
            .first()
        )
        return dict(row.context_json) if row is not None else None


def _subject_kg(db: RelationalStore, subject_id: str) -> str | None:
    with db.session() as s:
        subj = s.get(Subject, subject_id)
        return subj.kg_id if subj else None


def _load_concepts(db: RelationalStore, kg_id: str | None) -> list[Concept]:
    if not kg_id:
        return []
    with db.session() as s:
        rows = s.query(ConceptRow).filter_by(kg_id=kg_id).all()
        out: list[Concept] = []
        for r in rows:
            try:
                out.append(Concept.model_validate(r.full_json))
            except Exception:  # noqa: BLE001 — 损坏概念跳过，不阻断面板
                continue
        return out


def _bkt_map(db: RelationalStore, user_id: str) -> dict[str, float]:
    with db.session() as s:
        rows = s.query(BKTParamRow).filter_by(user_id=user_id).all()
        return {r.concept_id: r.p_mastery for r in rows}


def get_dashboard_state(db: RelationalStore) -> dict[str, Any]:
    """拼出面板状态。无会话 → {"status": "idle"}。"""
    ctx_json = _latest_session(db)
    if ctx_json is None:
        return {"status": "idle"}
    try:
        ctx = SessionContext.model_validate(ctx_json)
    except Exception:  # noqa: BLE001
        return {"status": "idle", "error": "session context 解析失败"}

    user_id = ctx.user_id
    kg_id = ctx.teaching_plan_id or _subject_kg(db, ctx.subject_id)
    concepts = _load_concepts(db, kg_id)
    names = {c.id: (c.names[0] if c.names else c.id) for c in concepts}
    bkt = _bkt_map(db, user_id)

    def mastery_of(cid: str) -> float:
        return bkt.get(cid, _DEFAULT_MASTERY)

    mastered = sum(1 for c in concepts if mastery_of(c.id) >= _MASTERED)
    learning = sum(1 for c in concepts if _LEARNING <= mastery_of(c.id) < _MASTERED)
    weak = len(concepts) - mastered - learning

    # Phase 进度：优先持久化计划，否则内存临时构建（不落库）
    plan = LearningPlanStore(db).load(user_id, ctx.subject_id)
    if plan is None and concepts:
        plan = build_plan(
            user_id=user_id, subject_id=ctx.subject_id, kg_id=kg_id or "",
            ordered_concepts=sorted(concepts, key=lambda c: _chapter_key(c.id)),
        )
    prog = (
        compute_progress(plan=plan, mastery_of=mastery_of, name_of=names).model_dump()
        if plan is not None
        else None
    )

    cur = ctx.current_concept_id
    flow = ctx.recent_history[-1].get("flow_level") if ctx.recent_history else None

    return {
        "status": ctx.status,
        "user_id": user_id,
        "subject_id": ctx.subject_id,
        "current_concept_id": cur,
        "current_concept_name": names.get(cur) if cur else None,
        "current_mastery": round(mastery_of(cur), 3) if cur else None,
        "flow_level": flow,
        "strategy": ctx.current_strategy,
        "strategy_state": ctx.current_strategy_state,
        "strategy_internal": dict(ctx.strategy_internal or {}),
        "cognitive_load": round(ctx.meta.current_cognitive_load, 3),
        "mastery": {
            "mastered": mastered, "learning": learning,
            "weak": weak, "total": len(concepts),
        },
        "recent_history": ctx.recent_history[-10:],
        "plan_progress": prog,
    }
