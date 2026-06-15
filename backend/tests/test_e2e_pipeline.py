"""v2 第一波过堂——端到端真管线（无 fake runner / 无 FakeEngine / 无网络 / 无真 LLM）。

走完：真采集语料 → 真建图(toc，纯规则免 LLM) 异步 → 图查看 → RAG 检索 → 教学会话
(真 TeachingEngine + StubLLM) → 作答判分。证明 v2 backend 全链在真数据上打通。

资产保护：用 tests/fixtures/mini_subject.md 牺牲品语料，**不碰演示科目**。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "mini_subject.md"


@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(_env_file=None, db_path=tmp_path / "e2e.db")
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c, app, tmp_path


def test_full_backend_pipeline_real_kg(client):
    c, app, tmp_path = client
    store = app.state.store

    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from shared.models import User
    from shared.storage import FileStore

    assert FIXTURE.exists(), f"fixture 缺失: {FIXTURE}"

    # 1) 真采集语料 → 真 Corpus（落库）
    with store.session() as s:
        s.add(User(id="yhn", display_name="T"))
        s.commit()
    fs = FileStore(tmp_path / "files")
    _manifest, corpus_id = acquire(
        subject="高数测试", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=fs, db=store,
    )

    # 2) 真建图 toc（纯规则，无 LLM）——经 M-007 异步任务（默认 runner，非 fake）
    r = c.post("/api/knowledge/subjects/gaoshu/graphs",
               json={"corpus_id": corpus_id, "depth": "toc"})
    assert r.status_code == 202
    task_id = r.json()["data"]["task_id"]
    final = app.state.tasks.wait(task_id, timeout=30)
    assert final["state"] == "succeeded", final
    kg_id = final["result"]["kg_id"]

    # 3) 图查看（#5 可视化数据）：2 章 + 5 节 + 10 小节 = 17 概念
    view = c.get(f"/api/knowledge/graphs/{kg_id}/view")
    assert view.status_code == 200
    vdata = view.json()["data"]
    assert vdata["node_count"] == 17
    assert vdata["edge_count"] >= 15  # part_of 父子边

    # 4) RAG 检索（#9）：在真 KG 上检索命中
    rag = c.post("/api/knowledge/rag/query",
                 json={"kg_id": kg_id, "query": "极限", "top_k": 3})
    assert rag.status_code == 200
    assert rag.json()["data"]["chunks"], "RAG 应在真 KG 上检索到概念"

    # 5) 教学会话（#10）：真 TeachingEngine + StubLLM（无真 LLM）
    start = c.post("/api/tutoring/sessions/start",
                   json={"user_id": "yhn", "subject_id": "gaoshu", "kg_id": kg_id})
    assert start.status_code == 200
    sdata = start.json()["data"]
    sid = sdata["session_id"]
    assert sdata["total_concepts"] == 17
    assert sdata["current_action"]["type"]

    # 6) 作答 → 判分（StubLLM 启发式）
    resp = c.post(f"/api/tutoring/sessions/{sid}/respond",
                  json={"answer": "极限是自变量趋近某点时函数值的趋向"})
    assert resp.status_code == 200
    correctness = resp.json()["data"]["result"]["correctness"]
    assert correctness in ("correct", "partial", "incorrect")

    # 7) 会话进 list_sessions（M-004 共享存储）
    lst = c.get("/api/tutoring/sessions", params={"user_id": "yhn"}).json()["data"]
    assert any(x["session_id"] == sid for x in lst)
