"""L3 长期记忆持久化 — MemoryStore。

写入路径:
- record_review() → 写 review_history + 重拟合 forgetting_curve

读取路径:
- load_curve() → ForgettingCurve（无记录则默认）
- predict_current_recall() → R(now) 实时
- get_due_reviews() → next_review_at <= cutoff 的概念列表
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from shared.logging_config import get_logger
from shared.models import ForgettingCurveRow, ReviewHistoryRow
from shared.schemas import ForgettingCurve
from shared.storage import RelationalStore

from .forgetting_curve import (
    DEFAULT_LAMBDA,
    fit_lambda,
    predict_recall,
    recommend_review_days,
)

logger = get_logger("tutoring_mcp.memory_store")


_TARGET_RECALL = 0.7  # 多少召回率时应该被复习


@dataclass
class DueReview:
    concept_id: str
    subject_id: str
    next_review_at: datetime
    lambda_param: float
    n_data_points: int
    days_overdue: float


class MemoryStore:
    def __init__(self, db: RelationalStore) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # record
    # ------------------------------------------------------------------ #
    def record_review(
        self,
        *,
        user_id: str,
        concept_id: str,
        subject_id: str,
        accuracy: float,
        review_mode: str = "quick_quiz",
        error_types: list[str] | None = None,
        review_date: datetime | None = None,
        session_id: str | None = None,
    ) -> ForgettingCurve:
        """记一次复习 + 重新拟合遗忘曲线，返回更新后的 curve。"""
        now = review_date or datetime.utcnow()

        with self.db.session() as s:
            # 拿历史用于拟合
            prev = (
                s.query(ReviewHistoryRow)
                .filter_by(user_id=user_id, concept_id=concept_id)
                .order_by(ReviewHistoryRow.review_date.asc())
                .all()
            )
            # days_since_last
            if prev:
                last_at = max(r.review_date for r in prev)
                # SQLAlchemy 把 Date 列读成 datetime.date；统一处理
                if not isinstance(last_at, datetime):
                    last_at = datetime.combine(last_at, datetime.min.time())
                days_since = max(0, (now - last_at).days)
            else:
                days_since = 0

            # 新增 history row
            s.add(
                ReviewHistoryRow(
                    user_id=user_id,
                    concept_id=concept_id,
                    subject_id=subject_id,
                    review_date=now,
                    days_since_last=days_since,
                    accuracy=accuracy,
                    review_mode=review_mode,
                    error_types=error_types,
                    session_id=session_id,
                )
            )
            s.commit()

        # 拟合 λ 用所有历史点（含本次）
        with self.db.session() as s:
            rows = (
                s.query(ReviewHistoryRow)
                .filter_by(user_id=user_id, concept_id=concept_id)
                .order_by(ReviewHistoryRow.review_date.asc())
                .all()
            )

        # 把绝对时间转为相对第一次的"天数"作为 x 轴
        if rows:
            first_at = rows[0].review_date
            if not isinstance(first_at, datetime):
                first_at = datetime.combine(first_at, datetime.min.time())
            points: list[tuple[float, float]] = []
            for r in rows:
                rd = r.review_date
                if not isinstance(rd, datetime):
                    rd = datetime.combine(rd, datetime.min.time())
                points.append(((rd - first_at).total_seconds() / 86400.0, r.accuracy))
        else:
            points = []

        lam, r2 = fit_lambda(data_points=points)
        next_days = recommend_review_days(lambda_param=lam, target_recall=_TARGET_RECALL)
        next_at = now + timedelta(days=next_days)

        # upsert forgetting_curves
        with self.db.session() as s:
            curve = s.get(ForgettingCurveRow, (user_id, concept_id))
            if curve is None:
                curve = ForgettingCurveRow(
                    user_id=user_id, concept_id=concept_id, subject_id=subject_id,
                    lambda_param=lam,
                )
                s.add(curve)
            curve.subject_id = subject_id
            curve.lambda_param = lam
            curve.r_squared = r2
            curve.n_data_points = len(points)
            curve.last_review_at = now
            curve.next_review_at = next_at
            curve.review_streak = (curve.review_streak or 0) + (1 if accuracy >= 0.6 else 0)
            s.commit()

            result = ForgettingCurve(
                user_id=user_id, concept_id=concept_id,
                lambda_param=lam, r_squared=r2,
                n_data_points=len(points),
                last_review_at=now,
                next_review_at=next_at,
                review_streak=curve.review_streak,
            )

        logger.info(
            "memory.record_review",
            user_id=user_id, concept_id=concept_id,
            lambda_param=round(lam, 3), n=len(points),
            next_days=round(next_days, 2),
        )
        return result

    # ------------------------------------------------------------------ #
    # read
    # ------------------------------------------------------------------ #
    def load_curve(self, *, user_id: str, concept_id: str) -> ForgettingCurve:
        with self.db.session() as s:
            row = s.get(ForgettingCurveRow, (user_id, concept_id))
            if row is None:
                return ForgettingCurve(
                    user_id=user_id, concept_id=concept_id,
                    lambda_param=DEFAULT_LAMBDA,
                )
            return ForgettingCurve(
                user_id=user_id, concept_id=concept_id,
                lambda_param=row.lambda_param,
                r_squared=row.r_squared,
                n_data_points=row.n_data_points or 0,
                last_review_at=row.last_review_at,
                next_review_at=row.next_review_at,
                review_streak=row.review_streak or 0,
            )

    def predict_current_recall(
        self, *, user_id: str, concept_id: str, now: datetime | None = None,
    ) -> float:
        curve = self.load_curve(user_id=user_id, concept_id=concept_id)
        if curve.last_review_at is None:
            return 1.0  # 从未复习过：假装刚学（caller 应有别的信号判断）
        ref = now or datetime.utcnow()
        days = (ref - curve.last_review_at).total_seconds() / 86400.0
        return predict_recall(lambda_param=curve.lambda_param, days_elapsed=days)

    def get_due_reviews(
        self,
        *,
        user_id: str,
        subject_id: str | None = None,
        by_date: datetime | None = None,
    ) -> list[DueReview]:
        """next_review_at <= by_date 的所有 concept，按 overdue 倒序。"""
        cutoff = by_date or datetime.utcnow()
        with self.db.session() as s:
            q = s.query(ForgettingCurveRow).filter_by(user_id=user_id)
            if subject_id is not None:
                q = q.filter_by(subject_id=subject_id)
            rows = q.all()

        out: list[DueReview] = []
        for r in rows:
            if r.next_review_at is None:
                continue
            if r.next_review_at > cutoff:
                continue
            overdue_days = (cutoff - r.next_review_at).total_seconds() / 86400.0
            out.append(
                DueReview(
                    concept_id=r.concept_id,
                    subject_id=r.subject_id,
                    next_review_at=r.next_review_at,
                    lambda_param=r.lambda_param,
                    n_data_points=r.n_data_points or 0,
                    days_overdue=overdue_days,
                )
            )
        out.sort(key=lambda d: d.days_overdue, reverse=True)
        return out
