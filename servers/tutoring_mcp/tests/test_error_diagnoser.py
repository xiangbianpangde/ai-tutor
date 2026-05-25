"""ErrorDiagnoser 契约测试。

diagnose(concept, student_answer, score_evidence) → ErrorDiagnosis

- LLM 在错答时给出: error_type / root_concept_id / surface_concept_id / evidence / remediation
- correct 答案不应触发诊断（返回 None）
- LLM 不可用时返回 type='blank' 默认值
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
)


def _concept(cid: str = "ml:1:word_bag", name: str = "词袋模型") -> Concept:
    return Concept(
        id=cid,
        names=[name],
        category="definition",
        definition=f"{name} 把文本转词频向量",
        informal_description="",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.5, domain="ml"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0,
            formula_density=0.1, coupling=0.1,
            cognitive_load_estimate=0.3, typical_learning_time_min=15,
        ),
        confidence=0.85,
    )


def _diag_response(error_type: str = "concept_confusion") -> str:
    return json.dumps({
        "error_type": error_type,
        "root_concept_id": "ml:1:word_bag",
        "surface_concept_id": "ml:1:word_bag",
        "confidence": 0.85,
        "evidence": ["学生把词袋当成了 TF-IDF"],
        "remediation_suggestion": "对比词袋（只算词频）和 TF-IDF（频次 × 稀有度）",
    }, ensure_ascii=False)


def test_diagnose_returns_none_for_correct() -> None:
    """correct 答案不应触发诊断（节省调用）。"""
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    llm = MockLLMProvider(canned_responses=["不应调用"])
    d = ErrorDiagnoser(llm=llm).diagnose(
        concept=_concept(),
        student_answer="词袋模型把文本转词频向量",
        correctness="correct",
        score_evidence="LLM 判 correct",
    )
    assert d is None
    assert len(llm.calls) == 0


def test_diagnose_incorrect_gives_full_diagnosis() -> None:
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    llm = MockLLMProvider(canned_responses=[_diag_response()])
    d = ErrorDiagnoser(llm=llm).diagnose(
        concept=_concept(),
        student_answer="词袋就是 TF-IDF",
        correctness="incorrect",
        score_evidence="完全混淆两个概念",
    )
    assert d is not None
    assert d.error_type == "concept_confusion"
    assert d.root_concept_id == "ml:1:word_bag"
    assert "对比" in d.remediation_suggestion
    assert d.confidence == 0.85


def test_diagnose_partial_also_diagnoses() -> None:
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    llm = MockLLMProvider(canned_responses=[_diag_response("logic_gap")])
    d = ErrorDiagnoser(llm=llm).diagnose(
        concept=_concept(),
        student_answer="词袋统计词频但不算停用词",
        correctness="partial",
        score_evidence="缺失语序信息这一点",
    )
    assert d is not None
    assert d.error_type == "logic_gap"


def test_diagnose_falls_back_when_llm_unavailable() -> None:
    """StubLLM → 返回 type='blank' 默认诊断，不抛错。"""
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    d = ErrorDiagnoser(llm=StubLLMProvider()).diagnose(
        concept=_concept(),
        student_answer="完全错的答案",
        correctness="incorrect",
        score_evidence="",
    )
    assert d is not None
    assert d.error_type == "blank"
    assert d.root_concept_id == "ml:1:word_bag"


def test_diagnose_clamps_unknown_error_type() -> None:
    """LLM 返回非 10 种枚举的 error_type → 安全降到 'blank'。"""
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    bad = json.dumps({"error_type": "alien_type", "evidence": ["x"]}, ensure_ascii=False)
    d = ErrorDiagnoser(llm=MockLLMProvider(canned_responses=[bad])).diagnose(
        concept=_concept(),
        student_answer="x",
        correctness="incorrect",
        score_evidence="",
    )
    assert d is not None
    assert d.error_type in {
        "concept_confusion", "symbol_mistake", "logic_gap",
        "syntax_error", "prereq_gap", "overgeneralization",
        "arithmetic_mistake", "reading_error", "careless", "blank",
    }


def test_diagnose_tolerates_invalid_json() -> None:
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    llm = MockLLMProvider(canned_responses=["不是 JSON"])
    d = ErrorDiagnoser(llm=llm).diagnose(
        concept=_concept(),
        student_answer="x",
        correctness="incorrect",
        score_evidence="",
    )
    assert d is not None
    assert d.error_type == "blank"


def test_regex_fast_path_epsilon_delta_reversal_skips_llm() -> None:
    """ε-δ 量词顺序反了 → 正则快速路径确诊 symbol_mistake，不调 LLM。"""
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    llm = MockLLMProvider(canned_responses=["不应调用"])
    d = ErrorDiagnoser(llm=llm).diagnose(
        concept=_concept(name="函数极限"),
        student_answer="存在 ε>0，对任意 δ>0 使得 |f(x)-L|<ε",
        correctness="incorrect",
        score_evidence="",
    )
    assert d is not None
    assert d.error_type == "symbol_mistake"
    assert d.confidence == 0.8
    assert len(llm.calls) == 0  # 快速路径短路了 LLM


def test_regex_fast_path_sufficient_vs_iff() -> None:
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    llm = MockLLMProvider(canned_responses=["不应调用"])
    d = ErrorDiagnoser(llm=llm).diagnose(
        concept=_concept(name="充要条件"),
        student_answer="如果可导则连续，反之不成立，所以可导是连续的充要条件",
        correctness="incorrect",
        score_evidence="",
    )
    assert d is not None
    assert d.error_type == "symbol_mistake"
    assert len(llm.calls) == 0


def test_non_matching_answer_still_uses_llm() -> None:
    """不命中正则的普通错答仍走 LLM（快速路径不影响既有主路径）。"""
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    llm = MockLLMProvider(canned_responses=[_diag_response("concept_confusion")])
    d = ErrorDiagnoser(llm=llm).diagnose(
        concept=_concept(),
        student_answer="词袋就是 TF-IDF",
        correctness="incorrect",
        score_evidence="",
    )
    assert d is not None
    assert d.error_type == "concept_confusion"
    assert len(llm.calls) == 1  # 正则未命中 → 调了 LLM


def test_diagnose_includes_concept_in_prompt() -> None:
    from servers.tutoring_mcp.error_diagnoser import ErrorDiagnoser

    llm = MockLLMProvider(canned_responses=[_diag_response()])
    ErrorDiagnoser(llm=llm).diagnose(
        concept=_concept(name="稀疏向量"),
        student_answer="x",
        correctness="incorrect",
        score_evidence="",
    )
    full_prompt = " ".join(m["content"] for m in llm.calls[0]["messages"])
    assert "稀疏向量" in full_prompt
