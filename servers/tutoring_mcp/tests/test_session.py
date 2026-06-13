"""SessionContext CRUD 契约测试。

SessionStore 职责:
- create(user_id, subject_id) → SessionContext + 落库
- load(session_id) → SessionContext（不存在抛 SESSION_NOT_FOUND）
- save(SessionContext) → 写回，更新 ended_at（status=completed/expired 时）
- 通过 sessions 表（context_json 列）持久化
"""
from __future__ import annotations

import pytest

from shared.errors import TutorError
from shared.models import Subject, User
from shared.storage import RelationalStore


@pytest.fixture
def db_setup(tmp_db: RelationalStore) -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="gaoshu", user_id="yhn", display_name="高数"))
        s.commit()
    return tmp_db


def test_create_returns_session_with_id_and_meta(db_setup: RelationalStore) -> None:
    from servers.tutoring_mcp.session import SessionStore

    store = SessionStore(db_setup)
    ctx = store.create(user_id="yhn", subject_id="gaoshu")
    assert ctx.session_id
    assert ctx.user_id == "yhn"
    assert ctx.subject_id == "gaoshu"
    assert ctx.status == "idle"
    assert ctx.meta.started_at is not None
    assert ctx.session_stats.total_questions_asked == 0


def test_create_persists_to_db(db_setup: RelationalStore) -> None:
    from servers.tutoring_mcp.session import SessionStore
    from shared.models import SessionRow

    store = SessionStore(db_setup)
    ctx = store.create(user_id="yhn", subject_id="gaoshu")
    with db_setup.session() as s:
        row = s.get(SessionRow, ctx.session_id)
        assert row is not None
        assert row.user_id == "yhn"


def test_load_round_trip_preserves_all_fields(db_setup: RelationalStore) -> None:
    from servers.tutoring_mcp.session import SessionStore

    store = SessionStore(db_setup)
    ctx = store.create(user_id="yhn", subject_id="gaoshu")
    ctx.status = "active"
    ctx.current_concept_id = "x:1.1:a"
    ctx.position_in_plan = 3
    ctx.session_stats.total_questions_asked = 5
    ctx.session_stats.correct_rate = 0.8
    store.save(ctx)

    reloaded = store.load(ctx.session_id)
    assert reloaded.status == "active"
    assert reloaded.current_concept_id == "x:1.1:a"
    assert reloaded.position_in_plan == 3
    assert reloaded.session_stats.total_questions_asked == 5
    assert reloaded.session_stats.correct_rate == pytest.approx(0.8)


def test_load_missing_raises(db_setup: RelationalStore) -> None:
    from servers.tutoring_mcp.session import SessionStore

    store = SessionStore(db_setup)
    with pytest.raises(TutorError) as exc:
        store.load("nonexistent-session")
    assert exc.value.code == "SESSION_NOT_FOUND"


def test_save_completed_status_sets_ended_at(db_setup: RelationalStore) -> None:
    from servers.tutoring_mcp.session import SessionStore
    from shared.models import SessionRow

    store = SessionStore(db_setup)
    ctx = store.create(user_id="yhn", subject_id="gaoshu")
    ctx.status = "completed"
    store.save(ctx)

    with db_setup.session() as s:
        row = s.get(SessionRow, ctx.session_id)
        assert row.ended_at is not None
        assert row.status == "completed"


def test_save_active_status_does_not_set_ended_at(db_setup: RelationalStore) -> None:
    from servers.tutoring_mcp.session import SessionStore
    from shared.models import SessionRow

    store = SessionStore(db_setup)
    ctx = store.create(user_id="yhn", subject_id="gaoshu")
    ctx.status = "active"
    store.save(ctx)

    with db_setup.session() as s:
        row = s.get(SessionRow, ctx.session_id)
        assert row.ended_at is None


def test_save_serializes_focus_and_stats(db_setup: RelationalStore) -> None:
    """嵌套对象（FocusState、SessionStats）也要正确序列化。"""
    from servers.tutoring_mcp.session import SessionStore

    store = SessionStore(db_setup)
    ctx = store.create(user_id="yhn", subject_id="gaoshu")
    ctx.focus.primary_concept = "x:1.1:a"
    ctx.focus.supporting_concepts = ["x:1.1:b", "x:1.1:c"]
    ctx.session_stats.concepts_covered = ["x:1.1:a"]
    ctx.session_stats.errors_by_type = {"concept_confusion": 2}
    store.save(ctx)

    reloaded = store.load(ctx.session_id)
    assert reloaded.focus.primary_concept == "x:1.1:a"
    assert reloaded.focus.supporting_concepts == ["x:1.1:b", "x:1.1:c"]
    assert reloaded.session_stats.errors_by_type == {"concept_confusion": 2}
