"""backend.middleware.SessionManager 测试 —— spec 03 功能1（列表/切换/摘要/token/过期）。"""
from __future__ import annotations

import time

import pytest

from backend.middleware import SessionManager
from shared.errors import TutorError
from shared.storage import RelationalStore


@pytest.fixture
def store(tmp_path) -> RelationalStore:
    s = RelationalStore(f"sqlite:///{(tmp_path / 'tutor.db').as_posix()}")
    s.init_schema()
    return s


@pytest.fixture
def mgr(store) -> SessionManager:
    return SessionManager(store)


def _seed(mgr, user="yhn", subject="gaoshu", *, covered=None, mastered=None):
    ctx = mgr.store.create(user_id=user, subject_id=subject)
    if covered is not None:
        ctx.session_stats.concepts_covered = covered
        ctx.session_stats.concepts_mastered = mastered or []
        mgr.store.save(ctx)
    return ctx.session_id


def test_list_only_own_sessions(mgr):
    """spec 场景1：列出本人会话。"""
    _seed(mgr, "yhn", "gaoshu")
    _seed(mgr, "yhn", "ml")
    _seed(mgr, "other", "english")
    rows = mgr.list_sessions("yhn")
    assert len(rows) == 2
    assert {r["subject_id"] for r in rows} == {"gaoshu", "ml"}
    assert all({"summary", "last_active_at", "token_usage"} <= r.keys() for r in rows)


def test_switch_session_ownership(mgr):
    """spec 场景2（manager 部分）：加载目标会话 + 归属校验。"""
    sid = _seed(mgr, "yhn", "gaoshu")
    ctx = mgr.switch_session("yhn", sid)
    assert ctx.session_id == sid and ctx.subject_id == "gaoshu"
    # 非本人 → SESSION_NOT_FOUND（不泄露存在性）
    with pytest.raises(TutorError) as ei:
        mgr.switch_session("intruder", sid)
    assert ei.value.code == "SESSION_NOT_FOUND"


def test_auto_summarize(mgr):
    """spec 场景3：摘要含"学过 X 概念 / 薄弱 Y / 下一步 Z"，并落 session_summaries。"""
    sid = _seed(mgr, "yhn", "ml", covered=["c1", "c2", "c3"], mastered=["c1"])
    summary = mgr.summarize(sid)
    assert "学过 3 概念" in summary and "掌握 1" in summary and "薄弱 2" in summary
    assert "下一步" in summary
    # 落库后 list 可见
    row = next(r for r in mgr.list_sessions("yhn") if r["session_id"] == sid)
    assert row["summary"] == summary
    assert row["concepts_covered"] == ["c1", "c2", "c3"]


def test_token_usage(mgr):
    """spec 场景4：token 累计 input/output/total。"""
    sid = _seed(mgr, "yhn", "gaoshu")
    mgr.record_tokens(sid, input_tokens=120, output_tokens=80)
    mgr.record_tokens(sid, input_tokens=30, output_tokens=20)
    usage = mgr.token_usage(sid)
    assert usage == {"input_tokens": 150, "output_tokens": 100, "total_tokens": 250}


def test_cleanup_expired(mgr):
    """spec 场景5：超 7 天无活跃 → expired，列表不再显示。"""
    sid = _seed(mgr, "yhn", "gaoshu")
    future = time.time() + 8 * 24 * 3600  # 8 天后清理
    n = mgr.cleanup_expired(now=future)
    assert n == 1
    assert all(r["session_id"] != sid for r in mgr.list_sessions("yhn"))


def test_persistence_across_restart(mgr, store):
    """新 manager（模拟重启）仍读到同库已落摘要/token。"""
    sid = _seed(mgr, "yhn", "ml", covered=["a"], mastered=[])
    mgr.summarize(sid)
    mgr.record_tokens(sid, input_tokens=10, output_tokens=5)
    reborn = SessionManager(store)
    assert reborn.token_usage(sid)["total_tokens"] == 15
    assert next(r for r in reborn.list_sessions("yhn"))["summary"].startswith("学过 1 概念")
