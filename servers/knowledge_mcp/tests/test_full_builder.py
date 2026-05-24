"""FullKGBuilder 集成测试：concept enrich + 难度校准 + embedding 一条龙。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import ConceptRow, KnowledgeGraphRow, User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enriched(name: str) -> str:
    return json.dumps({
        "definition": f"{name}：精确定义",
        "informal_description": f"通俗{name}",
        "examples": [{"text": f"例子{name}", "type": "computation"}],
        "confidence": 0.85,
    }, ensure_ascii=False)


@pytest.fixture
def corpus(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ce-shi", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    return tmp_db, corpus_id, Path(manifest.file_paths["markdown"])


def _build_full(db, corpus_id, md):
    from servers.knowledge_mcp.kg_builder import FullKGBuilder

    llm = MockLLMProvider(canned_responses=[_enriched(f"c{i}") for i in range(50)])
    return FullKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="ce-shi", markdown_path=md, db=db,
    )


def test_full_build_persists_full_v1(corpus):
    db, corpus_id, md = corpus
    r = _build_full(db, corpus_id, md)
    assert r.kg_id.endswith("-kg-full-v1")
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, r.kg_id)
        assert kg is not None
        assert kg.version == "full-v1"
        assert kg.manifest_json.get("depth") == "full"


def test_full_build_writes_calibrated_difficulty(corpus):
    db, corpus_id, md = corpus
    r = _build_full(db, corpus_id, md)
    with db.session() as s:
        rows = s.query(ConceptRow).filter_by(kg_id=r.kg_id).all()
        assert rows
        for row in rows:
            diff = (row.full_json or {}).get("difficulty", {}).get("calibrated_difficulty")
            assert diff is not None
            assert 0.0 <= diff <= 1.0


def test_full_build_writes_embedding(corpus):
    db, corpus_id, md = corpus
    r = _build_full(db, corpus_id, md)
    with db.session() as s:
        rows = s.query(ConceptRow).filter_by(kg_id=r.kg_id).all()
        for row in rows:
            emb = (row.full_json or {}).get("embedding")
            assert emb is not None
            assert len(emb) == 64


def test_full_build_manifest_has_avg_difficulty(corpus):
    db, corpus_id, md = corpus
    r = _build_full(db, corpus_id, md)
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, r.kg_id)
        assert "avg_calibrated_difficulty" in kg.manifest_json
        assert kg.manifest_json["embedding_dim"] == 64


def test_full_build_concept_full_json_validates(corpus):
    """写回 full_json 后仍能被 Concept schema 校验（embedding/calibrated_difficulty 合法）。"""
    from shared.schemas import Concept

    db, corpus_id, md = corpus
    r = _build_full(db, corpus_id, md)
    with db.session() as s:
        rows = s.query(ConceptRow).filter_by(kg_id=r.kg_id).all()
        for row in rows:
            c = Concept.model_validate(row.full_json)  # 不应抛 ValidationError
            assert c.embedding is not None


def test_full_build_without_llm_raises(corpus):
    from servers.knowledge_mcp.kg_builder import FullKGBuilder
    from shared.errors import TutorError

    db, corpus_id, md = corpus
    with pytest.raises(TutorError) as exc:
        FullKGBuilder(llm=None).build(
            corpus_id=corpus_id, subject_slug="ce-shi", markdown_path=md, db=db,
        )
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"
