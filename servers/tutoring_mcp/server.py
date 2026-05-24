"""tutoring-mcp FastMCP server 入口（Spine v2）。

实现的 tool:
- start_learning_session: 校验 KG + 建 session + 第一个 concept + 首个 action
- next_action:           走 engine.next_action
- respond:               走 engine.respond
- health:                自检

Stub（占位，待后续切片）:
- interrupt:           中断与意图分类
- checkpoint:          自评 vs 系统评的差距
- learning_insight:    跨会话学习报告
- generate_review_plan: L3 多因子复习调度
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from shared.errors import TutorError
from shared.logging_config import configure_logging, get_logger
from shared.models import (
    BKTParamRow,
    KnowledgeGraphRow,
    LearnerProfileRow,
    SessionRow,
    Subject,
)
from shared.models import ConceptRow as ConceptRowORM
from shared.models import RelationRow as RelationRowORM
from shared.schemas import (
    ColdStartAnswer,
    ColdStartProbeSet,
    ColdStartResult,
    Concept,
    DailyReviewPlan,
    InsightReport,
    InterruptResult,
    LearnerProfile,
    LearningPlan,
    LearningProgress,
    ResponseResult,
    SessionStartResult,
    TeachingAction,
)
from shared.storage import RelationalStore

from . import cold_start
from . import learning_plan as lp
from .bkt_store import BKTStore
from .engine import TeachingEngine
from .insight import build_insight
from .review_scheduler import schedule_review_plan
from .session import SessionStore

configure_logging()
logger = get_logger("tutoring_mcp.server")

mcp: FastMCP = FastMCP("tutoring-mcp")


# --------------------------------------------------------------------------- #
# 依赖装配
# --------------------------------------------------------------------------- #


def _db() -> RelationalStore:
    return RelationalStore.from_env()


def _llm():
    """有 DEEPSEEK_API_KEY 则用 DeepSeek（启用判分/诊断/内容生成），否则 Stub（模板兜底）。"""
    from shared.llm_client import StubLLMProvider

    try:
        from shared.providers.deepseek import DeepSeekProvider

        return DeepSeekProvider.from_env() or StubLLMProvider()
    except Exception:  # noqa: BLE001 — provider 构建失败不应阻断 server
        return StubLLMProvider()


def _engine(db: RelationalStore) -> TeachingEngine:
    return TeachingEngine(db=db, sessions=SessionStore(db), llm=_llm())


# --------------------------------------------------------------------------- #
# 教学路径排序：拓扑序（按 prerequisite_strong）
# --------------------------------------------------------------------------- #


def _chapter_key(concept_id: str) -> tuple[int, ...]:
    """从 concept.id 取出章节段做数值元组排序。

    `{subject}:{chapter}.{section}.{index}:{slug}` → (chapter, section, index)
    保证 "1:..." 排在 "1.1:..." 之前（父节点 < 子节点）。
    """
    try:
        chapter_part = concept_id.split(":")[1]
        return tuple(int(x) for x in chapter_part.split("."))
    except (IndexError, ValueError):
        return (10**9,)  # 异常 id 排到最后


def _topological_order(db: RelationalStore, kg_id: str) -> list[ConceptRowORM]:
    """对 KG 中的概念按 prerequisite_strong 边做拓扑排序。

    入度为 0 的先讲；tie-break 按章节号数值序（父节点 < 子节点）。
    """
    with db.session() as s:
        nodes = s.query(ConceptRowORM).filter_by(kg_id=kg_id).all()
        if not nodes:
            return []
        edges = (
            s.query(RelationRowORM)
            .filter_by(kg_id=kg_id, type="prerequisite_strong", deprecated=False)
            .all()
        )

    indeg: dict[str, int] = {n.id: 0 for n in nodes}
    outgoing: dict[str, list[str]] = {n.id: [] for n in nodes}
    for e in edges:
        if e.from_id in indeg and e.to_id in indeg:
            indeg[e.to_id] += 1
            outgoing[e.from_id].append(e.to_id)

    by_id = {n.id: n for n in nodes}
    ready = sorted([nid for nid, d in indeg.items() if d == 0], key=_chapter_key)
    out: list[ConceptRowORM] = []
    while ready:
        cur = ready.pop(0)
        out.append(by_id[cur])
        for nxt in outgoing[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
        ready.sort(key=_chapter_key)
    # 残留（有环）按章节号追加
    seen = {x.id for x in out}
    remaining = sorted([n.id for n in nodes if n.id not in seen], key=_chapter_key)
    for nid in remaining:
        out.append(by_id[nid])
    return out


# --------------------------------------------------------------------------- #
# 冷启动摸底 helpers
# --------------------------------------------------------------------------- #


def _resolve_kg_id(db: RelationalStore, subject_id: str) -> str:
    """校验 subject + kg，返回 kg_id；缺失则抛对应 TutorError。"""
    with db.session() as s:
        subj = s.get(Subject, subject_id)
        if subj is None:
            raise TutorError("SUBJECT_NOT_FOUND", hint=subject_id)
        if not subj.kg_id:
            raise TutorError(
                "KG_NOT_BUILT",
                hint=f"subject={subject_id} 还没有关联 KG。先 build_knowledge_graph 并写回 subject.kg_id",
            )
        kg = s.get(KnowledgeGraphRow, subj.kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=subj.kg_id)
        return kg.kg_id


def _load_kg_concepts(db: RelationalStore, kg_id: str) -> list[Concept]:
    with db.session() as s:
        rows = s.query(ConceptRowORM).filter_by(kg_id=kg_id).all()
        return [Concept.model_validate(r.full_json) for r in rows]


def _has_assessment(db: RelationalStore, user_id: str, concept_ids: list[str]) -> bool:
    """该用户在本 KG 概念上是否已有 BKT 记录（先验或真实观测）。"""
    if not concept_ids:
        return False
    with db.session() as s:
        n = (
            s.query(BKTParamRow)
            .filter(BKTParamRow.user_id == user_id, BKTParamRow.concept_id.in_(concept_ids))
            .count()
        )
    return n > 0


def _seed_learner_profile(db: RelationalStore, user_id: str, result: ColdStartResult) -> None:
    """把摸底画像初值写入 LearnerProfileRow（合并，不清空其它字段）。"""
    with db.session() as s:
        row = s.get(LearnerProfileRow, user_id)
        if row is None:
            profile = LearnerProfile(user_id=user_id)
            row = LearnerProfileRow(
                user_id=user_id,
                profile_json=profile.model_dump(mode="json"),
            )
            s.add(row)
        data = dict(row.profile_json or {})
        cog = dict(data.get("cognitive") or {})
        cog["abstract_tolerance"] = result.abstract_tolerance_initial
        cog["transfer_ability"] = result.transfer_ability_initial
        data["cognitive"] = cog
        meta = dict(data.get("metacognitive") or {})
        meta["self_assessment_accuracy"] = result.self_assessment_accuracy_initial
        data["metacognitive"] = meta
        row.profile_json = data
        row.last_updated = datetime.utcnow()
        s.commit()


# --------------------------------------------------------------------------- #
# 多 Session 学习计划 helpers
# --------------------------------------------------------------------------- #


def _ordered_concepts(db: RelationalStore, kg_id: str) -> list[Concept]:
    rows = _topological_order(db, kg_id)
    return [Concept.model_validate(r.full_json) for r in rows]


def _concept_names(db: RelationalStore, kg_id: str) -> dict[str, str]:
    with db.session() as s:
        rows = s.query(ConceptRowORM).filter_by(kg_id=kg_id).all()
        out: dict[str, str] = {}
        for r in rows:
            names = (r.full_json or {}).get("names") or []
            out[r.id] = names[0] if names else r.id
        return out


def _get_or_build_plan(
    db: RelationalStore, user_id: str, subject_id: str, kg_id: str
) -> LearningPlan:
    store = lp.LearningPlanStore(db)
    plan = store.load(user_id, subject_id)
    if plan is None or plan.kg_id != kg_id:
        plan = lp.build_plan(
            user_id=user_id, subject_id=subject_id, kg_id=kg_id,
            ordered_concepts=_ordered_concepts(db, kg_id),
        )
        store.save(plan)
    return plan


def _progress_for(
    db: RelationalStore, user_id: str, subject_id: str, kg_id: str
) -> LearningProgress:
    plan = _get_or_build_plan(db, user_id, subject_id, kg_id)
    bkt = BKTStore(db)
    return lp.compute_progress(
        plan=plan,
        mastery_of=lambda cid: bkt.load(user_id, cid).p_mastery,
        name_of=_concept_names(db, kg_id),
    )


def _plan_to_dict(plan: LearningPlan, progress: LearningProgress) -> dict[str, Any]:
    """把计划 + 进度合成 SessionStartResult.teaching_plan 的 dict。"""
    prog_by_phase = {p.phase: p for p in progress.phases}
    phases = []
    for ph in plan.phases:
        pr = prog_by_phase.get(ph.phase)
        phases.append({
            "phase": ph.phase,
            "title": ph.title,
            "concepts": ph.concept_ids,
            "estimated_hours": ph.estimated_hours,
            "status": pr.status if pr else "pending",
            "concepts_mastered": pr.concepts_mastered if pr else 0,
            "concepts_total": len(ph.concept_ids),
        })
    return {
        "phases": phases,
        "total_concepts": plan.total_concepts,
        "estimated_hours": plan.estimated_hours,
        "concepts_mastered": progress.concepts_mastered,
        "overall_mastery_ratio": progress.overall_mastery_ratio,
        "current_phase": progress.current_phase,
    }


def _progress_sentence(progress: LearningProgress) -> str:
    if progress.concepts_total == 0:
        return "知识图谱里还没有概念。"
    if progress.completed:
        return f"本科目 {progress.concepts_total} 个概念已全部掌握 🎉 可以做综合复习了。"
    head = f"已掌握 {progress.concepts_mastered}/{progress.concepts_total} 个概念。"
    if progress.current_phase is not None:
        head += f"当前在 Phase {progress.current_phase}：{progress.current_phase_title}。"
    if progress.next_concept_name:
        head += f"今天从【{progress.next_concept_name}】继续。"
    return head


def _latest_open_session(
    db: RelationalStore, user_id: str, subject_id: str
) -> str | None:
    """最近一个未结束（active/interrupted）的会话 id，用于真正的"续学"。"""
    with db.session() as s:
        row = (
            s.query(SessionRow)
            .filter(
                SessionRow.user_id == user_id,
                SessionRow.subject_id == subject_id,
                SessionRow.status.in_(["active", "interrupted"]),
            )
            .order_by(SessionRow.started_at.desc())
            .first()
        )
        return row.id if row else None


# --------------------------------------------------------------------------- #
# Tools — 已实现
# --------------------------------------------------------------------------- #


@mcp.tool()
async def cold_start_probe(
    user_id: str,
    subject_id: str,
    num_questions: int = 10,
) -> ColdStartProbeSet:
    """冷启动摸底第 1 步：出一组跨难度摸底题。

    选 num_questions 个代表性概念（默认 10，分布 basic/current/abstract ≈ 3/4/3），
    每题让学生一句话作答 + 自评。学生答完后调 submit_cold_start 落库。

    若该用户在本科目已有 BKT 记录 → already_assessed=True 且不再出题。
    """
    db = _db()
    db.init_schema()
    kg_id = _resolve_kg_id(db, subject_id)
    concepts = _load_kg_concepts(db, kg_id)
    if not concepts:
        raise TutorError("KG_NOT_BUILT", hint=f"KG {kg_id} 没有 concept")

    if _has_assessment(db, user_id, [c.id for c in concepts]):
        return ColdStartProbeSet(
            user_id=user_id, subject_id=subject_id, kg_id=kg_id,
            probes=[], already_assessed=True,
        )

    selected = cold_start.select_probe_concepts(concepts, n=max(1, num_questions))
    probes = [cold_start.build_probe(c) for c in selected]
    logger.info("cold_start.probe", user_id=user_id, subject_id=subject_id, n=len(probes))
    return ColdStartProbeSet(
        user_id=user_id, subject_id=subject_id, kg_id=kg_id, probes=probes,
    )


@mcp.tool()
async def submit_cold_start(
    user_id: str,
    subject_id: str,
    answers: list[dict[str, Any]],
) -> ColdStartResult:
    """冷启动摸底第 2 步：判分 → 种 BKT 先验 + 写画像初值。

    answers 每项: {concept_id, answer, self_report in (sure/unsure/dont_know)}。
    答对的概念种到"已掌握"先验，start_learning_session/next_action 会跳过它们。
    """
    db = _db()
    db.init_schema()
    kg_id = _resolve_kg_id(db, subject_id)

    parsed = [ColdStartAnswer.model_validate(a) for a in answers]
    concepts = _load_kg_concepts(db, kg_id)
    by_id = {c.id: c for c in concepts}
    # 只对本 KG 里存在的概念出题判分
    probe_concepts = [by_id[a.concept_id] for a in parsed if a.concept_id in by_id]
    probes = [cold_start.build_probe(c) for c in probe_concepts]

    scorer = _engine(db).scorer  # 复用 engine 的判分器（与教学一致）
    result = cold_start.grade_assessment(
        probes=probes, answers=parsed, concepts_by_id=by_id, scorer=scorer,
    )

    # 落库：BKT 先验 + 画像初值
    bkt = BKTStore(db)
    for concept_id, mastery in result.mastery_priors.items():
        bkt.seed_prior(user_id=user_id, concept_id=concept_id, mastery=mastery)
    _seed_learner_profile(db, user_id, result)

    logger.info(
        "cold_start.submit",
        user_id=user_id, subject_id=subject_id,
        graded=result.probes_graded, mastered=len(result.seeded_mastered),
        level=result.recommended_starting_level,
    )
    return result


@mcp.tool()
async def start_learning_session(
    user_id: str,
    subject_id: str,
    goal: Literal["48h_sprint", "semester_study", "exam_review", "quick_overview"] = "48h_sprint",
    available_hours: int | None = None,
) -> SessionStartResult:
    """开启一次**新**学习会话。

    流程: 校验 subject.kg_id → 取/建持久化 LearningPlan（按章节切 Phase）→
          新建 session → engine.next_action（跳过已掌握）给首个动作。

    跨 Session：计划与进度持久化；已掌握概念（冷启动先验或往期学习）被 next_action
    自动跳过。teaching_plan 反映各 Phase 完成度；pre_session_insight 给进度摘要。
    想"续上次会话"用 resume_learning；只想看进度用 get_learning_progress。
    """
    db = _db()
    db.init_schema()
    kg_id = _resolve_kg_id(db, subject_id)

    ordered = _topological_order(db, kg_id)
    if not ordered:
        raise TutorError("KG_NOT_BUILT", hint=f"KG {kg_id} 没有 concept")

    plan = _get_or_build_plan(db, user_id, subject_id, kg_id)
    progress = _progress_for(db, user_id, subject_id, kg_id)

    sessions = SessionStore(db)
    ctx = sessions.create(user_id=user_id, subject_id=subject_id)
    ctx.current_concept_id = ordered[0].id
    ctx.position_in_plan = 0
    ctx.status = "active"
    ctx.teaching_plan_id = kg_id
    sessions.save(ctx)

    assessed = _has_assessment(db, user_id, [n.id for n in ordered])
    if not assessed:
        pre_insight: str | None = (
            "尚未做冷启动摸底——先调 cold_start_probe 能跳过已掌握内容，省下重复学习时间。"
        )
    else:
        pre_insight = _progress_sentence(progress)

    engine = _engine(db)
    first_action = engine.next_action(ctx.session_id)

    logger.info(
        "session.start",
        session_id=ctx.session_id, subject_id=subject_id,
        total_concepts=plan.total_concepts,
        mastered=progress.concepts_mastered, phases=len(plan.phases),
    )

    return SessionStartResult(
        session_id=ctx.session_id,
        teaching_plan=_plan_to_dict(plan, progress),
        current_action=first_action,
        pre_session_insight=pre_insight,
    )


@mcp.tool()
async def get_learning_progress(user_id: str, subject_id: str) -> LearningProgress:
    """查看跨 Session 学习进度（不开会话）：我学到哪了 / 明天从哪继续。

    返回：总体掌握比例、各 Phase 完成度、当前 Phase、下一个该学的概念。
    """
    db = _db()
    db.init_schema()
    kg_id = _resolve_kg_id(db, subject_id)
    return _progress_for(db, user_id, subject_id, kg_id)


@mcp.tool()
async def resume_learning(
    user_id: str,
    subject_id: str,
    goal: Literal["48h_sprint", "semester_study", "exam_review", "quick_overview"] = "48h_sprint",
) -> SessionStartResult:
    """续学：接着上次的进度继续。

    - 若有未结束（active/interrupted）的会话 → 直接复用它（保留历史/策略状态）。
    - 否则新建会话，定位到第一个未掌握的概念（已掌握的被引擎跳过）。
    pre_session_insight 给出"已掌握 N/M、当前 Phase、今天从【X】继续"。
    """
    db = _db()
    db.init_schema()
    kg_id = _resolve_kg_id(db, subject_id)

    ordered = _topological_order(db, kg_id)
    if not ordered:
        raise TutorError("KG_NOT_BUILT", hint=f"KG {kg_id} 没有 concept")

    plan = _get_or_build_plan(db, user_id, subject_id, kg_id)
    progress = _progress_for(db, user_id, subject_id, kg_id)

    sessions = SessionStore(db)
    existing = _latest_open_session(db, user_id, subject_id)
    resumed = existing is not None
    if existing is not None:
        ctx = sessions.load(existing)
        ctx.status = "active"
        if not ctx.teaching_plan_id:
            ctx.teaching_plan_id = kg_id
        sessions.save(ctx)
        sid = existing
    else:
        ctx = sessions.create(user_id=user_id, subject_id=subject_id)
        ctx.current_concept_id = ordered[0].id
        ctx.position_in_plan = 0
        ctx.status = "active"
        ctx.teaching_plan_id = kg_id
        sessions.save(ctx)
        sid = ctx.session_id

    engine = _engine(db)
    action = engine.next_action(sid)

    insight = _progress_sentence(progress)
    if resumed:
        insight = "接着上次的会话继续。" + insight

    logger.info(
        "session.resume",
        session_id=sid, subject_id=subject_id, resumed=resumed,
        mastered=progress.concepts_mastered, total=progress.concepts_total,
    )

    return SessionStartResult(
        session_id=sid,
        teaching_plan=_plan_to_dict(plan, progress),
        current_action=action,
        pre_session_insight=insight,
    )


@mcp.tool()
async def next_action(session_id: str) -> TeachingAction:
    """获取下一个教学动作。"""
    db = _db()
    return _engine(db).next_action(session_id)


@mcp.tool()
async def advance(session_id: str) -> TeachingAction:
    """讲解/展示步骤之后"继续下一步"。

    用法约定：next_action / start_learning_session 给出一个动作后——
    - 动作是讲解/示例/揭示答案/反思（explain/show_example/reveal_answer/reflection）→ 调 advance 继续；
    - 动作是提问/练习/请解释/提示（ask_question/give_exercise/request_explanation/provide_hint）→ 调 respond 作答。
    advance 会推进策略的纯展示态（如 reduction 的 INTRO→EXPLAIN→CHECK、jiangjie 的 GOAL→REDUCE）。
    """
    db = _db()
    return _engine(db).advance(session_id)


@mcp.tool()
async def respond(session_id: str, answer: str) -> ResponseResult:
    """提交学生的回答；返回判分 + 反馈 + mastery 变化。"""
    db = _db()
    return _engine(db).respond(session_id, answer)


@mcp.tool()
async def health() -> dict[str, Any]:
    """轻量自检：DB 可达 + session 数。"""
    db = _db()
    try:
        from shared.models import SessionRow

        with db.session() as s:
            n = s.query(SessionRow).count()
        return {
            "ok": True,
            "server": "tutoring-mcp",
            "version": "0.1.0",
            "session_count": n,
            "db_url": db.url,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --------------------------------------------------------------------------- #
# Tools — stub（待后续切片）
# --------------------------------------------------------------------------- #


@mcp.tool()
async def interrupt(session_id: str, question: str) -> InterruptResult:
    """学生中途打断。

    流程:
    1. 保存 SessionContext.interrupt_checkpoint
    2. IntentClassifier 分 5 类
       (concept_question / prereq_gap / pace_complaint / distraction / cognitive_overload)
    3. 不同分支不同响应
    4. 反馈过 PGFGA 防火墙
    5. 返回 InterruptResult.resume_prompt 让学生回来

    Returns: InterruptResult{type, content, checkpoint_saved, resume_prompt, suggested_action}
    """
    db = _db()
    return _engine(db).handle_interrupt(session_id, question)


@mcp.tool()
async def checkpoint(
    session_id: str,
    kind: Literal["self_summary", "test_result"] = "self_summary",
    content: str | None = None,
) -> dict[str, Any]:
    """阶段检查点：学生自评 vs BKT 实际 → 元认知更新。

    流程:
    1. 收集本会话涉及的 concepts（session_stats.concepts_covered 或本用户全 BKT）
    2. LLM 把自评文本映射到 0-1（StubLLM 时降级到关键词启发式）
    3. accuracy = 1 - |self - actual|
    4. EMA 更新 LearnerProfile.metacognitive.self_assessment_accuracy
    5. 返回 current_mastery_map + suggestions

    Returns: dict{self_assessment_accuracy, self_score, actual_mastery_avg,
                  current_mastery_map, cognitive_load, suggestions}
    """
    db = _db()
    return _engine(db).handle_checkpoint(session_id, kind=kind, content=content)


@mcp.tool()
async def learning_insight(user_id: str, subject_id: str) -> InsightReport:
    """学习报告：跨会话聚合 BKT + review_history。

    返回:
    - overall_mastery, concepts_mastered/learning/unknown
    - strengths (mastery > 0.85)
    - weaknesses (mastery < 0.4 + 错误类型)
    - recommended_focus (下一份复习计划前 5 个概念名)
    - next_review_plan: dict[review_mode, [concept_id]]
    """
    db = _db()
    return build_insight(db=db, user_id=user_id, subject_id=subject_id)


@mcp.tool()
async def generate_review_plan(
    user_id: str,
    subject_id: str,
    available_time_today_min: int = 60,
) -> DailyReviewPlan:
    """每日复习计划：基于个性化遗忘曲线 + 多因子优先级调度。

    流程: 收集 due_reviews → priority = urgency × difficulty × recency_decay
           → 按 budget 取前 N → 自动选 ReviewMode
    """
    db = _db()
    return schedule_review_plan(
        db=db,
        user_id=user_id,
        subject_id=subject_id,
        available_minutes=available_time_today_min,
    )


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #


def main() -> None:
    import sys

    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    logger.info("tutoring_mcp.start", transport=transport)
    if transport == "http":
        mcp.run(transport="sse", host="0.0.0.0", port=8002)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
