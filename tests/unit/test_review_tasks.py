"""复习队列 + 任务中心端点契约测试。

全部用临时库隔离，不触碰真实 data/tutor.db。复习队列依赖
forgetting_curves / review_history 表；任务中心依赖 tasks 表。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig


@pytest.fixture
def client(tmp_path):
    config = AppConfig(db_path=tmp_path / "tutor.db")
    app = create_app(config=config)
    with TestClient(app) as c:
        yield c, app


def test_review_due_empty_for_new_user(client) -> None:
    http, _app = client
    resp = http.get("/api/tutoring/users/empty-user/review-due")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user_id"] == "empty-user"
    assert data["items"] == []


def test_review_due_returns_overdue_concepts(client) -> None:
    from datetime import datetime, timedelta

    from shared.models import ForgettingCurveRow

    http, app = client
    store = app.state.store
    past = datetime.utcnow() - timedelta(days=3)
    with store.session() as s:
        s.add(ForgettingCurveRow(
            user_id="rv-user", concept_id="ml:1:x",
            subject_id="ml", lambda_param=0.9, r_squared=None,
            n_data_points=3, last_review_at=past,
            next_review_at=past, review_streak=1,
        ))
        # 未来才到期的不应返回
        s.add(ForgettingCurveRow(
            user_id="rv-user", concept_id="ml:2:y",
            subject_id="ml", lambda_param=0.9, r_squared=None,
            n_data_points=2, last_review_at=None,
            next_review_at=datetime.utcnow() + timedelta(days=7),
            review_streak=0,
        ))
        s.commit()

    resp = http.get("/api/tutoring/users/rv-user/review-due")
    data = resp.json()["data"]
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["concept_id"] == "ml:1:x"
    assert item["overdue_days"] >= 2.9
    assert item["n_data_points"] == 3


def test_record_review_advances_next_review_and_streak(client) -> None:
    http, app = client
    resp = http.post(
        "/api/tutoring/users/rv-user/review/record",
        json={
            "concept_id": "ml:1:x", "subject_id": "ml",
            "accuracy": 0.9, "review_mode": "quick_quiz",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]["curvature"]
    assert data["review_streak"] == 1
    assert data["next_review_at"] is not None
    # 再记一次，streak 增长
    resp2 = http.post(
        "/api/tutoring/users/rv-user/review/record",
        json={
            "concept_id": "ml:1:x", "subject_id": "ml",
            "accuracy": 1.0, "review_mode": "quick_quiz",
        },
    )
    assert resp2.json()["data"]["curvature"]["review_streak"] == 2


def test_record_review_rejects_invalid_accuracy(client) -> None:
    http, _app = client
    resp = http.post(
        "/api/tutoring/users/rv-user/review/record",
        json={"concept_id": "ml:1:x", "subject_id": "ml",
              "accuracy": 1.5, "review_mode": "quick_quiz"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "REVIEW_INVALID_ACCURACY"


def test_tasks_list_returns_recent_with_progress(client) -> None:
    http, app = client
    from backend.middleware.task_manager import TaskManager

    manager = app.state.tasks
    manager.submit("import_subject", lambda reporter: reporter.update(1.0, "完成"))
    import time

    time.sleep(0.2)
    resp = http.get("/api/tasks?limit=5")
    data = resp.json()["data"]
    assert len(data["items"]) >= 1
    assert data["items"][0]["kind"] == "import_subject"
    assert data["items"][0]["progress"] == 1.0
    assert "message" in data["items"][0]
