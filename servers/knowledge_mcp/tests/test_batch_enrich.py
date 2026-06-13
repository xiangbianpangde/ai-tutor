"""批量 KG 富化 (P1 #5) 测试：并行 enrich + checkpoint 续跑。

把"逐个 concept 调 LLM"升级为有界并行 + 断点续跑，使 KG 构建能扩到数百概念。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from servers.knowledge_mcp.batch_enrich import EnrichCheckpoint, batch_enrich
from servers.knowledge_mcp.concept_enricher import ConceptEnricher
from shared.errors import TutorError
from shared.llm_client import MockLLMProvider, StubLLMProvider
from shared.schemas import Concept, ConceptClassification, ConceptDifficulty


def _toc_concept(i: int) -> Concept:
    return Concept(
        id=f"s:1.{i}:c{i}",
        names=[f"概念{i}"],
        category="definition",
        definition=f"概念{i}",  # toc 默认：标题即定义
        classification=ConceptClassification(bloom_level="remember", abstract_level=0.5, domain="d"),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0, formula_density=0.1, coupling=0.1,
            cognitive_load_estimate=0.3, typical_learning_time_min=30,
        ),
        confidence=0.4,
    )


def _resp(i: int) -> str:
    return json.dumps({"definition": f"LLM定义{i}", "confidence": 0.8}, ensure_ascii=False)


def _concepts(n: int) -> list[Concept]:
    return [_toc_concept(i) for i in range(n)]


def _sections(concepts) -> dict[str, str]:
    return {c.id: f"正文 {c.id}" for c in concepts}


# --------------------------------------------------------------------------- #
# 并行 enrich
# --------------------------------------------------------------------------- #


def test_parallel_enriches_all_in_order():
    concepts = _concepts(12)
    llm = MockLLMProvider(canned_responses=[_resp(i) for i in range(12)])
    enricher = ConceptEnricher(llm=llm)
    enriched, warnings = batch_enrich(
        enricher=enricher, concepts=concepts, sections=_sections(concepts), max_workers=4,
    )
    assert [c.id for c in enriched] == [c.id for c in concepts]  # 顺序保持
    assert all(c.confidence == pytest.approx(0.8) for c in enriched)  # 每个都富化了
    assert len(llm.calls) == 12


def test_single_worker_equivalent():
    concepts = _concepts(5)
    llm = MockLLMProvider(canned_responses=[_resp(i) for i in range(5)])
    enriched, _ = batch_enrich(
        enricher=ConceptEnricher(llm=llm), concepts=concepts, sections=_sections(concepts), max_workers=1,
    )
    assert all("LLM定义" in c.definition for c in enriched)


def test_plugin_unavailable_escalates():
    concepts = _concepts(4)
    with pytest.raises(TutorError) as exc:
        batch_enrich(
            enricher=ConceptEnricher(llm=StubLLMProvider()),
            concepts=concepts, sections=_sections(concepts), max_workers=2,
        )
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"


def test_per_concept_failure_tolerated():
    """单个坏响应 → 该 concept 保留 toc 默认，整体不崩，warning 记录。"""
    concepts = _concepts(6)
    # 1 个坏 + 足够好响应
    llm = MockLLMProvider(canned_responses=["这不是JSON"] + [_resp(i) for i in range(6)])
    enriched, warnings = batch_enrich(
        enricher=ConceptEnricher(llm=llm), concepts=concepts, sections=_sections(concepts), max_workers=3,
    )
    low = [c for c in enriched if c.confidence < 0.5]
    assert len(low) == 1
    assert len(enriched) == 6


# --------------------------------------------------------------------------- #
# checkpoint 续跑
# --------------------------------------------------------------------------- #


def test_checkpoint_records_and_resumes(tmp_path: Path):
    concepts = _concepts(10)
    cp_path = tmp_path / "enrich.jsonl"

    # 第一次：富化前 5 个（只喂 5 个响应），其余因 LLM 耗尽而失败容错
    cp = EnrichCheckpoint(cp_path)
    llm1 = MockLLMProvider(canned_responses=[_resp(i) for i in range(10)])
    enriched1, _ = batch_enrich(
        enricher=ConceptEnricher(llm=llm1), concepts=concepts[:5],
        sections=_sections(concepts), max_workers=2, checkpoint=cp,
    )
    assert cp_path.exists()
    assert all(c.confidence == pytest.approx(0.8) for c in enriched1)

    # 第二次：全 10 个，但 checkpoint 已有前 5 → 只对后 5 调 LLM
    cp2 = EnrichCheckpoint(cp_path)
    cp2.load()
    llm2 = MockLLMProvider(canned_responses=[_resp(i) for i in range(10)])
    enriched2, _ = batch_enrich(
        enricher=ConceptEnricher(llm=llm2), concepts=concepts,
        sections=_sections(concepts), max_workers=2, checkpoint=cp2,
    )
    assert [c.id for c in enriched2] == [c.id for c in concepts]
    assert all(c.confidence == pytest.approx(0.8) for c in enriched2)
    # 只对未完成的 5 个调了 LLM（前 5 个从 checkpoint 复用）
    assert len(llm2.calls) == 5


class _BoomEnricher:
    """对第 idx 个 concept 抛非 TutorError，其余正常。"""

    def __init__(self, boom_id: str):
        self.boom_id = boom_id

    def enrich(self, *, concept, body_text):
        if concept.id == self.boom_id:
            raise ValueError("LLM 返回了无法构造的字段")
        return concept.model_copy(update={"confidence": 0.8}), None


def test_non_tutorerror_degrades_to_warning_not_abort():
    """单个 concept 抛非 TutorError → 降级为 warning，整批不崩（code-review Fix C）。"""
    concepts = _concepts(5)
    enriched, warnings = batch_enrich(
        enricher=_BoomEnricher(boom_id=concepts[2].id),
        concepts=concepts, sections=_sections(concepts), max_workers=3,
    )
    assert len(enriched) == 5  # 没有因一个坏概念中止
    assert any(concepts[2].id in w and "enrich_failed" in w for w in warnings)
    # 坏的那个保留原（confidence 0.4），其余富化到 0.8
    boom = next(c for c in enriched if c.id == concepts[2].id)
    assert boom.confidence == pytest.approx(0.4)
    assert sum(1 for c in enriched if c.confidence == pytest.approx(0.8)) == 4


def test_get_builder_forwards_checkpoint_and_workers():
    """get_builder 透传 max_workers/checkpoint_path（Fix D）。"""
    from servers.knowledge_mcp.kg_builder import get_builder
    b = get_builder("concept", llm=MockLLMProvider(canned_responses=[]), max_workers=8, checkpoint_path=Path("x.jsonl"))
    assert b.max_workers == 8
    assert b.checkpoint_path == Path("x.jsonl")


def test_checkpoint_load_missing_file_is_empty(tmp_path: Path):
    cp = EnrichCheckpoint(tmp_path / "nope.jsonl")
    cp.load()
    assert cp.get("anything") is None
