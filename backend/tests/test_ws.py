"""#7 WebSocket 实时推送测试：连接握手 + EventBus 事件实时转发。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig


@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(_env_file=None, db_path=tmp_path / "t.db")
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c, app


def test_ws_connect_handshake(client):
    c, app = client
    with c.websocket_connect("/ws/events") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "ws.connected"
        assert hello["payload"]["bus"] is True


def test_ws_receives_published_event(client):
    """连接后经 HTTP 触发一个会发事件的动作 → WS 实时收到。"""
    c, app = client
    # 注入 stub engine 工厂，start 会 publish teaching.session_started
    from backend.tests.test_teaching import FakeEngine

    app.state.teaching_engine_factory = lambda: FakeEngine()
    with c.websocket_connect("/ws/events") as ws:
        assert ws.receive_json()["type"] == "ws.connected"
        # 触发事件
        c.post("/api/tutoring/sessions/start",
               json={"user_id": "u1", "subject_id": "s1", "kg_id": "kg-x"})
        msg = ws.receive_json()
        assert msg["type"] == "teaching.session_started"
        assert "payload" in msg and "ts" in msg


def test_ws_receives_rag_event(client):
    c, app = client
    # 种一个概念，RAG 检索会 publish rag.retrieve
    from shared.models import ConceptRow

    with app.state.store.session() as s:
        s.add(ConceptRow(
            id="k1", kg_id="kg-r", base_id="k1", name_primary="梯度下降",
            names_json=["梯度下降"], category="definition",
            definition="沿负梯度迭代最小化损失", abstract_level=0.5, bloom_level="understand",
            domain="ml", cognitive_load_estimate=0.5, typical_learning_time_min=20,
            prereq_count=0, prereq_max_depth=0, formula_density=0.1, coupling=0.1,
            confidence=0.9, full_json={},
        ))
        s.commit()
    with c.websocket_connect("/ws/events") as ws:
        ws.receive_json()  # hello
        c.post("/api/knowledge/rag/query", json={"kg_id": "kg-r", "query": "梯度下降", "top_k": 3})
        msg = ws.receive_json()
        assert msg["type"] == "rag.retrieve"
