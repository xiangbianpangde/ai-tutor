"""LLMScorer 契约测试。

score(concept, student_answer) → ScoreResult{correctness, evidence, suggested_remediation, raw_score}

- LLM 返回合法 JSON → 用 LLM 判分
- LLM 返回乱码 → 回退到 2-gram 启发式
- StubLLMProvider → 直接走启发式（不抛错）
"""
from __future__ import annotations

import json

import pytest

from shared.llm_client import MockLLMProvider, StubLLMProvider
from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
)


def _concept(name: str = "词袋模型") -> Concept:
    return Concept(
        id="ml:1:bag_of_words",
        names=[name],
        category="definition",
        definition=f"{name} 把文本表示为词频向量，忽略词序。",
        informal_description="把所有词丢进袋子里数次数",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.5, domain="ml"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0,
            formula_density=0.1, coupling=0.2,
            cognitive_load_estimate=0.3, typical_learning_time_min=15,
        ),
        confidence=0.85,
    )


def _llm_correct() -> str:
    return json.dumps({
        "correctness": "correct",
        "raw_score": 0.92,
        "evidence": "学生正确指出'词频向量'+'忽略词序'两个核心要点。",
        "suggested_remediation": "",
    }, ensure_ascii=False)


def _llm_partial() -> str:
    return json.dumps({
        "correctness": "partial",
        "raw_score": 0.55,
        "evidence": "提到了词频但漏掉了'忽略词序'。",
        "suggested_remediation": "提醒学生词袋丢失语序信息。",
    }, ensure_ascii=False)


def _llm_incorrect() -> str:
    return json.dumps({
        "correctness": "incorrect",
        "raw_score": 0.05,
        "evidence": "学生答的是 TF-IDF，不是词袋。",
        "suggested_remediation": "区分词袋与 TF-IDF：前者只算词频。",
    }, ensure_ascii=False)


def test_score_correct() -> None:
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    llm = MockLLMProvider(canned_responses=[_llm_correct()])
    r = LLMScorer(llm=llm).score(concept=_concept(), student_answer="词袋就是统计词频，丢词序")
    assert r.correctness == "correct"
    assert r.raw_score > 0.8
    assert "词频" in r.evidence or "正确" in r.evidence


def test_score_partial() -> None:
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    llm = MockLLMProvider(canned_responses=[_llm_partial()])
    r = LLMScorer(llm=llm).score(concept=_concept(), student_answer="词袋模型统计词频")
    assert r.correctness == "partial"
    assert r.suggested_remediation


def test_score_incorrect() -> None:
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    llm = MockLLMProvider(canned_responses=[_llm_incorrect()])
    r = LLMScorer(llm=llm).score(concept=_concept(), student_answer="词袋就是 TF-IDF")
    assert r.correctness == "incorrect"


def test_score_falls_back_when_llm_returns_garbage() -> None:
    """LLM 返回非 JSON → 回退到 2-gram 启发式。"""
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    llm = MockLLMProvider(canned_responses=["这不是 JSON 是散文"])
    # 含"词袋"应启发式判 correct
    r = LLMScorer(llm=llm).score(concept=_concept(), student_answer="词袋模型就是统计词频")
    assert r.correctness == "correct"
    assert r.evidence  # 应有 fallback 说明


def test_score_with_stub_llm_uses_heuristic() -> None:
    """StubLLMProvider 调 chat 会抛 PLUGIN_NOT_AVAILABLE → 应捕获并走启发式。"""
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    scorer = LLMScorer(llm=StubLLMProvider())
    r = scorer.score(concept=_concept(), student_answer="词袋模型是统计词频")
    assert r.correctness == "correct"

    r2 = scorer.score(concept=_concept(), student_answer="完全不相关的回答")
    assert r2.correctness in ("partial", "incorrect")

    r3 = scorer.score(concept=_concept(), student_answer="")
    assert r3.correctness == "incorrect"


def test_score_empty_answer_is_incorrect_without_llm_call() -> None:
    """空回答应立即判 incorrect，不浪费 LLM 调用。"""
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    llm = MockLLMProvider(canned_responses=["不应被调用"])
    r = LLMScorer(llm=llm).score(concept=_concept(), student_answer="   ")
    assert r.correctness == "incorrect"
    assert len(llm.calls) == 0


def test_score_clamps_raw_score_to_unit() -> None:
    """LLM 给 raw_score=1.5 这种 → clamp 到 [0,1]。"""
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    bad = json.dumps({"correctness": "correct", "raw_score": 1.5}, ensure_ascii=False)
    r = LLMScorer(llm=MockLLMProvider(canned_responses=[bad])).score(
        concept=_concept(), student_answer="任意"
    )
    assert 0.0 <= r.raw_score <= 1.0


# ------------------- FIX-D：判分题目感知（#18/#20 回归） ------------------- #


def test_score_passes_question_and_off_topic_rule() -> None:
    """传了题目 → prompt 必须含题目原文与「答非所问最高 partial」规则。"""
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    llm = MockLLMProvider(canned_responses=[_llm_correct()])
    r = LLMScorer(llm=llm).score(
        concept=_concept(),
        student_answer="词袋统计词频，不保留词序",
        question="请判断：词袋模型保留词序，对吗？",
    )
    assert r.correctness == "correct"
    prompt = llm.calls[-1]["messages"][-1]["content"]
    assert "请判断：词袋模型保留词序，对吗？" in prompt
    assert "答非所问" in prompt


def test_score_without_question_keeps_legacy_prompt() -> None:
    """不传题目 → 退化为旧 prompt（只比对概念定义），不带答非所问规则。"""
    from servers.tutoring_mcp.llm_scorer import LLMScorer

    llm = MockLLMProvider(canned_responses=[_llm_correct()])
    LLMScorer(llm=llm).score(concept=_concept(), student_answer="词袋统计词频")
    prompt = llm.calls[-1]["messages"][-1]["content"]
    assert "答非所问" not in prompt
    assert "题目（学生正在回答的提问/练习）" not in prompt
