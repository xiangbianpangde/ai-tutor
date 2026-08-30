"""薄弱概念诊断端点契约测试（/api/tutoring/users/{id}/weak-concepts）。

用真实 create_app + lifespan 初始化的 store 造数：
- 两条 BKT 行（一弱一强），一条会话 context_json（dict 形态，含 wrong/correct）。
覆盖：聚合排序、band 划分、可读名回退、context_json 的 dict/str 双形态、空用户。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from shared.models import BKTParamRow, SessionRow

USER = "diag-user"


@pytest.fixture
def client(tmp_path):
    """临时库隔离：db_path 指向 tmp_path，绝不触碰真实 data/tutor.db。"""
    from backend.config import AppConfig

    config = AppConfig(db_path=tmp_path / "diag-tutor.db")
    app = create_app(config=config)
    with TestClient(app) as c:
        yield c, app


def _seed(client: TestClient, ctx_json) -> None:
    store = client.app.state.store
    with store.session() as s:
        s.add(BKTParamRow(
            user_id=USER, concept_id="ml:1:overfitting",
            p_learn=0.15, p_guess=0.12, p_slip=0.08, p_init=0.05,
            p_mastery=0.2, n_observations=2, last_updated=datetime.utcnow(),
        ))
        s.add(BKTParamRow(
            user_id=USER, concept_id="ml:2:gradient",
            p_learn=0.15, p_guess=0.12, p_slip=0.08, p_init=0.05,
            p_mastery=0.9, n_observations=4, last_updated=datetime.utcnow(),
        ))
        s.add(SessionRow(
            id="sess-diag-1", user_id=USER, subject_id="ml",
            status="active", context_json=ctx_json, started_at=datetime.utcnow(),
        ))
        s.commit()


def test_weak_concepts_aggregate_sort_and_bands(client) -> None:
    http, _app = client
    _seed(http, {
        "recent_history": [
            {"concept_id": "ml:1:overfitting", "correctness": "incorrect",
             "timestamp": "2026-08-30T01:00:00", "was_self_corrected": False},
            {"concept_id": "ml:1:overfitting", "correctness": "partial",
             "timestamp": "2026-08-30T02:00:00", "was_self_corrected": True},
            {"concept_id": "ml:2:gradient", "correctness": "correct",
             "timestamp": "2026-08-30T03:00:00", "was_self_corrected": False},
        ],
    })

    body = http.get(f"/api/tutoring/users/{USER}/weak-concepts").json()["data"]
    assert body["overview"]["concepts"] == 2
    assert body["overview"]["weak"] == 1
    assert body["overview"]["mastered"] == 1
    assert body["overview"]["attempts"] == 3
    assert body["overview"]["wrong_attempts"] == 2

    items = body["items"]
    assert items[0]["concept_id"] == "ml:1:overfitting"  # 最薄弱在前
    assert items[0]["band"] == "weak"
    assert items[0]["attempts"] == 2
    assert items[0]["wrong_attempts"] == 2
    assert items[0]["last_wrong_at"] == "2026-08-30T02:00:00"
    assert items[1]["band"] == "mastered"
    assert items[1]["wrong_attempts"] == 0
    # 无 concepts 行时 label 回退为 concept_id
    assert items[0]["label"] == "ml:1:overfitting"


def test_weak_concepts_accepts_dict_context_json(client) -> None:
    """JSON 列在 ORM 层已是 dict：端点必须兼容 dict 与 str 两种形态。"""
    http, _app = client
    _seed(http, {"recent_history": [
        {"concept_id": "ml:1:overfitting", "correctness": "incorrect",
         "timestamp": "2026-08-30T01:00:00"},
    ]})
    body = http.get(f"/api/tutoring/users/{USER}/weak-concepts").json()["data"]
    assert body["overview"]["attempts"] == 1


def test_weak_concepts_empty_user_returns_zero_overview(client) -> None:
    http, _app = client
    body = http.get("/api/tutoring/users/nobody/weak-concepts").json()["data"]
    assert body["overview"] == {
        "concepts": 0, "mastered": 0, "consolidating": 0,
        "weak": 0, "attempts": 0, "wrong_attempts": 0,
    }
    assert body["items"] == []


def test_weak_concepts_ignores_other_users_sessions(client) -> None:
    http, _app = client
    _seed(http, {"recent_history": [
        {"concept_id": "ml:1:overfitting", "correctness": "incorrect",
         "timestamp": "2026-08-30T01:00:00"},
    ]})
    # 别的用户的会话不计入
    store = http.app.state.store
    from datetime import datetime

    with store.session() as s:
        s.add(SessionRow(
            id="sess-other", user_id="someone-else", subject_id="ml",
            status="active",
            context_json={"recent_history": [
                {"concept_id": "ml:1:overfitting", "correctness": "incorrect",
                 "timestamp": "2026-08-30T05:00:00"},
            ]},
            started_at=datetime.utcnow(),
        ))
        s.commit()
    body = http.get(f"/api/tutoring/users/{USER}/weak-concepts").json()["data"]
    assert body["overview"]["attempts"] == 1
