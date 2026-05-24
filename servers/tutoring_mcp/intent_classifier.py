"""学生打断意图分类 — 5 类。

接口:
    classifier.classify(question, current_concept_name) → IntentResult

LLM 优先；不可用 / 解析失败 → 关键词降级；完全不确定 → distraction（最保守）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from shared.errors import TutorError
from shared.llm_client import LLMProvider
from shared.logging_config import get_logger

logger = get_logger("tutoring_mcp.intent_classifier")


Intent = Literal[
    "concept_question", "prereq_gap", "pace_complaint",
    "distraction", "cognitive_overload",
]
_VALID = {"concept_question", "prereq_gap", "pace_complaint", "distraction", "cognitive_overload"}


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    evidence: str = ""


_KEYWORDS: dict[str, tuple[str, ...]] = {
    # 优先级：更"具体"的疑问 > 更"宽泛"的无能感
    "cognitive_overload": ("累", "晕", "脑袋", "信息太多", "晕了", "头疼", "懵", "休息"),
    "pace_complaint": ("太慢", "快一点", "快点", "跳过", "已经会", "无聊", "再快"),
    # concept_question 先于 prereq_gap：句中同时含 "为什么"+"不会" 这种
    # 复合问，意图重心是 concept_question；prereq_gap 更适合"我连基础都不会"
    "concept_question": ("是什么", "什么是", "怎么用", "为什么", "举个例子", "区别"),
    "prereq_gap": ("不懂", "不会", "先解释", "前置", "基础"),
    # distraction 不用关键词；其他都没命中 → 默认 distraction
}


_SYSTEM = (
    "你是教学打断意图分类器。学生在学习中打断老师提了一个问题，"
    "判断 5 类意图之一。只输出 JSON。"
)


def _build_prompt(question: str, concept_name: str | None) -> str:
    return f"""学生当前在学：{concept_name or '(未知)'}
学生说：{question}

判断他/她打断的意图，输出 JSON：
{{
  "intent": "concept_question|prereq_gap|pace_complaint|distraction|cognitive_overload",
  "confidence": 0.0~1.0,
  "evidence": "一句话依据"
}}

判别标准：
- concept_question:    在问当前/相关概念是什么、怎么用、为什么
- prereq_gap:          学生卡在前置（"我不懂 X 是什么"、"先解释 Y 吧"）
- pace_complaint:      抱怨节奏/难度、想跳过、嫌慢
- cognitive_overload:  表现疲惫、信息过载（晕、累、想休息）
- distraction:         离题闲聊、与学习无关
"""


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        pass
    s, e = text.find("{"), text.rfind("}")
    if s >= 0 and e > s:
        try:
            out = json.loads(text[s:e+1])
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _heuristic_classify(question: str) -> IntentResult:
    """关键词匹配；按 KEYWORDS 字典顺序优先级。"""
    q = question.strip()
    if not q:
        return IntentResult(intent="distraction", confidence=0.3, evidence="空问题")
    for intent, words in _KEYWORDS.items():
        for w in words:
            if w in q:
                return IntentResult(
                    intent=intent,  # type: ignore[arg-type]
                    confidence=0.6,
                    evidence=f"启发式：含关键词 '{w}'",
                )
    return IntentResult(intent="distraction", confidence=0.4, evidence="启发式：未命中关键词")


class IntentClassifier:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def classify(
        self, *, question: str, current_concept_name: str | None = None,
    ) -> IntentResult:
        if not (question or "").strip():
            return IntentResult(intent="distraction", confidence=0.3, evidence="空问题")

        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": _build_prompt(question, current_concept_name)},
                ],
                temperature=0.1,
                max_tokens=256,
            )
        except TutorError as exc:
            if exc.code == "PLUGIN_NOT_AVAILABLE":
                return _heuristic_classify(question)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("intent.llm_exception", error=str(exc))
            return _heuristic_classify(question)

        data = _parse_json(resp.content)
        if data is None:
            return _heuristic_classify(question)

        intent = data.get("intent")
        if intent not in _VALID:
            return IntentResult(intent="distraction", confidence=0.3, evidence=f"LLM 返回未知 intent={intent!r}")

        conf = data.get("confidence", 0.7)
        try:
            conf = max(0.0, min(1.0, float(conf)))
        except (TypeError, ValueError):
            conf = 0.5

        return IntentResult(
            intent=intent,  # type: ignore[arg-type]
            confidence=conf,
            evidence=str(data.get("evidence") or "")[:200],
        )
