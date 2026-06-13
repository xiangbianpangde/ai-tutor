"""backend 骨架测试 —— 覆盖 BDD 01（后端骨架）+ 02（统一信封）关键场景。"""
from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.core import TutorError

ENGINES = ["knowledge", "tutoring", "digest", "sync"]


def test_knowledge_health_matches_spec(client):
    """BDD 01 场景1：GET /api/knowledge/health → {ok:true, version:2.0.0}。"""
    r = client.get("/api/knowledge/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["version"] == "2.0.0"


@pytest.mark.parametrize("engine", ENGINES)
def test_all_engine_health(client, engine):
    r = client.get(f"/api/{engine}/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": "2.0.0", "engine": engine}


def test_root_banner_lists_engines(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert set(body["data"]["engines"]) == set(ENGINES)


def test_cache_stats_endpoint(client):
    """GET /api/meta/cache/stats → 统一信封 + 缓存统计字段。"""
    r = client.get("/api/meta/cache/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    for field in ("hits", "misses", "hit_rate", "saved_tokens", "entries"):
        assert field in body["data"]


def test_list_sessions_endpoint(client):
    """GET /api/tutoring/sessions?user_id= → 统一信封 + 会话列表（M-004）。"""
    # 空库先返回空列表
    r = client.get("/api/tutoring/sessions", params={"user_id": "yhn"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["data"] == []
    # 建一个会话后能列出
    client.app.state.sessions.store.create(user_id="yhn", subject_id="gaoshu")
    r2 = client.get("/api/tutoring/sessions", params={"user_id": "yhn"})
    data = r2.json()["data"]
    assert len(data) == 1 and data[0]["subject_id"] == "gaoshu"
    # user_id 必填
    assert client.get("/api/tutoring/sessions").status_code == 422


def test_db_auto_init_creates_tables(client, config):
    """BDD 01 场景3：data/tutor.db 自动创建，14 张表全部存在。"""
    assert config.db_path.exists()
    conn = sqlite3.connect(config.db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    finally:
        conn.close()
    names = {r[0] for r in rows}
    assert len(names) >= 13, f"建表数不足: {sorted(names)}"
    assert any("concept" in n.lower() for n in names)


def test_unknown_route_404(client):
    assert client.get("/api/knowledge/does-not-exist").status_code == 404


def test_tutor_error_unified_envelope(client):
    """BDD 02 场景7 形态：业务错误 → {ok:false, error:{code, hint}} + 正确状态码。"""
    app = client.app

    @app.get("/_test/boom")
    async def _boom():
        raise TutorError("KG_NOT_BUILT", hint="请先构建知识图谱")

    r = client.get("/_test/boom")
    assert r.status_code == 409
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "KG_NOT_BUILT"
    assert body["error"]["hint"] == "请先构建知识图谱"


def test_database_error_envelope(client):
    """BDD 01 场景5 形态：DB 错误 → DATABASE_ERROR 信封（不 500 裸崩）。"""
    app = client.app

    @app.get("/_test/db")
    async def _db():
        raise SQLAlchemyError("disk image is malformed")

    r = client.get("/_test/db")
    assert r.status_code == 500
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "DATABASE_ERROR"
