"""M-008 RAG 引擎测试：tokenize / 检索 / 验证（含永不过度授信） / 重检索状态机 / REST。

不碰网络/LLM/演示资产：检索用 StaticChunkSource 内存语料；REST 用注入假 KG 概念。
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig
from backend.rag import (
    STATE_CANNOT_CONFIRM,
    STATE_VALIDATED,
    AnswerValidator,
    Chunk,
    KeywordRouter,
    LexicalRetriever,
    RAGEngine,
    StaticChunkSource,
    tokenize,
)

# ----------------------------- tokenize -----------------------------

def test_tokenize_drops_stopwords_and_keeps_content():
    toks = tokenize("What is the gradient descent")
    assert "gradient" in toks and "descent" in toks
    assert "the" not in toks and "is" not in toks and "what" not in toks


def test_tokenize_cjk_chars_and_bigrams():
    toks = tokenize("梯度下降")
    assert "梯" in toks and "度" in toks
    assert "梯度" in toks and "下降" in toks  # bigram


# ----------------------------- retriever -----------------------------

def _corpus() -> StaticChunkSource:
    return StaticChunkSource([
        Chunk(id="c1", text="gradient descent optimizes a loss function by steps", source="c1"),
        Chunk(id="c2", text="backpropagation computes gradients through the chain rule", source="c2"),
        Chunk(id="c3", text="a transformer uses self attention over tokens", source="c3"),
    ])


def test_retriever_ranks_relevant_first():
    r = LexicalRetriever(_corpus())
    hits = r.retrieve("gradient descent", top_k=3)
    assert hits[0].id == "c1"
    assert hits[0].score > 0


def test_retriever_empty_query_returns_empty():
    r = LexicalRetriever(_corpus())
    assert r.retrieve("the a of", top_k=3) == []  # 全停用词


def test_retriever_no_match_returns_empty():
    r = LexicalRetriever(_corpus())
    assert r.retrieve("quantum chromodynamics", top_k=3) == []


def test_retriever_invalidate_rebuilds_index():
    r = LexicalRetriever(_corpus())
    r.retrieve("gradient", top_k=1)
    r.invalidate()
    assert r._chunks is None


# ----------------------------- validator -----------------------------

def test_validator_no_sources_never_supported():
    v = AnswerValidator()
    res = v.validate("gradient descent minimizes loss", [])
    assert res.is_supported is False
    assert res.confidence == 0.0


def test_validator_empty_answer_not_supported():
    v = AnswerValidator()
    res = v.validate("", ["gradient descent minimizes loss"])
    assert res.is_supported is False


def test_validator_heuristic_supported_when_covered():
    v = AnswerValidator()
    res = v.validate(
        "gradient descent minimizes loss",
        ["gradient descent is a method that minimizes the loss function"],
    )
    assert res.is_supported is True
    assert res.method == "heuristic"


def test_validator_heuristic_never_overclaims_confidence():
    """回退启发式置信永远封顶 0.6——绝不冒充 LLM 级判定（FIX-L 教训）。"""
    v = AnswerValidator()
    res = v.validate(
        "gradient descent minimizes loss",
        ["gradient descent is a method that minimizes the loss function value"],
    )
    assert res.method == "heuristic"
    assert res.confidence <= 0.6


def test_validator_unsupported_when_offtopic():
    v = AnswerValidator()
    res = v.validate(
        "transformers use attention mechanisms",
        ["gradient descent minimizes the loss function"],
    )
    assert res.is_supported is False
    assert res.mismatched_claims  # 列出未覆盖 token


def test_validator_llm_judge_takes_priority():
    def judge(answer, sources):
        return {"is_supported": True, "confidence": 0.95, "mismatched_claims": []}

    v = AnswerValidator(llm_judge=judge)
    res = v.validate("anything", ["src"])
    assert res.method == "llm"
    assert res.confidence == 0.95


def test_validator_llm_judge_failure_falls_back():
    def judge(answer, sources):
        raise RuntimeError("judge down")

    v = AnswerValidator(llm_judge=judge)
    res = v.validate("gradient descent", ["gradient descent method"])
    assert res.method == "heuristic"  # 法官挂 → 降级，不抛


# ----------------------------- engine -----------------------------

def test_engine_retrieve_confirmed_state():
    eng = RAGEngine(LexicalRetriever(_corpus()), AnswerValidator(), nli_threshold=0.3)
    res = asyncio.run(eng.retrieve("gradient descent loss"))
    assert res.chunks
    assert res.state in (STATE_VALIDATED, STATE_CANNOT_CONFIRM)
    assert res.rounds >= 1


def test_engine_cannot_confirm_when_no_hits():
    eng = RAGEngine(LexicalRetriever(_corpus()), AnswerValidator(), nli_threshold=0.7)
    res = asyncio.run(eng.retrieve("quantum chromodynamics theory"))
    assert res.chunks == []
    assert res.confirmed is False
    assert res.state == STATE_CANNOT_CONFIRM
    assert res.rounds == eng.max_rounds  # 跑满重检索轮次仍无确认


def test_engine_empty_query_raises():
    from shared.errors import TutorError

    eng = RAGEngine(LexicalRetriever(_corpus()), AnswerValidator())
    with pytest.raises(TutorError):
        asyncio.run(eng.retrieve("   "))


def test_engine_emits_events():
    seen = []

    class _Bus:
        async def publish(self, event):
            seen.append(event.type)
            return 1

    eng = RAGEngine(LexicalRetriever(_corpus()), AnswerValidator(),
                    events=_Bus(), nli_threshold=0.3)
    asyncio.run(eng.retrieve("gradient descent"))
    assert "rag.retrieve" in seen


def test_engine_router_extracts_keywords():
    d = KeywordRouter().route("how does gradient descent work")
    assert "gradient" in d.keywords and "descent" in d.keywords
    assert d.scope == "concept"


# ----------------------------- REST 端点 -----------------------------

@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(db_path=tmp_path / "t.db", files_root=tmp_path / "files")
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c, app


def _seed_kg(app, kg_id="kg-test"):
    """直接写两个概念到 store，供 RAG 检索（牺牲品 KG，非演示资产）。

    RAG 检索只读 ConceptRow（按 kg_id），无需 KnowledgeGraphRow；SQLite 默认不强制 FK。
    """
    store = app.state.store

    from shared.models import ConceptRow

    with store.session() as s:
        for cid, name, defi in [
            ("k1", "梯度下降", "一种沿负梯度方向迭代最小化损失函数的优化方法"),
            ("k2", "反向传播", "利用链式法则逐层计算梯度的算法"),
        ]:
            s.add(ConceptRow(
                id=cid, kg_id=kg_id, base_id=cid, name_primary=name,
                names_json=[name], category="definition", definition=defi,
                abstract_level=0.5, bloom_level="understand", domain="ml",
                cognitive_load_estimate=0.5, typical_learning_time_min=20,
                prereq_count=0, prereq_max_depth=0, formula_density=0.1,
                coupling=0.1, confidence=0.9, full_json={},
            ))
        s.commit()
    return kg_id


def test_rest_rag_query(client):
    c, app = client
    kg_id = _seed_kg(app)
    resp = c.post("/api/knowledge/rag/query",
                  json={"kg_id": kg_id, "query": "梯度下降", "top_k": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    data = body["data"]
    assert data["chunks"]
    assert data["chunks"][0]["metadata"]["name"] == "梯度下降"
    assert "rounds" in data and "confirmed" in data


def test_rest_rag_validate(client):
    c, app = client
    resp = c.post("/api/knowledge/rag/validate", json={
        "answer": "梯度下降沿负梯度迭代最小化损失",
        "sources": ["梯度下降是一种沿负梯度方向迭代最小化损失函数的优化方法"],
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_supported"] is True
    assert data["method"] == "heuristic"


def test_rest_rag_validate_no_sources(client):
    c, app = client
    resp = c.post("/api/knowledge/rag/validate",
                  json={"answer": "随便说点什么", "sources": []})
    assert resp.status_code == 200
    assert resp.json()["data"]["is_supported"] is False
