"""ErrorDiagnoser — 学生答错时分析错误类型 + 建议补救。

合同来源:
  shared/schemas.py 的 ErrorType (10 种枚举)
  ErrorDiagnosis

调用模式:
  diagnoser.diagnose(concept, student_answer, correctness, score_evidence)
  → 返回 ErrorDiagnosis 或 None（correct 时跳过）

容错:
- LLM 不可用 / 返回乱码 / 枚举外类型 → type='blank' + 原 concept_id 兜底
"""
from __future__ import annotations

import json
from typing import Literal

from shared.errors import TutorError
from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.schemas import Concept, ErrorDiagnosis

logger = get_logger("tutoring_mcp.error_diagnoser")


_VALID_ERROR_TYPES = {
    "concept_confusion", "symbol_mistake", "logic_gap",
    "syntax_error", "prereq_gap", "overgeneralization",
    "arithmetic_mistake", "reading_error", "careless", "blank",
}


_SYSTEM = (
    "你是认知诊断专家。学生答错或部分答对时，分析错误类型（不评判学生），"
    "指出根本概念缺口 + 给一句友善的补救建议。只输出 JSON。"
)


def _build_prompt(concept: Concept, answer: str, correctness: str, evidence: str) -> str:
    return f"""学生在学习概念 {concept.names[0]} 时给出了如下回答：

学生答案: {answer}

判分: {correctness}
判分依据: {evidence}

概念定义: {concept.definition}
概念 id: {concept.id}

请输出 JSON：
{{
  "error_type": "concept_confusion|symbol_mistake|logic_gap|syntax_error|prereq_gap|overgeneralization|arithmetic_mistake|reading_error|careless|blank",
  "root_concept_id": "造成错误的根本概念 id（如不清楚就填当前概念 id）",
  "surface_concept_id": "学生当前在学的概念 id",
  "confidence": 0.0~1.0,
  "evidence": ["一两条具体证据"],
  "remediation_suggestion": "一句友善的下一步建议"
}}
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
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            out = json.loads(text[start : end + 1])
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _fallback(concept: Concept, evidence: str) -> ErrorDiagnosis:
    return ErrorDiagnosis(
        error_type="blank",
        root_concept_id=concept.id,
        surface_concept_id=concept.id,
        confidence=0.3,
        evidence=[evidence] if evidence else [],
        remediation_suggestion=f"我们再换一种方式看看 {concept.names[0]}",
    )


class ErrorDiagnoser:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def diagnose(
        self,
        *,
        concept: Concept,
        student_answer: str,
        correctness: Literal["correct", "partial", "incorrect"],
        score_evidence: str = "",
    ) -> ErrorDiagnosis | None:
        if correctness == "correct":
            return None

        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": _build_prompt(concept, student_answer, correctness, score_evidence)},
                ],
                temperature=0.2,
                max_tokens=512,
            )
        except TutorError as exc:
            if exc.code == "PLUGIN_NOT_AVAILABLE":
                return _fallback(concept, score_evidence)
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("diagnoser.llm_exception", error=str(exc))
            return _fallback(concept, score_evidence)

        data = _parse_json(resp.content)
        if data is None:
            return _fallback(concept, score_evidence)

        et = data.get("error_type")
        if et not in _VALID_ERROR_TYPES:
            et = "blank"

        evidence_list = data.get("evidence") or []
        if isinstance(evidence_list, str):
            evidence_list = [evidence_list]
        elif not isinstance(evidence_list, list):
            evidence_list = []

        confidence = data.get("confidence", 0.5)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        return ErrorDiagnosis(
            error_type=et,  # type: ignore[arg-type]
            root_concept_id=str(data.get("root_concept_id") or concept.id),
            surface_concept_id=str(data.get("surface_concept_id") or concept.id),
            confidence=confidence,
            evidence=[str(e) for e in evidence_list if e],
            remediation_suggestion=str(data.get("remediation_suggestion") or "")
            or f"再试一次：{concept.names[0]} 的关键点是？",
        )
