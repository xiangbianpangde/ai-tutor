"""LLM 语义判分 — 替换 engine 中原本的 2-gram 启发式。

设计:
- 优先 LLM；解析失败 / LLM 不可用 → 回退到 2-gram 启发式（保留 spine v2 行为）
- 空答案 → 立即 incorrect（不调 LLM）
- 返回 ScoreResult，含 evidence + suggested_remediation，可被 ErrorDiagnoser 二次利用
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from shared.errors import TutorError
from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.schemas import Concept

logger = get_logger("tutoring_mcp.llm_scorer")


Correctness = Literal["correct", "partial", "incorrect"]


@dataclass
class ScoreResult:
    correctness: Correctness
    raw_score: float  # 0..1
    evidence: str
    suggested_remediation: str = ""


_SYSTEM = (
    "你是教学判分助理。比对学生答案与概念定义，判断是否正确。"
    "只输出 JSON，不要解释，不评判学生人格。"
)


def _build_prompt(concept: Concept, answer: str) -> str:
    name = concept.names[0]
    return f"""判断学生答案是否抓住了概念定义的核心。只输出 JSON：

概念: {name}
官方定义: {concept.definition}
通俗解释: {concept.informal_description or "(无)"}

学生答案: {answer}

输出格式:
{{
  "correctness": "correct" | "partial" | "incorrect",
  "raw_score": 0.0~1.0,
  "evidence": "为什么这么判（一句话）",
  "suggested_remediation": "若 partial/incorrect，给学生的下一步建议（一句话）"
}}

判断标准:
- correct (>=0.8): 触达核心要点
- partial (0.4-0.8): 部分要点对，缺关键
- incorrect (<0.4): 完全偏题或空白
"""


def _ngrams(text: str, n: int = 2) -> set[str]:
    text = text.strip()
    return {text[i : i + n] for i in range(len(text) - n + 1)} if len(text) >= n else {text}


def _heuristic_score(concept: Concept, answer: str) -> ScoreResult:
    """spine v2 的 2-gram 启发式作为最终 fallback。"""
    a = answer.strip()
    if not a:
        return ScoreResult(
            correctness="incorrect",
            raw_score=0.0,
            evidence="空答案",
            suggested_remediation="请尝试用一句话回应",
        )
    name_grams = _ngrams(concept.names[0])
    overlap = name_grams & _ngrams(a)
    if overlap:
        return ScoreResult(
            correctness="correct",
            raw_score=0.7,
            evidence=f"启发式：答案与概念名 '{concept.names[0]}' 有 {len(overlap)} 个 2-gram 重叠",
            suggested_remediation="",
        )
    return ScoreResult(
        correctness="partial",
        raw_score=0.4,
        evidence="启发式：答案不空但未命中概念名",
        suggested_remediation=f"想想 {concept.names[0]} 的核心特征",
    )


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.5


def _parse_llm_json(text: str) -> dict | None:
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
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            out = json.loads(text[start : end + 1])
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None
    return None


class LLMScorer:
    """主入口: scorer.score(concept, answer) → ScoreResult。"""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def score(self, *, concept: Concept, student_answer: str) -> ScoreResult:
        # 空答案：不浪费 LLM
        if not (student_answer or "").strip():
            return ScoreResult(
                correctness="incorrect",
                raw_score=0.0,
                evidence="学生未作答",
                suggested_remediation="请尝试回应，哪怕半成品也可以",
            )

        # 调 LLM
        prompt = _build_prompt(concept, student_answer)
        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=512,
            )
        except TutorError as exc:
            if exc.code == "PLUGIN_NOT_AVAILABLE":
                logger.info("scorer.fallback_heuristic", reason="llm_unavailable")
                return _heuristic_score(concept, student_answer)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("scorer.llm_exception", error=str(exc))
            return _heuristic_score(concept, student_answer)

        data = _parse_llm_json(resp.content)
        if data is None:
            logger.info("scorer.fallback_heuristic", reason="bad_json")
            r = _heuristic_score(concept, student_answer)
            return ScoreResult(
                correctness=r.correctness,
                raw_score=r.raw_score,
                evidence=f"(LLM 返回无法解析，回退启发式) {r.evidence}",
                suggested_remediation=r.suggested_remediation,
            )

        corr = data.get("correctness")
        if corr not in ("correct", "partial", "incorrect"):
            logger.info("scorer.fallback_heuristic", reason="bad_correctness")
            return _heuristic_score(concept, student_answer)

        return ScoreResult(
            correctness=corr,  # type: ignore[arg-type]
            raw_score=_clamp(data.get("raw_score", 0.5)),
            evidence=str(data.get("evidence", "")) or "(LLM 未给出 evidence)",
            suggested_remediation=str(data.get("suggested_remediation", "")),
        )
