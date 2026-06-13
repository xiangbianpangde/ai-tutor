"""backend.middleware.task_manager —— 异步后台任务（M-007 / spec 02 场景4）。

长操作（build_kg / digest 产物生成）**不能在单个 HTTP 请求里同步跑**（会超时＝不及格）。
本层把它们丢进线程池后台执行，立即返回 task_id；进度/结果经 `GET /api/tasks/{id}` 轮询。

任务记录落 `tasks` 表（跨重启可查状态/结果——**进程内 future 不跨重启，运行中的任务重启不续**，
但已落库的状态/结果重启后仍可查）。
"""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from sqlalchemy import text

from ..core import get_logger

logger = get_logger("backend.tasks")

_DDL = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id    TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    state      TEXT NOT NULL,
    progress   REAL NOT NULL DEFAULT 0.0,
    message    TEXT,
    result     TEXT,
    error      TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
)
"""


class ProgressReporter:
    """任务体经此上报进度：``reporter.update(0.4, "构建中")``。"""

    def __init__(self, manager: TaskManager, task_id: str) -> None:
        self._mgr = manager
        self._task_id = task_id

    def update(self, progress: float, message: str | None = None) -> None:
        self._mgr._set_progress(self._task_id, max(0.0, min(1.0, progress)), message)


class TaskManager:
    """线程池后台任务 + SQLite 状态持久化。"""

    def __init__(self, db_engine, *, max_workers: int = 4) -> None:
        self._engine = db_engine
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task")
        self._futures: dict[str, Future] = {}
        with self._engine.begin() as conn:
            conn.execute(text(_DDL))

    def submit(self, kind: str, fn: Callable[[ProgressReporter], Any]) -> str:
        """登记并后台执行 ``fn(reporter)``，立即返回 task_id。"""
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO tasks (task_id, kind, state, progress, created_at, updated_at)"
                    " VALUES (:t, :k, 'pending', 0.0, :n, :n)"
                ),
                {"t": task_id, "k": kind, "n": now},
            )
        self._futures[task_id] = self._executor.submit(self._run, task_id, fn)
        return task_id

    def _run(self, task_id: str, fn: Callable[[ProgressReporter], Any]) -> None:
        self._update(task_id, state="running")
        try:
            result = fn(ProgressReporter(self, task_id))
            self._update(task_id, state="succeeded", progress=1.0, result=result)
        except Exception as exc:  # 任务失败记录而非上抛（轮询端取 error）
            logger.warning("task.failed", task_id=task_id, error=str(exc))
            self._update(task_id, state="failed", error=f"{type(exc).__name__}: {exc}")

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT task_id, kind, state, progress, message, result, error,"
                    " created_at, updated_at FROM tasks WHERE task_id = :t"
                ),
                {"t": task_id},
            ).first()
        if row is None:
            return None
        return {
            "task_id": row[0], "kind": row[1], "state": row[2], "progress": row[3],
            "message": row[4],
            "result": json.loads(row[5]) if row[5] else None,
            "error": row[6], "created_at": row[7], "updated_at": row[8],
        }

    def wait(self, task_id: str, timeout: float = 10.0) -> dict[str, Any] | None:
        """阻塞到任务结束（仅本进程已提交任务可等）。供测试/同步场景。"""
        fut = self._futures.get(task_id)
        if fut is not None:
            fut.result(timeout=timeout)
        return self.get(task_id)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    # ----- 内部 ------------------------------------------------------- #
    def _set_progress(self, task_id: str, progress: float, message: str | None) -> None:
        self._update(task_id, progress=progress, message=message)

    def _update(
        self,
        task_id: str,
        *,
        state: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        result: Any = None,
        error: str | None = None,
    ) -> None:
        sets = ["updated_at = :now"]
        params: dict[str, Any] = {"t": task_id, "now": time.time()}
        if state is not None:
            sets.append("state = :state")
            params["state"] = state
        if progress is not None:
            sets.append("progress = :progress")
            params["progress"] = progress
        if message is not None:
            sets.append("message = :message")
            params["message"] = message
        if result is not None:
            sets.append("result = :result")
            params["result"] = json.dumps(result, ensure_ascii=False, default=str)
        if error is not None:
            sets.append("error = :error")
            params["error"] = error
        with self._engine.begin() as conn:
            conn.execute(text(f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = :t"), params)
