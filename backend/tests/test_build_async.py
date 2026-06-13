"""build_kg 异步任务端到端（M-007 / spec 02 场景4）—— 用假 runner，不碰演示资产。"""
from __future__ import annotations


def test_build_kg_returns_task_then_polls(client):
    """POST 构建立即返回 task_id（不阻塞）；GET /api/tasks/{id} 轮询到 succeeded。"""

    def fake_runner(reporter, *, store, corpus_id, depth, **_):
        reporter.update(0.5, "mock 构建中")
        return {"kg_id": f"{corpus_id}-kg", "depth": depth}

    client.app.state.build_runner = fake_runner

    r = client.post(
        "/api/knowledge/subjects/gaoshu/graphs",
        json={"corpus_id": "c1", "depth": "toc"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["ok"] is True
    task_id = body["data"]["task_id"]

    final = client.app.state.tasks.wait(task_id, timeout=5)
    assert final["state"] == "succeeded"
    assert final["result"]["kg_id"] == "c1-kg"

    g = client.get(f"/api/tasks/{task_id}")
    assert g.status_code == 200
    assert g.json()["data"]["state"] == "succeeded"


def test_unknown_task_404(client):
    r = client.get("/api/tasks/task-doesnotexist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "TASK_NOT_FOUND"
