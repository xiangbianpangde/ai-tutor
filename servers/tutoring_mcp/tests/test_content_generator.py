"""教学内容 LLM 生成 (P0 #1) 测试。

ContentGenerator.enrich：把策略产出的"模板填空"动作，用 LLM 改写成有例子/直觉的
真实讲解内容。只在 provider.supports_generation 时调用 LLM；否则原样返回（模板兜底）。
"""
from __future__ import annotations

import pytest

from servers.tutoring_mcp.content_generator import ContentGenerator
from shared.llm_client import MockLLMProvider, StubLLMProvider
from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    TeachingAction,
)


def _concept() -> Concept:
    return Concept(
        id="math:2.1:partial",
        names=["偏导数"],
        category="definition",
        definition="函数对其中一个变量的变化率",
        informal_description="衡量曲面在某方向有多陡",
        classification=ConceptClassification(bloom_level="understand", abstract_level=0.6, domain="calculus"),
        difficulty=ConceptDifficulty(
            prereq_count=1, prereq_max_depth=1, formula_density=0.5, coupling=0.3,
            cognitive_load_estimate=0.5, typical_learning_time_min=30,
        ),
        common_misconceptions=["偏导数和其他变量没关系"],
        confidence=0.85,
    )


def _action(type_="explain", content="模板内容") -> TeachingAction:
    return TeachingAction(type=type_, content=content, estimated_duration_min=3, metadata={"k": "v"})


def _real_llm(text: str) -> MockLLMProvider:
    """模拟真实 provider：supports_generation=True。"""
    return MockLLMProvider(canned_responses=[text], supports_generation=True)


# --------------------------------------------------------------------------- #
# 不支持生成 → 原样返回（保持既有 Mock/Stub 测试不受影响）
# --------------------------------------------------------------------------- #


def test_stub_returns_action_unchanged():
    gen = ContentGenerator(StubLLMProvider())
    act = _action()
    out = gen.enrich(action=act, concept=_concept())
    assert out.content == "模板内容"
    assert out is act or out.content == act.content


def test_mock_without_generation_flag_unchanged():
    """默认 MockLLMProvider（supports_generation=False）不被内容生成消费 canned。"""
    llm = MockLLMProvider(canned_responses=["不该被用到"])
    gen = ContentGenerator(llm)
    out = gen.enrich(action=_action(), concept=_concept())
    assert out.content == "模板内容"
    assert llm.calls == []  # 根本没调 LLM


# --------------------------------------------------------------------------- #
# 支持生成 → 用 LLM 内容替换
# --------------------------------------------------------------------------- #


def test_enrich_replaces_content_for_explain():
    llm = _real_llm("偏导数就像只沿东西方向走时的坡度……（生动讲解）")
    gen = ContentGenerator(llm)
    out = gen.enrich(action=_action("explain"), concept=_concept())
    assert "生动讲解" in out.content
    assert out.type == "explain"
    assert out.metadata.get("generated") is True
    assert out.metadata.get("k") == "v"  # 保留原 metadata
    assert len(llm.calls) == 1
    # prompt 里带了概念名/定义
    prompt = llm.calls[0]["messages"][-1]["content"]
    assert "偏导数" in prompt


@pytest.mark.parametrize("atype", ["explain", "show_example", "give_exercise", "provide_hint", "ask_question", "reveal_answer"])
def test_enrichable_types_call_llm(atype):
    llm = _real_llm("生成的内容")
    gen = ContentGenerator(llm)
    out = gen.enrich(action=_action(atype), concept=_concept())
    assert out.content == "生成的内容"
    assert len(llm.calls) == 1


@pytest.mark.parametrize("atype", ["break_suggestion", "reflection", "checkpoint", "review"])
def test_meta_types_not_enriched(atype):
    """休息/反思/检查点等元动作不需要 LLM 改写。"""
    llm = _real_llm("不该用到")
    gen = ContentGenerator(llm)
    out = gen.enrich(action=_action(atype, "原始"), concept=_concept())
    assert out.content == "原始"
    assert llm.calls == []


# --------------------------------------------------------------------------- #
# 失败兜底
# --------------------------------------------------------------------------- #


def test_empty_llm_response_falls_back_to_template():
    llm = _real_llm("   ")  # 空白
    gen = ContentGenerator(llm)
    out = gen.enrich(action=_action("explain", "模板兜底"), concept=_concept())
    assert out.content == "模板兜底"


def test_llm_exception_falls_back_to_template():
    # 没有 canned → MockLLM 抛 PLUGIN_NOT_AVAILABLE
    llm = MockLLMProvider(canned_responses=[], supports_generation=True)
    gen = ContentGenerator(llm)
    out = gen.enrich(action=_action("explain", "模板兜底"), concept=_concept())
    assert out.content == "模板兜底"


def test_empty_names_does_not_crash():
    """names 为空（schema 允许）+ 真实 LLM → 原样返回，不抛 IndexError（code-review）。"""
    c = _concept()
    c = c.model_copy(update={"names": []})
    gen = ContentGenerator(_real_llm("x"))
    out = gen.enrich(action=_action("explain", "模板"), concept=c)
    assert out.content == "模板"  # 兜底，不崩


def test_scaffold_level_influences_prompt():
    llm = _real_llm("x")
    gen = ContentGenerator(llm)
    gen.enrich(action=_action("explain"), concept=_concept(), scaffold_level=3)
    p_high = llm.calls[0]["messages"][-1]["content"]

    llm2 = _real_llm("x")
    ContentGenerator(llm2).enrich(action=_action("explain"), concept=_concept(), scaffold_level=0)
    p_low = llm2.calls[0]["messages"][-1]["content"]
    assert p_high != p_low  # 脚手架级别进入了 prompt
