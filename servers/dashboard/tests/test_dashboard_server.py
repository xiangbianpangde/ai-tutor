"""状态面板 server 路由 smoke test（Starlette TestClient，只读）。"""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'd.db'}")
    from shared.storage import RelationalStore
    RelationalStore.from_env().init_schema()
    # 延迟导入，确保 server 用到的 _db() 读到上面的 DATABASE_URL
    from servers.dashboard.server import app
    return TestClient(app)


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "教学状态" in r.text
    assert "/api/state" in r.text  # 前端轮询端点


def test_api_state_idle_when_empty(client):
    r = client.get("/api/state")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


def test_layers_page_serves_html(client):
    r = client.get("/layers")
    assert r.status_code == 200
    assert "逐层视图" in r.text
    assert "/api/layer/" in r.text  # 前端按层取数端点


@pytest.mark.parametrize("layer", ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "pgfga"])
def test_api_layer_each_returns_json(client, layer):
    r = client.get(f"/api/layer/{layer}")
    assert r.status_code == 200
    body = r.json()
    assert body["layer"] == layer
    assert "error" not in body


def test_api_layer_unknown_404(client):
    r = client.get("/api/layer/L99")
    assert r.status_code == 404
    assert "valid" in r.json()
