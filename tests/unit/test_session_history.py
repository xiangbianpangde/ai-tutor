"""会话历史回放端点契约测试（GET session-history）。

临时库隔离。覆盖：跨会话聚合 + 概览统计 + 时间倒序 + 概念名回填 + 空用户。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig

USER = "hist-user"


@pytest.fixture
def client(tmp_path):
    config = AppConfig(db_path=tmp_path / "tutor.db")
    app = create_app(config=config)
    with TestClient(app) as c:
        yield c, app


def _seed(client, sessions) -> None:
    from shared.models import ConceptRow, SessionRow

    http, app = client
    store = app.state.store
    with store.session() as s:
        s.add(ConceptRow(
            id="ml:1:ml_basics", kg_id="kg-1", base_id="ml:1:ml_basics",
            name_primary="机器学习基础", names_json=["机器学习基础"],
            category="definition", definition="定义", informal_description="",
            abstract_level=0.3, bloom_level="remember", domain="ml",
            cognitive_load_estimate=0.3, typical_learning_time_min=15,
            prereq_count=0, prereq_max_depth=0, formula_density=0.0,
            coupling=0.0, confidence=0.9, created_at=datetime.utcnow(),
            full_json={"id": "ml:1:ml_basics", "names": ["机器学习基础"],
                       "category": "definition", "definition": "定义",
                       "informal_description": "", "attributes": {},
                       "classification": {"bloom_level": "remember",
                                          "abstract_level": 0.3, "domain": "ml",
                                          "cross_domain_tags": []},
                       "difficulty": {"prereq_count": 0, "prereq_max_depth": 0,
                                      "formula_density": 0.3, "coupling": 0.3,
                                      "cognitive_load_estimate": 0.4,
                                      "typical_learning_time_min": 15},
                       "examples": [], "counter_examples": [],
                       "common_misconceptions": [], "keywords": [],
                       "embedding": None, "sources": [], "confidence": 0.9},
        ))
        for sid, ctx, started in sessions:
            s.add(SessionRow(
                id=sid, user_id=USER, subject_id="ml",
                status="active", context_json=ctx, started_at=started,
            ))
        s.commit()


def test_session_history_aggregates_across_sessions(client) -> None:
    http, _app = client
    _seed(client, [
        ("sess-1", {"recent_history": [
            {"concept_id": "ml:1:ml_basics", "correctness": "incorrect",
             "timestamp": "2026-08-30T01:00:00", "was_self_corrected": False,
             "answer": "错的回答"},
            {"concept_id": "ml:1:ml_basics", "correctness": "correct",
             "timestamp": "2026-08-30T02:00:00", "was_self_corrected": True,
             "answer": "对的回答"},
        ]}, datetime(2026, 8, 30, 1, 0)),
        ("sess-2", {"recent_history": [
            {"concept_id": "ml:1:ml_basics", "correctness": "partial",
             "timestamp": "2026-08-30T03:00:00", "was_self_corrected": False,
             "answer": "部分回答"},
        ]}, datetime(2026, 8, 30, 3, 0)),
    ])
    resp = http.get(f"/api/tutoring/users/{USER}/session-history")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["overview"]["sessions"] == 2
    assert data["overview"]["attempts"] == 3
    assert data["overview"]["correct"] == 1
    assert data["overview"]["partial"] == 1
    assert data["overview"]["incorrect"] == 1
    assert data["overview"]["correct_rate"] == pytest.approx(0.333, abs=0.01)
    # 时间倒序：最新的在前
    assert [e["timestamp"] for e in data["entries"]] == [
        "2026-08-30T03:00:00", "2026-08-30T02:00:00", "2026-08-30T01:00:00",
    ]
    # 概念名回填
    assert data["entries"][0]["concept_name"] == "机器学习基础"
    assert data["entries"][2]["answer"] == "错的回答"


def test_session_history_empty_user(client) -> None:
    http, _app = client
    resp = http.get("/api/tutoring/users/nobody/session-history")
    data = resp.json()["data"]
    assert data["overview"] == {
        "sessions": 0, "attempts": 0, "correct": 0,
        "partial": 0, "incorrect": 0, "correct_rate": 0.0,
    }
    assert data["sessions"] == []
    assert data["entries"] == []
