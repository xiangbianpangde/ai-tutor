"""逐层可视化的只读数据层 —— 八个 get_layer_*_state。

与 state.py 的总览面板互补：这里按七层认知架构 + PGFGA 各自拼出该层的
诊断数据，全部**只读**，从同一 SQLite 取可得数据，绝不写库、不调 MCP tool。

设计取舍（诚实优先）：
- 已落库的（KG/概念/关系/BKT/复习历史/遗忘曲线/会话）→ 真实拼出。
- 运行时瞬态、未落库的（插件/缓存健康、防火墙触发、SDT 信号、增益回路事件）
  → 标注 persisted=False，给出能从会话历史派生的近似（如心流趋势），不臆造。
每个函数都不抛错：单点数据异常降级为空/部分，保证面板永不崩。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from servers.dashboard.state import (
    _latest_session,
    _load_concepts,
    _subject_kg,
)
from shared.models import (
    BKTParamRow,
    ConceptRow,
    Corpus,
    ForgettingCurveRow,
    KnowledgeGraphRow,
    LearnerProfileRow,
    LearningPlanRow,
    RelationRow,
    ReviewHistoryRow,
    SessionRow,
    Subject,
    User,
)
from shared.schemas import SessionContext
from shared.storage import RelationalStore

_MERMAID_MAX_NODES = 40


def _safe_ctx(db: RelationalStore) -> SessionContext | None:
    ctx_json = _latest_session(db)
    if ctx_json is None:
        return None
    try:
        return SessionContext.model_validate(ctx_json)
    except Exception:  # noqa: BLE001 — 解析失败按无会话处理
        return None


# --------------------------------------------------------------------------- #
# L1 基础设施
# --------------------------------------------------------------------------- #
def get_layer_l1_state(db: RelationalStore) -> dict[str, Any]:
    """存储统计（各表行数）。插件/缓存健康为运行时态，read-only 进程拿不到 → 标注。"""
    models = {
        "users": User, "subjects": Subject, "corpora": Corpus,
        "knowledge_graphs": KnowledgeGraphRow, "concepts": ConceptRow,
        "relations": RelationRow, "bkt_params": BKTParamRow,
        "review_history": ReviewHistoryRow, "forgetting_curves": ForgettingCurveRow,
        "learner_profiles": LearnerProfileRow, "sessions": SessionRow,
        "learning_plans": LearningPlanRow,
    }
    tables: dict[str, int] = {}
    with db.session() as s:
        for name, model in models.items():
            try:
                tables[name] = s.query(model).count()
            except Exception:  # noqa: BLE001
                tables[name] = -1
    return {
        "db_url": db.url,
        "tables": tables,
        "total_rows": sum(v for v in tables.values() if v >= 0),
        "plugin_health": {"persisted": False,
                          "note": "插件/缓存健康为运行时态，需在 MCP 进程内查询"},
    }


# --------------------------------------------------------------------------- #
# L2 短期记忆
# --------------------------------------------------------------------------- #
def get_layer_l2_state(db: RelationalStore) -> dict[str, Any]:
    """会话列表 + 中断恢复记录。"""
    sessions: list[dict[str, Any]] = []
    active = interrupted = 0
    with db.session() as s:
        rows = s.query(SessionRow).order_by(SessionRow.started_at.desc()).limit(50).all()
        for r in rows:
            cj = r.context_json or {}
            cp = cj.get("interrupt_checkpoint")
            if r.status == "active":
                active += 1
            if r.status == "interrupted" or cp:
                interrupted += 1
            sessions.append({
                "session_id": r.id,
                "user_id": r.user_id,
                "subject_id": r.subject_id,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "current_concept_id": cj.get("current_concept_id"),
                "has_checkpoint": cp is not None,
                "interrupt_count": (cj.get("meta") or {}).get("interrupt_count", 0),
            })
    return {"sessions": sessions, "active_count": active, "interrupted_count": interrupted}


# --------------------------------------------------------------------------- #
# L3 长期记忆
# --------------------------------------------------------------------------- #
def get_layer_l3_state(db: RelationalStore) -> dict[str, Any]:
    """遗忘曲线 + 到期复习队列 + 复习模式分布。"""
    now = datetime.utcnow()
    curves: list[dict[str, Any]] = []
    due = 0
    mode_dist: dict[str, int] = {}
    with db.session() as s:
        for fc in s.query(ForgettingCurveRow).limit(200).all():
            is_due = fc.next_review_at is not None and fc.next_review_at <= now
            if is_due:
                due += 1
            curves.append({
                "concept_id": fc.concept_id,
                "lambda": round(fc.lambda_param, 4),
                "r_squared": round(fc.r_squared, 3) if fc.r_squared is not None else None,
                "n_data_points": fc.n_data_points,
                "review_streak": fc.review_streak,
                "next_review_at": fc.next_review_at.isoformat() if fc.next_review_at else None,
                "due": is_due,
            })
        total_reviews = s.query(ReviewHistoryRow).count()
        for r in s.query(ReviewHistoryRow).all():
            mode_dist[r.review_mode] = mode_dist.get(r.review_mode, 0) + 1
    return {
        "curves": curves,
        "tracked_concepts": len(curves),
        "due_count": due,
        "review_mode_distribution": mode_dist,
        "total_reviews": total_reviews,
    }


# --------------------------------------------------------------------------- #
# L4 知识工程
# --------------------------------------------------------------------------- #
def _difficulty_bucket(load: float) -> str:
    if load < 0.34:
        return "easy"
    if load < 0.67:
        return "medium"
    return "hard"


def _mermaid(concepts: list, relations: list[dict]) -> str:
    """轻量 Mermaid：节点过多时截断到 _MERMAID_MAX_NODES。"""
    def nid(cid: str) -> str:
        return cid.replace(":", "__").replace(".", "_").replace("-", "_")

    shown = concepts[:_MERMAID_MAX_NODES]
    shown_ids = {c.id for c in shown}
    lines = ["graph TD"]
    for c in shown:
        label = (c.names[0] if c.names else c.id).replace('"', "'")
        lines.append(f'  {nid(c.id)}["{label}"]')
    for e in relations:
        if e["from_id"] in shown_ids and e["to_id"] in shown_ids:
            lines.append(f'  {nid(e["from_id"])} -->|{e["type"]}| {nid(e["to_id"])}')
    return "\n".join(lines)


def get_layer_l4_state(db: RelationalStore) -> dict[str, Any]:
    """KG 列表 + 当前科目 KG 的概念难度分布 / 关系类型分布 / Mermaid 拓扑。"""
    graphs: list[dict[str, Any]] = []
    with db.session() as s:
        for kg in s.query(KnowledgeGraphRow).order_by(KnowledgeGraphRow.created_at.desc()).all():
            quality = (kg.quality_json or {}).get("overall") if kg.quality_json else None
            graphs.append({
                "kg_id": kg.kg_id, "subject_id": kg.subject_id, "version": kg.version,
                "node_count": kg.node_count, "edge_count": kg.edge_count,
                "quality": quality, "parent_kg_id": kg.parent_kg_id,
            })

    # 当前会话科目的 KG → 拓扑 + 分布
    ctx = _safe_ctx(db)
    kg_id = None
    if ctx is not None:
        kg_id = ctx.teaching_plan_id or _subject_kg(db, ctx.subject_id)
    elif graphs:
        kg_id = graphs[0]["kg_id"]

    concepts = _load_concepts(db, kg_id)
    diff_dist = {"easy": 0, "medium": 0, "hard": 0}
    for c in concepts:
        diff_dist[_difficulty_bucket(c.difficulty.cognitive_load_estimate)] += 1

    rel_types: dict[str, int] = {}
    relations: list[dict] = []
    if kg_id:
        with db.session() as s:
            for r in s.query(RelationRow).filter_by(kg_id=kg_id, deprecated=False).all():
                rel_types[r.type] = rel_types.get(r.type, 0) + 1
                relations.append({"from_id": r.from_id, "to_id": r.to_id, "type": r.type})

    return {
        "graphs": graphs,
        "active_kg_id": kg_id,
        "concept_count": len(concepts),
        "difficulty_distribution": diff_dist,
        "relation_types": rel_types,
        "mermaid": _mermaid(concepts, relations) if concepts else "",
    }


# --------------------------------------------------------------------------- #
# L5 学习者建模
# --------------------------------------------------------------------------- #
def get_layer_l5_state(db: RelationalStore) -> dict[str, Any]:
    """BKT 掌握度热力图数据 + 错误类型分布 + 当前认知负荷 + 画像版本。"""
    ctx = _safe_ctx(db)
    user_id = ctx.user_id if ctx else None

    bkt: list[dict[str, Any]] = []
    error_types: dict[str, int] = {}
    profile_version = None
    with db.session() as s:
        q = s.query(BKTParamRow)
        if user_id:
            q = q.filter_by(user_id=user_id)
        for r in q.order_by(BKTParamRow.p_mastery.desc()).limit(200).all():
            bkt.append({
                "concept_id": r.concept_id,
                "p_mastery": round(r.p_mastery, 3),
                "n_observations": r.n_observations,
            })
        rq = s.query(ReviewHistoryRow)
        if user_id:
            rq = rq.filter_by(user_id=user_id)
        for r in rq.all():
            for et in (r.error_types or []):
                error_types[et] = error_types.get(et, 0) + 1
        if user_id:
            prof = s.get(LearnerProfileRow, user_id)
            profile_version = prof.version if prof else None

    return {
        "user_id": user_id,
        "bkt": bkt,
        "bkt_count": len(bkt),
        "error_types": error_types,
        "current_cognitive_load": round(ctx.meta.current_cognitive_load, 3) if ctx else None,
        "profile_version": profile_version,
    }


# --------------------------------------------------------------------------- #
# L6 自适应教学
# --------------------------------------------------------------------------- #
def get_layer_l6_state(db: RelationalStore) -> dict[str, Any]:
    """当前策略状态机 + 心流曲线（recent_history 派生）。增益回路事件为瞬态未落库。"""
    ctx = _safe_ctx(db)
    if ctx is None:
        return {"status": "idle", "flow_series": [], "gain_loop": {"persisted": False}}

    flow_series = [
        h.get("flow_level") for h in ctx.recent_history if h.get("flow_level") is not None
    ]
    return {
        "status": ctx.status,
        "strategy": ctx.current_strategy,
        "strategy_state": ctx.current_strategy_state,
        "strategy_internal": dict(ctx.strategy_internal or {}),
        "cognitive_load": round(ctx.meta.current_cognitive_load, 3),
        "flow_series": flow_series[-20:],
        "gain_loop": {"persisted": False,
                      "note": "增益回路断裂/修复为运行时事件，未落库"},
    }


# --------------------------------------------------------------------------- #
# L7 交互层
# --------------------------------------------------------------------------- #
def get_layer_l7_state(db: RelationalStore) -> dict[str, Any]:
    """对话历史（最近交互）。digest 产物 / Obsidian 同步状态走文件系统，不在 DB。"""
    ctx = _safe_ctx(db)
    if ctx is None:
        return {"status": "idle", "dialogue": [], "turn_count": 0}

    dialogue = [
        {
            "concept_id": h.get("concept_id"),
            "answer": (h.get("answer") or "")[:120],
            "correctness": h.get("correctness"),
            "flow_level": h.get("flow_level"),
        }
        for h in ctx.recent_history[-15:]
        if "answer" in h or "correctness" in h
    ]
    return {
        "status": ctx.status,
        "dialogue": dialogue,
        "turn_count": len(ctx.recent_history),
        "artifacts": {"persisted": False, "note": "digest/Obsidian 产物在文件系统，非 DB"},
    }


# --------------------------------------------------------------------------- #
# PGFGA 正向增益
# --------------------------------------------------------------------------- #
def get_layer_pgfga_state(db: RelationalStore) -> dict[str, Any]:
    """心流趋势健康度（从最近心流序列派生）。防火墙/SDT 触发为运行时事件，未落库。"""
    ctx = _safe_ctx(db)
    if ctx is None:
        return {"status": "idle", "flow_trend": "unknown", "recent_flow": []}

    flow = [h.get("flow_level") for h in ctx.recent_history if h.get("flow_level") is not None]
    trend = "flat"
    if len(flow) >= 2:
        delta = flow[-1] - flow[0]
        trend = "rising" if delta > 0 else ("falling" if delta < 0 else "flat")
    return {
        "status": ctx.status,
        "recent_flow": flow[-20:],
        "flow_trend": trend,
        "current_flow_level": flow[-1] if flow else None,
        "firewall": {"persisted": False, "note": "非评判防火墙触发为运行时事件，未落库"},
        "sdt_signals": {"persisted": False, "note": "SDT 自主/胜任/归属信号未落库"},
    }


# 便于路由批量取用
LAYER_FUNCS = {
    "L1": get_layer_l1_state,
    "L2": get_layer_l2_state,
    "L3": get_layer_l3_state,
    "L4": get_layer_l4_state,
    "L5": get_layer_l5_state,
    "L6": get_layer_l6_state,
    "L7": get_layer_l7_state,
    "pgfga": get_layer_pgfga_state,
}
