"""ConceptKGBuilder 真实实现契约测试（依赖 K1.1 ConceptEnricher）。

流程:
1. 跑 _build_toc 拿骨架 concepts + edges
2. 把 markdown 切成 section_text[concept_id]（heading 之间的正文）
3. 对每个 concept 调 ConceptEnricher，富化 definition/examples/confidence
4. 保留 toc 的 part_of / prerequisite_strong 边
5. 算 quality_report；写 ConceptRow + RelationRow
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.errors import TutorError
from shared.llm_client import MockLLMProvider, StubLLMProvider
from shared.models import User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


@pytest.fixture
def db_with_corpus(tmp_db: RelationalStore, tmp_filestore):
    """跑 acquire 得到 corpus_id 和 md_path。"""
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()

    manifest, corpus_id = acquire(
        subject="测试",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=tmp_db,
    )
    return tmp_db, corpus_id, Path(manifest.file_paths["markdown"])


def _enrichment_response(idx: int) -> str:
    """每个 concept 一个简单响应：filled definition + confidence。"""
    return json.dumps({
        "definition": f"LLM-填充的定义 #{idx}",
        "informal_description": f"口语化解释 #{idx}",
        "examples": [{"text": f"例子 #{idx}", "type": "computation"}],
        "confidence": 0.75,
    }, ensure_ascii=False)


def test_concept_builder_no_longer_raises(db_with_corpus) -> None:
    """K1.2 之后 ConceptKGBuilder 不再 raise DEPENDENCY_MISSING。"""
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    db, corpus_id, md_path = db_with_corpus
    # mini_subject.md 有 17 个章节标题，每个会调一次 LLM
    llm = MockLLMProvider(canned_responses=[_enrichment_response(i) for i in range(50)])
    builder = ConceptKGBuilder(llm=llm)
    result = builder.build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=md_path,
        db=db,
    )
    assert result.kg_id.endswith("-kg-concept-v1")
    assert result.triples_count > 0
    assert result.quality_report.overall in ("pass", "pass_with_warnings")


def test_concept_builder_enriches_each_concept(db_with_corpus) -> None:
    """每个 concept 都被 LLM 调过一次；ConceptRow.confidence 从 0.4 升到 0.75。"""
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from shared.models import ConceptRow as ConceptRowORM

    db, corpus_id, md_path = db_with_corpus
    llm = MockLLMProvider(canned_responses=[_enrichment_response(i) for i in range(50)])
    result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=md_path,
        db=db,
    )

    with db.session() as s:
        rows = s.query(ConceptRowORM).filter_by(kg_id=result.kg_id).all()
        assert len(rows) == 17  # fixture: 2 # + 5 ## + 10 ###
        # 每个 concept 都应被 enrich：confidence 从 toc 默认 0.4 → 0.75
        confs = [r.confidence for r in rows]
        assert all(c == pytest.approx(0.75) for c in confs)
        # definition 从纯标题 → LLM 填充
        defs = [r.definition for r in rows]
        assert all("LLM-填充" in d for d in defs)

    # LLM 调用次数 = 17 个 concept 富化 + 1 次关系抽取（RelationExtractor 单次调用）
    assert len(llm.calls) == 18


def test_concept_builder_falls_back_when_llm_unavailable(db_with_corpus) -> None:
    """LLMProvider stub → enricher 抛 PLUGIN_NOT_AVAILABLE → builder 上抛。"""
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    db, corpus_id, md_path = db_with_corpus
    with pytest.raises(TutorError) as exc:
        ConceptKGBuilder(llm=StubLLMProvider()).build(
            corpus_id=corpus_id,
            subject_slug="ce-shi",
            markdown_path=md_path,
            db=db,
        )
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"


def test_concept_builder_tolerates_per_concept_failures(db_with_corpus) -> None:
    """单个 concept LLM 返回乱码 → 该 concept 保留 toc 默认值，整体仍写库成功。"""
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from shared.models import ConceptRow as ConceptRowORM

    db, corpus_id, md_path = db_with_corpus
    # 第 1 个 concept 返回乱码，其余 OK
    responses = ["这不是 JSON"] + [_enrichment_response(i) for i in range(50)]
    llm = MockLLMProvider(canned_responses=responses)

    result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=md_path,
        db=db,
    )

    with db.session() as s:
        rows = s.query(ConceptRowORM).filter_by(kg_id=result.kg_id).order_by(ConceptRowORM.id).all()
        # 至少一个保留了 toc 默认 confidence=0.4
        low_conf = [r for r in rows if r.confidence < 0.5]
        assert len(low_conf) >= 1
        # 其他大多数应该是 0.75
        high_conf = [r for r in rows if r.confidence >= 0.7]
        assert len(high_conf) >= len(rows) - 1


def test_concept_builder_preserves_toc_edges(db_with_corpus) -> None:
    """concept 模式产出的边应该至少包含 toc 模式的 part_of/prerequisite_strong。"""
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from shared.models import RelationRow as RelationRowORM

    db, corpus_id, md_path = db_with_corpus
    llm = MockLLMProvider(canned_responses=[_enrichment_response(i) for i in range(50)])
    result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=md_path,
        db=db,
    )

    with db.session() as s:
        rels = s.query(RelationRowORM).filter_by(kg_id=result.kg_id).all()
        part_of = [r for r in rels if r.type == "part_of"]
        prereq = [r for r in rels if r.type == "prerequisite_strong"]
        assert len(part_of) >= 1
        assert len(prereq) >= 1


def test_concept_quality_report_has_higher_confidence(db_with_corpus) -> None:
    """concept 模式产出的 KG 平均 confidence 应高于 toc 模式的 0.40。"""
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    db, corpus_id, md_path = db_with_corpus
    llm = MockLLMProvider(canned_responses=[_enrichment_response(i) for i in range(50)])
    result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=md_path,
        db=db,
    )
    assert result.quality_report.avg_confidence > 0.5
