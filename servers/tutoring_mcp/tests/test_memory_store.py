"""MemoryStore（L3 长期记忆）契约测试。

职责:
- record_review(user, concept, subject, accuracy, review_mode, error_types):
   * 写一行 review_history
   * 拉本 (user,concept) 历史 → 重新拟合 λ → upsert forgetting_curves
   * 写入 next_review_at = recommend_review_days(λ, 0.7)
- load_curve(user, concept) → ForgettingCurve（没记录 → 默认 lambda）
- get_due_reviews(user, subject_id, by_date) → 按 next_review_at 排序
- predict_current_recall(user, concept) → 实时 R(now)
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shared.models import Subject, User
from shared.storage import RelationalStore


@pytest.fixture
def db_setup(tmp_db: RelationalStore) -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ml", user_id="yhn", display_name="ML"))
        s.commit()
    return tmp_db


def test_record_review_writes_history(db_setup) -> None:
    from servers.tutoring_mcp.memory_store import MemoryStore
    from shared.models import ReviewHistoryRow

    store = MemoryStore(db_setup)
    store.record_review(
        user_id="yhn", concept_id="ml:1:bow", subject_id="ml",
        accuracy=0.8, review_mode="quick_quiz",
    )
    with db_setup.session() as s:
        rows = s.query(ReviewHistoryRow).filter_by(user_id="yhn").all()
    assert len(rows) == 1
    assert rows[0].accuracy == 0.8
    assert rows[0].review_mode == "quick_quiz"


def test_load_curve_default_when_missing(db_setup) -> None:
    from servers.tutoring_mcp.memory_store import MemoryStore
    from servers.tutoring_mcp.forgetting_curve import DEFAULT_LAMBDA

    store = MemoryStore(db_setup)
    curve = store.load_curve(user_id="yhn", concept_id="ml:1:bow")
    assert curve.lambda_param == DEFAULT_LAMBDA
    assert curve.n_data_points == 0
    assert curve.last_review_at is None


def test_record_three_reviews_updates_lambda(db_setup) -> None:
    """3 个数据点 → 触发拟合 → λ 与默认不同。"""
    from servers.tutoring_mcp.memory_store import MemoryStore

    store = MemoryStore(db_setup)
    now = datetime.utcnow()

    # 故意造一个明显高遗忘率的序列：4 天后准确率掉到 0.4
    samples = [
        (now - timedelta(days=10), 0.95),
        (now - timedelta(days=6), 0.65),
        (now, 0.35),
    ]
    for ts, acc in samples:
        store.record_review(
            user_id="yhn", concept_id="ml:1:bow", subject_id="ml",
            accuracy=acc, review_mode="quick_quiz",
            review_date=ts,
        )

    curve = store.load_curve(user_id="yhn", concept_id="ml:1:bow")
    assert curve.n_data_points == 3
    assert curve.lambda_param != pytest.approx(0.3)  # 默认值
    assert curve.r_squared is not None


def test_record_review_sets_next_review_at(db_setup) -> None:
    from servers.tutoring_mcp.memory_store import MemoryStore

    store = MemoryStore(db_setup)
    store.record_review(
        user_id="yhn", concept_id="ml:1:bow", subject_id="ml",
        accuracy=0.9, review_mode="quick_quiz",
    )
    curve = store.load_curve(user_id="yhn", concept_id="ml:1:bow")
    assert curve.next_review_at is not None
    assert curve.next_review_at > datetime.utcnow()


def test_predict_recall_decays_with_real_data(db_setup) -> None:
    from servers.tutoring_mcp.memory_store import MemoryStore

    store = MemoryStore(db_setup)
    store.record_review(
        user_id="yhn", concept_id="ml:1:bow", subject_id="ml",
        accuracy=0.9, review_mode="quick_quiz",
        review_date=datetime.utcnow() - timedelta(days=2),
    )
    r0 = store.predict_current_recall(user_id="yhn", concept_id="ml:1:bow", now=datetime.utcnow() - timedelta(days=2))
    r1 = store.predict_current_recall(user_id="yhn", concept_id="ml:1:bow", now=datetime.utcnow())
    r7 = store.predict_current_recall(user_id="yhn", concept_id="ml:1:bow", now=datetime.utcnow() + timedelta(days=5))
    assert r0 > r1 > r7
    assert 0 <= r7 <= 1


def test_get_due_reviews_returns_overdue_concepts(db_setup) -> None:
    """next_review_at <= now 的 concept 被列出。"""
    from servers.tutoring_mcp.memory_store import MemoryStore

    store = MemoryStore(db_setup)
    now = datetime.utcnow()

    # 记一笔几天前的复习；预测的 next_review_at 大约 1-2 天后（λ=0.3，target=0.7 → 1.2 天）
    # 让"过去 5 天前学的"现在 due
    store.record_review(
        user_id="yhn", concept_id="ml:1:bow", subject_id="ml",
        accuracy=0.7, review_mode="quick_quiz",
        review_date=now - timedelta(days=5),
    )
    # 未来的概念（刚学的，不该 due）
    store.record_review(
        user_id="yhn", concept_id="ml:1:bow_future", subject_id="ml",
        accuracy=0.9, review_mode="quick_quiz",
        review_date=now,
    )
    due = store.get_due_reviews(user_id="yhn", subject_id="ml", by_date=now)
    due_ids = [d.concept_id for d in due]
    assert "ml:1:bow" in due_ids
    assert "ml:1:bow_future" not in due_ids


def test_users_isolated(db_setup) -> None:
    """u1 的复习不影响 u2。"""
    from servers.tutoring_mcp.memory_store import MemoryStore
    from shared.models import User

    with db_setup.session() as s:
        s.add(User(id="u2"))
        s.commit()

    store = MemoryStore(db_setup)
    store.record_review(
        user_id="yhn", concept_id="x:1:a", subject_id="ml",
        accuracy=0.7, review_mode="quick_quiz",
    )
    other = store.load_curve(user_id="u2", concept_id="x:1:a")
    assert other.n_data_points == 0


def test_record_review_with_error_types(db_setup) -> None:
    from servers.tutoring_mcp.memory_store import MemoryStore
    from shared.models import ReviewHistoryRow

    store = MemoryStore(db_setup)
    store.record_review(
        user_id="yhn", concept_id="ml:1:bow", subject_id="ml",
        accuracy=0.3, review_mode="error_revisit",
        error_types=["concept_confusion", "symbol_mistake"],
    )
    with db_setup.session() as s:
        row = s.query(ReviewHistoryRow).filter_by(user_id="yhn").first()
        assert row.error_types == ["concept_confusion", "symbol_mistake"]
