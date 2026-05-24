"""learning_insight 真实实现 — 聚合 BKT + review_history → InsightReport。

聚合逻辑:
- overall_mastery     = avg(BKT.p_mastery)
- concepts_mastered   = count(p_mastery > 0.85)
- concepts_learning   = count(0.4 < p_mastery <= 0.85)
- strengths           = top-K mastery 的概念名
- weaknesses          = bottom-K + 最近错误类型
- recommended_focus   = ReviewScheduler 出的下一份复习计划里前 5 个 concept 名
- next_review_plan    = ReviewMode → [concept_id]
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from shared.logging_config import get_logger
from shared.models import (
    BKTParamRow,
    ConceptRow,
    ReviewHistoryRow,
    Subject,
)
from shared.schemas import InsightReport
from shared.storage import RelationalStore

from .review_scheduler import schedule_review_plan

logger = get_logger("tutoring_mcp.insight")


_STRENGTH_THRESHOLD = 0.85
_LEARNING_THRESHOLD = 0.4
_WEAKNESS_THRESHOLD = 0.4


def build_insight(
    *,
    db: RelationalStore,
    user_id: str,
    subject_id: str,
    now: datetime | None = None,
) -> InsightReport:
    ref = now or datetime.utcnow()

    with db.session() as s:
        subject = s.get(Subject, subject_id)
        kg_id = subject.kg_id if subject else None
        # 拉本科目所有 concepts 名称（按 id）
        concepts_by_id: dict[str, ConceptRow] = {}
        if kg_id:
            concepts_by_id = {
                c.id: c
                for c in s.query(ConceptRow).filter_by(kg_id=kg_id).all()
            }

        # BKT
        bkt_rows = (
            s.query(BKTParamRow)
            .filter(BKTParamRow.user_id == user_id)
            .all()
        )
        # 过滤到本 subject（concept 在 kg 内）
        if concepts_by_id:
            bkt_rows = [r for r in bkt_rows if r.concept_id in concepts_by_id]

        # 最近 14 天的错误类型
        recent_errors = defaultdict(list)
        cutoff = ref - timedelta(days=14)
        err_rows = (
            s.query(ReviewHistoryRow)
            .filter(
                ReviewHistoryRow.user_id == user_id,
                ReviewHistoryRow.subject_id == subject_id,
                ReviewHistoryRow.review_date >= cutoff,
                ReviewHistoryRow.error_types.isnot(None),
            )
            .all()
        )
        for r in err_rows:
            if r.error_types:
                recent_errors[r.concept_id].extend(r.error_types)

    if not bkt_rows:
        return InsightReport(
            overall_mastery=0.0,
            concepts_mastered=0,
            concepts_learning=0,
            strengths=[],
            weaknesses=[],
            recommended_focus=[],
            next_review_plan={},
        )

    masteries = [r.p_mastery for r in bkt_rows]
    overall = sum(masteries) / len(masteries)
    mastered = sum(1 for m in masteries if m > _STRENGTH_THRESHOLD)
    learning = sum(
        1 for m in masteries if _LEARNING_THRESHOLD < m <= _STRENGTH_THRESHOLD
    )

    # strengths: top mastery 概念名（按 mastery 降序，前 5）
    sorted_high = sorted(
        bkt_rows, key=lambda r: r.p_mastery, reverse=True
    )[:5]
    strengths: list[str] = []
    for r in sorted_high:
        if r.p_mastery <= _STRENGTH_THRESHOLD:
            continue
        name = (
            concepts_by_id[r.concept_id].name_primary
            if r.concept_id in concepts_by_id
            else r.concept_id
        )
        strengths.append(name)

    # weaknesses
    sorted_low = sorted(bkt_rows, key=lambda r: r.p_mastery)[:5]
    weaknesses: list[dict] = []
    for r in sorted_low:
        if r.p_mastery >= _WEAKNESS_THRESHOLD:
            continue
        name = (
            concepts_by_id[r.concept_id].name_primary
            if r.concept_id in concepts_by_id
            else r.concept_id
        )
        weaknesses.append(
            {
                "concept": r.concept_id,
                "name": name,
                "mastery": round(r.p_mastery, 3),
                "root_cause": (
                    ", ".join(sorted(set(recent_errors[r.concept_id])))
                    if r.concept_id in recent_errors
                    else "mastery 偏低，但近期无明显错误类型"
                ),
            }
        )

    # 下一份复习计划
    plan = schedule_review_plan(
        db=db, user_id=user_id, subject_id=subject_id, available_minutes=30,
        now=ref,
    )
    recommended_focus: list[str] = []
    for sec in plan.sections[:5]:
        name = (
            concepts_by_id[sec.concept_id].name_primary
            if sec.concept_id in concepts_by_id
            else sec.concept_id
        )
        recommended_focus.append(name)

    next_review_plan: dict[str, list[str]] = defaultdict(list)
    for sec in plan.sections:
        next_review_plan[sec.review_mode].append(sec.concept_id)

    logger.info(
        "insight.done",
        user_id=user_id, subject_id=subject_id,
        overall_mastery=round(overall, 3),
        mastered=mastered, learning=learning,
        strengths_n=len(strengths), weaknesses_n=len(weaknesses),
    )
    return InsightReport(
        overall_mastery=round(overall, 3),
        concepts_mastered=mastered,
        concepts_learning=learning,
        strengths=strengths,
        weaknesses=weaknesses,
        recommended_focus=recommended_focus,
        next_review_plan=dict(next_review_plan),
    )
