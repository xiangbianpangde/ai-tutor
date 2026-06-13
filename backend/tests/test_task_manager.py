"""backend.middleware.TaskManager 测试 —— 异步提交/进度/失败/跨重启可查（M-007）。"""
from __future__ import annotations

import threading

import pytest

from backend.middleware import TaskManager
from shared.storage import RelationalStore


@pytest.fixture
def engine(tmp_path):
    return RelationalStore(f"sqlite:///{(tmp_path / 'tasks.db').as_posix()}").engine


@pytest.fixture
def mgr(engine):
    m = TaskManager(engine, max_workers=2)
    yield m
    m.shutdown()


def test_submit_returns_before_completion(mgr):
    """submit 立即返回 task_id，任务还在跑（不阻塞——单 HTTP 不会超时）。"""
    gate = threading.Event()

    def job(reporter):
        reporter.update(0.5, "半程")
        gate.wait(timeout=5)
        return {"answer": 42}

    tid = mgr.submit("demo", job)
    rec = mgr.get(tid)
    assert rec is not None and rec["state"] in ("pending", "running")
    assert rec["result"] is None  # 尚未完成
    gate.set()
    final = mgr.wait(tid, timeout=5)
    assert final["state"] == "succeeded"
    assert final["progress"] == 1.0
    assert final["result"] == {"answer": 42}


def test_progress_is_queryable(mgr):
    def job(reporter):
        for p in (0.2, 0.6, 0.9):
            reporter.update(p, f"step {p}")
        return "done"

    final = mgr.wait(mgr.submit("demo", job))
    assert final["state"] == "succeeded" and final["progress"] == 1.0


def test_failure_records_error(mgr):
    def job(reporter):
        raise ValueError("boom")

    final = mgr.wait(mgr.submit("demo", job))
    assert final["state"] == "failed"
    assert "ValueError" in final["error"] and "boom" in final["error"]
    assert final["result"] is None


def test_get_unknown_returns_none(mgr):
    assert mgr.get("task-nope") is None


def test_persisted_across_restart(mgr, engine):
    """新 TaskManager（模拟重启）仍可查同库已完成任务的状态/结果。"""
    tid = mgr.submit("demo", lambda r: {"x": 1})
    mgr.wait(tid)
    reborn = TaskManager(engine)
    try:
        rec = reborn.get(tid)
        assert rec["state"] == "succeeded" and rec["result"] == {"x": 1}
    finally:
        reborn.shutdown()
