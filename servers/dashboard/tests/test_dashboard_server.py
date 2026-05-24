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
