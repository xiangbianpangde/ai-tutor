"""IntentClassifier 契约测试。

5 类意图（来自 spec interrupt() §4 与 PGFGA）:
- concept_question     学生在问当前/相关概念是什么 / 怎么用
- prereq_gap           学生卡在前置知识（"我不懂 X 是什么"）
- pace_complaint       学生抱怨节奏/难度 / 想跳过
- distraction          离题（不相关的话题 / 闲聊）
- cognitive_overload   学生表现/表达出疲惫 / 信息过载

接口:
  classify(question, current_concept_name=...) → IntentResult
    .intent: 5 选 1
    .confidence: 0..1
    .evidence: str

行为:
- LLM 可用 → JSON 分类
- LLM 不可用 → 关键词降级（基础启发式）
- 完全无法判断 → 默认 distraction（保守）
"""
from __future__ import annotations

import json

from shared.llm_client import MockLLMProvider, StubLLMProvider


def _resp(intent: str, conf: float = 0.85, evidence: str = "ok") -> str:
    return json.dumps({"intent": intent, "confidence": conf, "evidence": evidence}, ensure_ascii=False)


def test_classify_concept_question() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    llm = MockLLMProvider(canned_responses=[_resp("concept_question")])
    r = IntentClassifier(llm=llm).classify(
        question="什么是词袋模型？", current_concept_name="词袋模型",
    )
    assert r.intent == "concept_question"
    assert r.confidence > 0.5


def test_classify_prereq_gap() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    llm = MockLLMProvider(canned_responses=[_resp("prereq_gap")])
    r = IntentClassifier(llm=llm).classify(
        question="我不懂向量是什么，能先解释下吗？",
        current_concept_name="词袋模型",
    )
    assert r.intent == "prereq_gap"


def test_classify_pace_complaint() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    llm = MockLLMProvider(canned_responses=[_resp("pace_complaint")])
    r = IntentClassifier(llm=llm).classify(
        question="能不能快一点？这部分我已经会了",
        current_concept_name="词袋模型",
    )
    assert r.intent == "pace_complaint"


def test_classify_cognitive_overload() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    llm = MockLLMProvider(canned_responses=[_resp("cognitive_overload")])
    r = IntentClassifier(llm=llm).classify(
        question="我有点晕了，信息太多",
        current_concept_name="词袋模型",
    )
    assert r.intent == "cognitive_overload"


def test_classify_distraction() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    llm = MockLLMProvider(canned_responses=[_resp("distraction")])
    r = IntentClassifier(llm=llm).classify(
        question="今天天气真好",
        current_concept_name="词袋模型",
    )
    assert r.intent == "distraction"


def test_fallback_keyword_concept_question() -> None:
    """LLM 不可用时关键词降级：'什么是 / 怎么 / 解释' 等触发 concept_question。"""
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    cl = IntentClassifier(llm=StubLLMProvider())
    r = cl.classify(question="什么是词袋模型？", current_concept_name="词袋模型")
    assert r.intent == "concept_question"


def test_fallback_keyword_pace_complaint() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    cl = IntentClassifier(llm=StubLLMProvider())
    r = cl.classify(question="快一点吧，太慢了", current_concept_name="x")
    assert r.intent == "pace_complaint"


def test_fallback_keyword_overload() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    cl = IntentClassifier(llm=StubLLMProvider())
    r = cl.classify(question="累了 头疼 想休息", current_concept_name="x")
    assert r.intent == "cognitive_overload"


def test_fallback_invalid_intent_defaults_to_distraction() -> None:
    """LLM 返回 5 类之外的 intent → 默认 distraction（保守）。"""
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    bad = json.dumps({"intent": "alien_intent", "confidence": 0.9}, ensure_ascii=False)
    llm = MockLLMProvider(canned_responses=[bad])
    r = IntentClassifier(llm=llm).classify(
        question="x", current_concept_name="x",
    )
    assert r.intent == "distraction"


def test_classify_empty_question_returns_distraction() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    llm = MockLLMProvider(canned_responses=[])
    r = IntentClassifier(llm=llm).classify(
        question="", current_concept_name="x",
    )
    assert r.intent == "distraction"
    # 空问题不应调 LLM
    assert len(llm.calls) == 0


def test_clamps_confidence() -> None:
    from servers.tutoring_mcp.intent_classifier import IntentClassifier

    bad = json.dumps({"intent": "concept_question", "confidence": 1.5}, ensure_ascii=False)
    llm = MockLLMProvider(canned_responses=[bad])
    r = IntentClassifier(llm=llm).classify(question="x", current_concept_name="x")
    assert 0.0 <= r.confidence <= 1.0
