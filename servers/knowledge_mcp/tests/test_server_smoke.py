"""knowledge-mcp server tool 注册 + 调用 smoke test。

不起 transport，直接调 server 模块里注册的 async 函数。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from servers.knowledge_mcp import server as srv
from shared.models import User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


@pytest.fixture
def db_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RelationalStore:
    """让 server._db() 指向临时 SQLite。"""
    db_path = tmp_path / "srv_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AI_TUTOR_DATA_ROOT", str(tmp_path / "data"))

    store = RelationalStore.from_env()
    store.init_schema()
    with store.session() as s:
        s.add(User(id="default"))
        s.commit()
    return store


def _unwrap(tool_obj):
    """FastMCP 的 @tool() 把函数包装；用其 .fn 或 .call 跳过 schema 校验。"""
    return getattr(tool_obj, "fn", None) or getattr(tool_obj, "func", None) or tool_obj


@pytest.mark.asyncio
async def test_health_ok(db_env: RelationalStore) -> None:
    fn = _unwrap(srv.health)
    out = await fn()
    assert out["ok"] is True
    assert out["server"] == "knowledge-mcp"


@pytest.mark.asyncio
async def test_acquire_then_build_then_query(db_env: RelationalStore) -> None:
    acquire_fn = _unwrap(srv.acquire_subject)
    build_fn = _unwrap(srv.build_knowledge_graph)
    query_fn = _unwrap(srv.query_knowledge)

    a = await acquire_fn(
        subject="测试高数",
        sources=[{"type": "file", "uri": str(FIXTURE)}],
        user_id="default",
        version="v1",
    )
    assert a.stats["total_chapters"] == 2

    b = await build_fn(corpus_id=a.corpus_id, depth="toc")
    assert b.triples_count > 0
    assert b.quality_report.overall in ("pass", "pass_with_warnings")
    assert b.mermaid and "graph TD" in b.mermaid

    # 查询：找含"极限"的概念
    q = await query_fn(kg_id=b.kg_id, query="极限", query_type="concept", max_results=10)
    assert len(q["results"]) >= 1
    assert all("极限" in r["name"] for r in q["results"])


@pytest.mark.asyncio
async def test_build_links_subject_and_kg_id(db_env: RelationalStore) -> None:
    """build_knowledge_graph 后自动建/更新 Subject 并把 kg_id 指过去（闭合采集→教学）。"""
    from shared.models import Subject

    acquire_fn = _unwrap(srv.acquire_subject)
    build_fn = _unwrap(srv.build_knowledge_graph)
    a = await acquire_fn(
        subject="测试高数", sources=[{"type": "file", "uri": str(FIXTURE)}],
        user_id="default", version="v1",
    )
    b = await build_fn(corpus_id=a.corpus_id, depth="toc")

    with db_env.session() as s:
        # subject_id == 科目名 slug；kg_id 已指向刚建的 KG
        subj = s.get(Subject, "ce-shi-gao-shu") or next(
            (x for x in s.query(Subject).all() if x.kg_id == b.kg_id), None
        )
        assert subj is not None, "build 后应存在指向该 KG 的 Subject"
        assert subj.kg_id == b.kg_id
        assert subj.user_id == "default"


@pytest.mark.asyncio
async def test_query_path_and_subgraph(db_env: RelationalStore) -> None:
    """path / subgraph 两种 query_type 经 server 分派可用。"""
    acquire_fn = _unwrap(srv.acquire_subject)
    build_fn = _unwrap(srv.build_knowledge_graph)
    query_fn = _unwrap(srv.query_knowledge)

    a = await acquire_fn(
        subject="测试高数", sources=[{"type": "file", "uri": str(FIXTURE)}],
        user_id="default", version="v1",
    )
    b = await build_fn(corpus_id=a.corpus_id, depth="toc")

    # 取两个真实 concept_id（章节 1 下的父子）做 path/subgraph
    os.environ["DATABASE_URL"] = db_env.url
    from shared.models import ConceptRow as CR
    with db_env.session() as s:
        ids = [r.id for r in s.query(CR).filter_by(kg_id=b.kg_id).order_by(CR.id).all()]
    assert ids

    # subgraph：中心取第一个概念，depth=1，应至少含自己
    sg = await query_fn(kg_id=b.kg_id, query=ids[0], query_type="subgraph", depth=1)
    assert sg["found"] is True
    assert any(c["concept_id"] == ids[0] for c in sg["concepts"])

    # path：起点=终点 → 平凡路径
    p = await query_fn(kg_id=b.kg_id, query=ids[0], query_type="path", target=ids[0])
    assert p["found"] is True
    assert p["path"] == [ids[0]]

    # 缺失终点 → found=False（不抛）
    p2 = await query_fn(kg_id=b.kg_id, query=ids[0], query_type="path", target="x:9:ghost")
    assert p2["found"] is False


@pytest.mark.asyncio
async def test_build_kg_unknown_corpus_fails(db_env: RelationalStore) -> None:
    from shared.errors import TutorError

    build_fn = _unwrap(srv.build_knowledge_graph)
    with pytest.raises(TutorError) as exc_info:
        await build_fn(corpus_id="does-not-exist", depth="toc")
    assert exc_info.value.code == "CORPUS_NOT_FOUND"


@pytest.mark.asyncio
async def test_concept_and_full_depth_need_llm(db_env: RelationalStore) -> None:
    """K1.4: server 默认装 StubLLMProvider，depth=concept/full 调到 enrich 时
    都抛 PLUGIN_NOT_AVAILABLE（full 已实现，复用同一 enrich pipeline）。
    """
    from shared.errors import TutorError

    acquire_fn = _unwrap(srv.acquire_subject)
    a = await acquire_fn(
        subject="stub-test",
        sources=[{"type": "file", "uri": str(FIXTURE)}],
        user_id="default",
        version="v1",
    )

    build_fn = _unwrap(srv.build_knowledge_graph)
    # concept: 默认 stub provider 调 .chat → PLUGIN_NOT_AVAILABLE
    with pytest.raises(TutorError) as exc_concept:
        await build_fn(corpus_id=a.corpus_id, depth="concept")
    assert exc_concept.value.code == "PLUGIN_NOT_AVAILABLE"
    # full: 已实现，复用同一 enrich pipeline → stub provider 同样 PLUGIN_NOT_AVAILABLE
    with pytest.raises(TutorError) as exc_full:
        await build_fn(corpus_id=a.corpus_id, depth="full")
    assert exc_full.value.code == "PLUGIN_NOT_AVAILABLE"
