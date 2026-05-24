"""L3 复习调度 — 把"哪些概念该复习 + 怎么复习 + 排多久"集中算清楚。

priority(concept) = urgency × difficulty × recency_decay
- urgency      = 1 - predicted_recall
- difficulty   = concept.cognitive_load_estimate（已掌握难度）
- recency_decay = log(1 + days_overdue) / 2，让 overdue 越久越优先

按 priority 排序，依次填入 plan 直到 available_minutes 耗尽。

ReviewMode:
- 有最近错题            → error_revisit
- mastery > 0.7         → quick_quiz
- 0.4 < mastery ≤ 0.7   → concept_map
- mastery ≤ 0.4         → teach_back
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from shared.logging_config import get_logger
from shared.models import BKTParamRow, ConceptRow, ReviewHistoryRow
from shared.schemas import DailyReviewPlan, DailyReviewSection
from shared.storage import RelationalStore

from .memory_store import MemoryStore

logger = get_logger("tutoring_mcp.review_scheduler")


ReviewMode = Literal["quick_quiz", "concept_map", "teach_back", "error_revisit"]


def pick_review_mode(*, mastery: float, has_recent_errors: bool) -> ReviewMode:
    if has_recent_errors:
        return "error_revisit"
    if mastery > 0.7:
        return "quick_quiz"
    if mastery > 0.4:
        return "concept_map"
    return "teach_back"


@dataclass
class _Candidate:
    concept_id: str
    subject_id: str
    name: str
    mastery: float
    recall: float
    difficulty: float
    learning_time_min: int
    days_overdue: float
    has_recent_errors: bool
    last_review_at: datetime | None


def _gather_candidates(
    db: RelationalStore, user_id: str, subject_id: str, now: datetime,
) -> list[_Candidate]:
    mem = MemoryStore(db)
    due = mem.get_due_reviews(user_id=user_id, subject_id=subject_id, by_date=now)
    if not due:
        return []

    concept_ids = [d.concept_id for d in due]
    with db.session() as s:
        concepts = {
            c.id: c
            for c in s.query(ConceptRow).filter(ConceptRow.id.in_(concept_ids)).all()
        }
        bkt_rows = {
            (r.user_id, r.concept_id): r
            for r in s.query(BKTParamRow)
            .filter(
                BKTParamRow.user_id == user_id,
                BKTParamRow.concept_id.in_(concept_ids),
            )
            .all()
        }
        recent_err: dict[str, bool] = {}
        recent_cutoff = now - timedelta(days=7)
        rows = (
            s.query(ReviewHistoryRow)
            .filter(
                ReviewHistoryRow.user_id == user_id,
                ReviewHistoryRow.concept_id.in_(concept_ids),
                ReviewHistoryRow.review_date >= recent_cutoff,
                ReviewHistoryRow.error_types.isnot(None),
            )
            .all()
        )
        for r in rows:
            if r.error_types:
                recent_err[r.concept_id] = True

    candidates: list[_Candidate] = []
    for d in due:
        c = concepts.get(d.concept_id)
        if c is None:
            continue  # KG 中已被删
        bkt = bkt_rows.get((user_id, d.concept_id))
        mastery = bkt.p_mastery if bkt else 0.3  # 缺省
        recall = mem.predict_current_recall(
            user_id=user_id, concept_id=d.concept_id, now=now,
        )
        candidates.append(
            _Candidate(
                concept_id=d.concept_id,
                subject_id=d.subject_id,
                name=c.name_primary,
                mastery=mastery,
                recall=recall,
                difficulty=c.cognitive_load_estimate,
                learning_time_min=c.typical_learning_time_min,
                days_overdue=d.days_overdue,
                has_recent_errors=recent_err.get(d.concept_id, False),
                last_review_at=None,  # 调度器不需要
            )
        )
    return candidates


def _priority(c: _Candidate) -> float:
    urgency = 1.0 - c.recall
    difficulty = c.difficulty
    recency = math.log1p(max(0.0, c.days_overdue)) / 2.0
    return urgency * difficulty * (1.0 + recency)


def _estimated_minutes(mode: ReviewMode, base_learning_time: int) -> int:
    """复习时间 = 学习时长的折扣。"""
    if mode == "quick_quiz":
        return max(1, base_learning_time // 6)
    if mode == "concept_map":
        return max(2, base_learning_time // 3)
    if mode == "teach_back":
        return max(3, base_learning_time // 2)
    # error_revisit
    return max(2, base_learning_time // 3)


def schedule_review_plan(
    *,
    db: RelationalStore,
    user_id: str,
    subject_id: str,
    available_minutes: int = 60,
    now: datetime | None = None,
) -> DailyReviewPlan:
    """主入口：算出今天该复习的 N 个概念，每个用合适的 review_mode。"""
    ref = now or datetime.utcnow()
    candidates = _gather_candidates(db, user_id, subject_id, ref)

    candidates.sort(key=_priority, reverse=True)

    sections: list[DailyReviewSection] = []
    used_min = 0
    for cand in candidates:
        mode = pick_review_mode(
            mastery=cand.mastery, has_recent_errors=cand.has_recent_errors,
        )
        est = _estimated_minutes(mode, cand.learning_time_min)
        if used_min + est > available_minutes:
            continue
        sections.append(
            DailyReviewSection(
                concept_id=cand.concept_id,
                priority=_priority(cand),
                predicted_recall=cand.recall,
                estimated_minutes=est,
                review_mode=mode,
                urgency_context=(
                    f"{cand.days_overdue:.1f} 天前到期；预测召回率 "
                    f"{cand.recall * 100:.0f}%；当前 mastery {cand.mastery:.2f}"
                ),
            )
        )
        used_min += est

    tips: list[str] = []
    if sections:
        avg_recall = sum(s.predicted_recall for s in sections) / len(sections)
        if avg_recall < 0.4:
            tips.append("整体召回率偏低，今天优先做 teach_back / error_revisit。")
        elif avg_recall > 0.8:
            tips.append("整体掌握不错，可以用 quick_quiz 一遍过。")
        else:
            tips.append("混合 concept_map 与 quick_quiz，效率最高。")

    plan = DailyReviewPlan(
        user_id=user_id,
        subject_id=subject_id,
        date=ref.date().isoformat(),
        sections=sections,
        total_estimated_min=used_min,
        tips=tips,
    )
    logger.info(
        "scheduler.plan",
        user_id=user_id, subject_id=subject_id,
        candidates=len(candidates), picked=len(sections),
        budget_min=available_minutes, used_min=used_min,
    )
    return plan
