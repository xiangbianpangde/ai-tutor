"""M-013 长期记忆测试：save/query/evict_lru/extract + REST。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig
from backend.memory import LongTermMemory, extract_facts


@pytest.fixture()
def store(tmp_path):
    from shared.storage import RelationalStore

    s = RelationalStore(f"sqlite:///{tmp_path / 'mem.db'}")
    s.init_schema()
    return s


def test_extract_facts_splits_sentences():
    facts = extract_facts("梯度下降最小化损失。反向传播算梯度！注意力机制处理序列？")
    assert len(facts) == 3


def test_extract_facts_filters_short():
    facts = extract_facts("。。短。这是一条足够长的有效事实句子")
    assert all(len(f) >= 6 for f in facts)


def test_save_and_query(store):
    mem = LongTermMemory(store)
    mem.save_fact(user_id="u1", subject_id="s1", content="梯度下降沿负梯度最小化损失")
    mem.save_fact(user_id="u1", subject_id="s1", content="反向传播用链式法则算梯度")
    hits = mem.query_facts(user_id="u1", subject_id="s1", query="梯度")
    assert hits
    assert any("梯度" in h["content"] for h in hits)


def test_save_idempotent(store):
    mem = LongTermMemory(store)
    a = mem.save_fact(user_id="u1", subject_id="s1", content="同一句事实")
    b = mem.save_fact(user_id="u1", subject_id="s1", content="同一句事实")
    assert a == b  # 同内容 → 同 id 幂等
    all_facts = mem.query_facts(user_id="u1", subject_id="s1")
    assert len(all_facts) == 1


def test_save_empty_raises(store):
    from shared.errors import TutorError

    mem = LongTermMemory(store)
    with pytest.raises(TutorError):
        mem.save_fact(user_id="u1", subject_id="s1", content="   ")


def test_evict_lru(store):
    mem = LongTermMemory(store, max_facts_per_subject=3)
    for i in range(5):
        mem.save_fact(user_id="u1", subject_id="s1", content=f"事实编号 {i} 内容")
    remaining = mem.query_facts(user_id="u1", subject_id="s1", limit=100)
    assert len(remaining) <= 3  # 超额已淘汰最久未访问


def test_query_isolates_users(store):
    mem = LongTermMemory(store)
    mem.save_fact(user_id="u1", subject_id="s1", content="用户一的事实内容")
    mem.save_fact(user_id="u2", subject_id="s1", content="用户二的事实内容")
    u1 = mem.query_facts(user_id="u1", subject_id="s1")
    assert len(u1) == 1
    assert "用户一" in u1[0]["content"]


def test_ingest_text(store):
    mem = LongTermMemory(store)
    ids = mem.ingest_text(user_id="u1", subject_id="s1",
                          text_blob="第一条重要事实内容。第二条重要事实内容。", source="lecture")
    assert len(ids) == 2


# ----------------------------- REST -----------------------------

@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(_env_file=None, db_path=tmp_path / "t.db")
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c


def test_rest_save_and_query(client):
    r = client.post("/api/tutoring/memory/facts", json={
        "user_id": "u1", "subject_id": "s1",
        "content": "梯度下降沿负梯度方向最小化损失函数",
    })
    assert r.status_code == 200
    assert r.json()["data"]["fact_id"]

    q = client.get("/api/tutoring/memory/facts",
                   params={"user_id": "u1", "subject_id": "s1", "query": "梯度"})
    assert q.status_code == 200
    assert q.json()["data"]
