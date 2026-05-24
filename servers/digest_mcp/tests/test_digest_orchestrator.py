"""digest() orchestrator 契约测试。

入口: digest(corpus_id=..., kg_id=..., formats=[...], ...) → DigestResult(artifacts=[ArtifactURI])

formats:
  - 已实现: "mindmap", "notes", "quiz"
  - stub: "slides", "audio", "simulation", "multi_agent" → 抛 DEPENDENCY_MISSING

设计:
- formats 为空 → 默认 ["mindmap", "quiz"]
- 多 format 调用 → 全部 artifact 返回
- 单个 format stub → 不影响已实现的 format 生成（部分成功，warnings）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import Subject, User
from shared.storage import RelationalStore


FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enriched(name: str) -> str:
    return json.dumps({"definition": f"{name} 的定义", "confidence": 0.85}, ensure_ascii=False)


@pytest.fixture
def kg_and_corpus(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ce-shi", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    canned = [_enriched(f"c{i}") for i in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id, subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    return tmp_db, corpus_id, r.kg_id


def test_digest_default_formats(kg_and_corpus, tmp_path: Path) -> None:
    from servers.digest_mcp.orchestrator import digest

    db, _, kg_id = kg_and_corpus
    result = digest(db=db, kg_id=kg_id, out_dir=tmp_path)  # 不传 formats
    types = {a.mime_type for a in result.artifacts}
    # 默认 ["mindmap", "quiz"]，quiz 产两个（html+json）
    assert "text/vnd.mermaid" in types
    assert "text/html" in types


def test_digest_explicit_three_formats(kg_and_corpus, tmp_path: Path) -> None:
    from servers.digest_mcp.orchestrator import digest

    db, _, kg_id = kg_and_corpus
    result = digest(
        db=db, kg_id=kg_id, out_dir=tmp_path,
        formats=["mindmap", "notes", "quiz"],
    )
    types = {a.mime_type for a in result.artifacts}
    assert "text/vnd.mermaid" in types
    assert "text/markdown" in types
    assert "text/html" in types
    assert "application/json" in types  # quiz 的 json


def test_digest_all_seven_formats_produce_artifacts(kg_and_corpus, tmp_path: Path) -> None:
    """D2 后 7 种 format 全部产出 artifact，无 stub warning。"""
    from servers.digest_mcp.orchestrator import digest

    db, _, kg_id = kg_and_corpus
    result = digest(
        db=db, kg_id=kg_id, out_dir=tmp_path,
        formats=["mindmap", "notes", "quiz", "simulation", "multi_agent", "slides", "audio"],
    )
    # 每个 format 至少 1 个 artifact（quiz 可能多个）→ ≥ 7
    assert len(result.artifacts) >= 7
    mimes = {a.mime_type for a in result.artifacts}
    assert "text/vnd.mermaid" in mimes        # mindmap
    assert "text/markdown" in mimes           # notes / audio script
    assert "text/html" in mimes               # simulation / slides(html)
    assert "application/json" in mimes        # multi_agent
    # 不应再有 "暂未实现 / stub" 类 warning
    assert not any("未实现" in w or "stub" in w.lower() for w in result.warnings)


def test_digest_unknown_format_warning(kg_and_corpus, tmp_path: Path) -> None:
    from servers.digest_mcp.orchestrator import digest

    db, _, kg_id = kg_and_corpus
    result = digest(
        db=db, kg_id=kg_id, out_dir=tmp_path,
        formats=["mindmap", "alien_format"],
    )
    assert any("alien_format" in w for w in result.warnings)


def test_digest_unknown_kg_raises(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from shared.errors import TutorError
    from servers.digest_mcp.orchestrator import digest

    with pytest.raises(TutorError) as exc:
        digest(db=tmp_db, kg_id="no-such", out_dir=tmp_path, formats=["mindmap"])
    assert exc.value.code == "KG_NOT_FOUND"


@pytest.mark.asyncio
async def test_digest_tool_registered() -> None:
    """server.py 的 digest tool 应当被 FastMCP 注册。"""
    from servers.digest_mcp import server as srv

    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    assert "digest" in names
    assert "health" in names
    # spec §三 #2/#3 独立入口
    assert "build_quiz_html" in names
    assert "compile_slides" in names


@pytest.mark.asyncio
async def test_digest_tool_calls_orchestrator(kg_and_corpus, tmp_path: Path, monkeypatch) -> None:
    """server.digest 应该 dispatch 到 orchestrator.digest。"""
    from servers.digest_mcp import server as srv
    from shared.storage import RelationalStore

    db, _, kg_id = kg_and_corpus
    monkeypatch.setenv("DATABASE_URL", db.url)
    monkeypatch.setenv("AI_TUTOR_DATA_ROOT", str(tmp_path))

    fn = getattr(srv.digest, "fn", srv.digest)
    result = await fn(kg_id=kg_id, formats=["mindmap"])
    assert len(result.artifacts) >= 1
