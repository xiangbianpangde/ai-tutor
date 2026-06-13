"""教学反馈分级 (P1 #7) 测试。

FeedbackGenerator 是反馈三级管道的 L3：把 L1（按 correctness 的模板）+ L2（带
remediation 的针对性模板）用 LLM 润色成温暖、具体、非评判的反馈。
仅在 provider.supports_generation 时调用 LLM；否则原样返回传入的 fallback 模板。
"""
from __future__ import annotations

import pytest

from servers.tutoring_mcp.feedback_generator import FeedbackGenerator
from shared.llm_client import MockLLMProvider, StubLLMProvider
from shared.schemas import Concept, ConceptClassification, ConceptDifficulty


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
        confidence=0.85,
    )


def _real(text: str) -> MockLLMProvider:
    return MockLLMProvider(canned_responses=[text], supports_generation=True)


def _gen(correctness, llm, **kw):
    return FeedbackGenerator(llm).generate(
        correctness=correctness, concept=_concept(),
        student_answer=kw.get("answer", "学生的答案"),
        evidence=kw.get("evidence", "命中核心"),
        remediation=kw.get("remediation", ""),
        fallback=kw.get("fallback", "模板反馈"),
    )


# --------------------------------------------------------------------------- #
# 不支持生成 → 返回 fallback（保持既有 respond 行为）
# --------------------------------------------------------------------------- #


def test_stub_returns_fallback():
    out = _gen("correct", StubLLMProvider(), fallback="模板反馈X")
    assert out == "模板反馈X"


def test_mock_without_flag_returns_fallback_no_call():
    llm = MockLLMProvider(canned_responses=["不该用到"])  # supports_generation=False
    out = _gen("partial", llm, fallback="模板反馈Y")
    assert out == "模板反馈Y"
    assert llm.calls == []


# --------------------------------------------------------------------------- #
# 支持生成 → LLM 润色
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("corr", ["correct", "partial", "incorrect"])
def test_real_llm_polishes(corr):
    llm = _real("你把变化率和方向联系起来了，这正是偏导的核心。")
    out = _gen(corr, llm)
    assert out == "你把变化率和方向联系起来了，这正是偏导的核心。"
    assert len(llm.calls) == 1
    prompt = llm.calls[0]["messages"][-1]["content"]
    assert "偏导数" in prompt
    assert "学生的答案" in prompt  # 学生答案进了 prompt


def test_remediation_enters_prompt_for_incorrect():
    llm = _real("反馈")
    _gen("incorrect", llm, remediation="回到一元导数的定义再看一遍")
    prompt = llm.calls[0]["messages"][-1]["content"]
    assert "回到一元导数" in prompt


def test_empty_response_falls_back():
    out = _gen("correct", _real("  "), fallback="兜底")
    assert out == "兜底"


def test_exception_falls_back():
    llm = MockLLMProvider(canned_responses=[], supports_generation=True)  # 用尽即抛
    out = _gen("partial", llm, fallback="兜底")
    assert out == "兜底"


def test_correctness_changes_prompt_tone():
    llm_c = _real("x")
    _gen("correct", llm_c)
    llm_i = _real("x")
    _gen("incorrect", llm_i)
    assert llm_c.calls[0]["messages"][-1]["content"] != llm_i.calls[0]["messages"][-1]["content"]
