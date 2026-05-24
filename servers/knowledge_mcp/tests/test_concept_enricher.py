"""ConceptEnricher 契约测试。

输入: toc 模式的 Concept 骨架 + 该节的正文文本 + LLMProvider
输出: 富化后的 Concept（新对象），填充:
  - definition（真实定义，而非纯标题）
  - informal_description（口语化描述）
  - examples（[Example] 列表）
  - common_misconceptions（高频误解列表）
  - classification.bloom_level（LLM 校正）
  - confidence（LLM 自评，覆盖 toc 默认 0.4）

容错:
- LLM 返回非 JSON 或 schema 不合法 → 返回原 concept + warning（不抛错）
- LLM 抛 TutorError(PLUGIN_NOT_AVAILABLE) → 上抛（调用方决定降级）
- LLM 抛其他异常 → 包装成 warning，返回原 concept
"""
from __future__ import annotations

import json

import pytest

from shared.errors import TutorError
from shared.llm_client import MockLLMProvider, StubLLMProvider
from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    SourceRef,
)


def _toc_concept(
    cid: str = "test:1.1:word_bag",
    name: str = "词袋模型",
) -> Concept:
    return Concept(
        id=cid,
        names=[name],
        category="definition",
        definition=name,
        informal_description="（toc 占位）",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.5, domain="test"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0,
            prereq_max_depth=0,
            formula_density=0.1,
            coupling=0.1,
            cognitive_load_estimate=0.3,
            typical_learning_time_min=30,
        ),
        confidence=0.4,
        sources=[SourceRef(type="textbook", ref="x.md")],
    )


def _llm_json_ok() -> str:
    return json.dumps({
        "definition": "词袋模型把文本表示为词频向量，忽略词序。",
        "informal_description": "想象把所有词丢进一个袋子里，只数每个词出现多少次。",
        "examples": [
            {"text": "对'我爱学习' 用词袋得到 {我:1, 爱:1, 学习:1}", "type": "computation"},
        ],
        "common_misconceptions": [
            "误认为词袋会保留词序",
            "忽略了高频停用词的影响",
        ],
        "bloom_level": "understand",
        "confidence": 0.85,
    }, ensure_ascii=False)


def test_enricher_sets_difficulty_signals() -> None:
    """P2 #11：LLM 返回 abstract_level/formula_density/cognitive_load_estimate → 落库（clamp）。"""
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    resp = json.dumps({
        "definition": "拉格朗日中值定理……",
        "abstract_level": 0.85,
        "formula_density": 0.7,
        "cognitive_load_estimate": 0.6,
        "confidence": 0.8,
    }, ensure_ascii=False)
    ec, w = ConceptEnricher(llm=MockLLMProvider(canned_responses=[resp])).enrich(
        concept=_toc_concept(), body_text="正文"
    )
    assert ec.classification.abstract_level == pytest.approx(0.85)
    assert ec.difficulty.formula_density == pytest.approx(0.7)
    assert ec.difficulty.cognitive_load_estimate == pytest.approx(0.6)


def test_enricher_clamps_out_of_range_signals() -> None:
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    resp = json.dumps({"abstract_level": 1.5, "formula_density": -0.2, "cognitive_load_estimate": 2.0})
    ec, _ = ConceptEnricher(llm=MockLLMProvider(canned_responses=[resp])).enrich(
        concept=_toc_concept(), body_text="x"
    )
    assert ec.classification.abstract_level == 1.0
    assert ec.difficulty.formula_density == 0.0
    assert ec.difficulty.cognitive_load_estimate == 1.0


def test_enricher_missing_signals_keeps_toc_defaults() -> None:
    """不返回难度信号时保持 toc 默认（向后兼容，既有 canned 响应不受影响）。"""
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    resp = json.dumps({"definition": "d", "bloom_level": "apply", "confidence": 0.8})
    ec, _ = ConceptEnricher(llm=MockLLMProvider(canned_responses=[resp])).enrich(
        concept=_toc_concept(), body_text="x"
    )
    assert ec.classification.abstract_level == pytest.approx(0.5)   # toc 默认
    assert ec.difficulty.formula_density == pytest.approx(0.1)      # toc 默认
    assert ec.classification.bloom_level == "apply"                 # bloom 仍更新


def test_enricher_fills_definition_and_description() -> None:
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    llm = MockLLMProvider(canned_responses=[_llm_json_ok()])
    enricher = ConceptEnricher(llm=llm)
    enriched, warning = enricher.enrich(
        concept=_toc_concept(),
        body_text="词袋模型(Bag of Words)\n这是文本向量化方法 ...",
    )
    assert warning is None
    assert "词频向量" in enriched.definition
    assert "袋子" in enriched.informal_description
    assert len(enriched.examples) == 1
    assert enriched.common_misconceptions == [
        "误认为词袋会保留词序",
        "忽略了高频停用词的影响",
    ]
    assert enriched.confidence == pytest.approx(0.85)


def test_enricher_calls_llm_once_per_concept() -> None:
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    llm = MockLLMProvider(canned_responses=[_llm_json_ok()])
    ConceptEnricher(llm=llm).enrich(concept=_toc_concept(), body_text="...")
    assert len(llm.calls) == 1


def test_enricher_includes_concept_name_and_body_in_prompt() -> None:
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    llm = MockLLMProvider(canned_responses=[_llm_json_ok()])
    body = "稀疏向量是大部分元素为 0 的向量。"
    ConceptEnricher(llm=llm).enrich(
        concept=_toc_concept(name="稀疏向量"),
        body_text=body,
    )
    messages = llm.calls[0]["messages"]
    full_prompt = " ".join(m["content"] for m in messages)
    assert "稀疏向量" in full_prompt
    assert body in full_prompt


def test_enricher_returns_new_concept_not_mutating_input() -> None:
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    original = _toc_concept()
    original_def = original.definition
    llm = MockLLMProvider(canned_responses=[_llm_json_ok()])
    enriched, _ = ConceptEnricher(llm=llm).enrich(concept=original, body_text="...")
    assert original.definition == original_def  # 输入不变
    assert enriched is not original
    assert enriched.definition != original_def  # 输出已变


def test_enricher_tolerates_invalid_json() -> None:
    """LLM 返回非 JSON → 返回原 concept + warning，不抛错。"""
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    llm = MockLLMProvider(canned_responses=["这不是 JSON，是一段散文。"])
    enricher = ConceptEnricher(llm=llm)
    original = _toc_concept()
    enriched, warning = enricher.enrich(concept=original, body_text="...")
    assert enriched.definition == original.definition  # 未变
    assert enriched.confidence == original.confidence  # 未变
    assert warning is not None
    assert "json" in warning.lower() or "parse" in warning.lower()


def test_enricher_tolerates_partial_json() -> None:
    """LLM 返回只含部分字段的 JSON → 已填字段更新，缺字段保留。"""
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    partial = json.dumps({"definition": "新定义"}, ensure_ascii=False)
    llm = MockLLMProvider(canned_responses=[partial])
    enricher = ConceptEnricher(llm=llm)
    original = _toc_concept()
    enriched, warning = enricher.enrich(concept=original, body_text="...")
    assert warning is None
    assert enriched.definition == "新定义"
    assert enriched.informal_description == original.informal_description  # 未提供 → 保留


def test_enricher_propagates_plugin_unavailable() -> None:
    """LLMProvider stub 抛 PLUGIN_NOT_AVAILABLE 时 enricher 应往上抛，不吞。"""
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    enricher = ConceptEnricher(llm=StubLLMProvider())
    with pytest.raises(TutorError) as exc:
        enricher.enrich(concept=_toc_concept(), body_text="...")
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"


def test_enricher_validates_bloom_level() -> None:
    """LLM 返回的 bloom_level 不在 6 种枚举内 → 忽略此字段，其他字段照常更新。"""
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    bad_bloom = json.dumps({
        "definition": "新定义",
        "bloom_level": "memorize",  # 不在 remember/understand/apply/analyze/evaluate/create
    }, ensure_ascii=False)
    llm = MockLLMProvider(canned_responses=[bad_bloom])
    enriched, warning = ConceptEnricher(llm=llm).enrich(
        concept=_toc_concept(), body_text="..."
    )
    assert enriched.definition == "新定义"
    assert enriched.classification.bloom_level == "understand"  # 保留 toc 原值
    assert warning is not None
    assert "bloom" in warning.lower()


def test_enricher_clamps_confidence_to_unit_interval() -> None:
    """LLM 返回 confidence=1.5 这类越界值 → clamp 到 [0,1]。"""
    from servers.knowledge_mcp.concept_enricher import ConceptEnricher

    out_of_range = json.dumps({"definition": "x", "confidence": 1.5}, ensure_ascii=False)
    llm = MockLLMProvider(canned_responses=[out_of_range])
    enriched, _ = ConceptEnricher(llm=llm).enrich(
        concept=_toc_concept(), body_text="..."
    )
    assert 0.0 <= enriched.confidence <= 1.0
