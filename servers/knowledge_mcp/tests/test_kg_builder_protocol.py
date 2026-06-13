"""KGBuilder Protocol 契约测试 + 两个实现的覆盖断言。

Protocol 定义在 servers.knowledge_mcp.kg_builder
- TocKGBuilder: 已有 build_kg_toc 的封装
- ConceptKGBuilder: 已实现（无 llm → PLUGIN_NOT_AVAILABLE）
- FullKGBuilder: 已实现（concept enrich + 难度校准 + embedding）
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.errors import TutorError
from shared.models import User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


@pytest.fixture
def db_with_user(tmp_db: RelationalStore) -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    return tmp_db


def _make_corpus(db: RelationalStore, file_store, subject_slug: str = "test") -> tuple[str, Path]:
    """新建一个 corpus 记录指向 fixture，返回 (corpus_id, md_path)。"""
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire

    manifest, corpus_id = acquire(
        subject="测试",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=file_store,
        db=db,
    )
    return corpus_id, Path(manifest.file_paths["markdown"])


def test_kg_builder_protocol_exists() -> None:
    from servers.knowledge_mcp.kg_builder import KGBuilder

    assert hasattr(KGBuilder, "build")


def test_get_builder_returns_correct_class() -> None:
    from servers.knowledge_mcp.kg_builder import (
        ConceptKGBuilder,
        FullKGBuilder,
        TocKGBuilder,
        get_builder,
    )

    assert isinstance(get_builder("toc"), TocKGBuilder)
    assert isinstance(get_builder("concept"), ConceptKGBuilder)
    assert isinstance(get_builder("full"), FullKGBuilder)


def test_get_builder_unknown_raises() -> None:
    from servers.knowledge_mcp.kg_builder import get_builder

    with pytest.raises(TutorError) as exc:
        get_builder("super_full")  # type: ignore[arg-type]
    assert exc.value.code == "DEPENDENCY_MISSING"


def test_toc_builder_round_trip(db_with_user, tmp_filestore) -> None:
    from servers.knowledge_mcp.kg_builder import TocKGBuilder

    corpus_id, md_path = _make_corpus(db_with_user, tmp_filestore)
    result = TocKGBuilder().build(
        corpus_id=corpus_id,
        subject_slug="test",
        markdown_path=md_path,
        db=db_with_user,
    )
    assert result.kg_id.endswith("-kg-toc-v1")
    assert result.triples_count > 0
    assert result.quality_report.overall in ("pass", "pass_with_warnings")
    assert result.mermaid and "graph TD" in result.mermaid


def test_concept_builder_without_llm_raises(db_with_user, tmp_filestore) -> None:
    """K1.2 后 ConceptKGBuilder 已实现；无 llm 时抛 PLUGIN_NOT_AVAILABLE。"""
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    corpus_id, md_path = _make_corpus(db_with_user, tmp_filestore)
    with pytest.raises(TutorError) as exc:
        ConceptKGBuilder(llm=None).build(
            corpus_id=corpus_id,
            subject_slug="test",
            markdown_path=md_path,
            db=db_with_user,
        )
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"
    assert "LLM" in (exc.value.hint or "") or "llm" in (exc.value.hint or "")


def test_full_builder_without_llm_raises_plugin_not_available(db_with_user, tmp_filestore) -> None:
    """full 已实现：无 llm → PLUGIN_NOT_AVAILABLE（不再是 DEPENDENCY_MISSING stub）。"""
    from servers.knowledge_mcp.kg_builder import FullKGBuilder

    corpus_id, md_path = _make_corpus(db_with_user, tmp_filestore)
    with pytest.raises(TutorError) as exc:
        FullKGBuilder().build(
            corpus_id=corpus_id,
            subject_slug="test",
            markdown_path=md_path,
            db=db_with_user,
        )
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"
