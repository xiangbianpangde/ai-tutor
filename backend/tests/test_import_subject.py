"""导入资料一键建科目（#21 零门槛入口）：采集→建图→建 Subject 全链异步。

牺牲品语料（内联 markdown），不碰演示资产。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig

_MD = """# 线性代数入门

## 向量

### 向量加法
两个向量逐分量相加。

### 数乘
向量每个分量乘以标量。

## 矩阵

### 矩阵乘法
行乘列求和。
"""


@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(_env_file=None, db_path=tmp_path / "t.db")
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c


def test_import_builds_subject_and_kg(client):
    r = client.post("/api/knowledge/subjects/import", json={
        "user_id": "newbie", "subject_name": "线性代数入门", "markdown": _MD,
    })
    assert r.status_code == 202
    body = r.json()["data"]
    task_id = body["task_id"]
    subject_id = body["subject_id"]

    final = client.app.state.tasks.wait(task_id, timeout=30)
    assert final["state"] == "succeeded", final
    res = final["result"]
    assert res["subject_id"] == subject_id
    assert res["concepts"] >= 6  # 2 章 + 2 节 + 3 小节
    kg_id = res["kg_id"]

    # 建好的科目可直接开学（start 不传 kg_id，从 subject 解析）
    start = client.post("/api/tutoring/sessions/start",
                        json={"user_id": "newbie", "subject_id": subject_id})
    assert start.status_code == 200
    assert start.json()["data"]["total_concepts"] == res["concepts"]

    # 图可视化数据就绪
    view = client.get(f"/api/knowledge/graphs/{kg_id}/view")
    assert view.json()["data"]["node_count"] == res["concepts"]


def test_import_empty_rejected(client):
    r = client.post("/api/knowledge/subjects/import", json={
        "user_id": "newbie", "subject_name": "空", "markdown": "   ",
    })
    assert r.status_code >= 400


def test_subjects_list_after_import(client):
    """独立验收驱动：导入后科目进"我的科目"列表（免手填不透明 ID）。"""
    before = client.get("/api/knowledge/subjects", params={"user_id": "picker"}).json()["data"]
    assert before == []
    r = client.post("/api/knowledge/subjects/import", json={
        "user_id": "picker", "subject_name": "线性代数入门", "markdown": _MD,
    })
    client.app.state.tasks.wait(r.json()["data"]["task_id"], timeout=30)
    after = client.get("/api/knowledge/subjects", params={"user_id": "picker"}).json()["data"]
    assert len(after) == 1
    assert after[0]["display_name"] == "线性代数入门"
    assert after[0]["concepts"] >= 6
    assert after[0]["subject_id"]
