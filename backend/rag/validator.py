"""backend.rag.validator —— 答案-引用源一致性验证（M-008，NLI 风格）。

设计文档要 DeBERTa-v3-large-mnli；那要下模型（死代理风险）+ CPU 争抢。务实做法：
- **主路径**：可注入 LLM 法官（judge(answer, sources) -> dict），有就用。
- **回退路径**：纯词法支撑度启发式。沿用 FIX-L 教训——**回退永不过度授信**：
  无源 → 不支撑；支撑需答案 token 被源覆盖到实打实的比例，且 confidence 封顶 0.6
  （启发式说"支撑"也只能是低置信"看起来一致"，绝不冒充 LLM 级判定）。

未被任何源覆盖的答案 token 聚成 mismatched_claims（粗粒度，够 API 透明披露）。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .retriever import tokenize
from .types import ValidationResult

# 回退启发式：支撑判定的 token 覆盖率门槛 + 置信封顶
_SUPPORT_COVERAGE = 0.6
_HEURISTIC_CONF_CAP = 0.6

LLMJudge = Callable[[str, Sequence[str]], dict[str, Any]]


class AnswerValidator:
    """验证 answer 是否被 sources 支撑。优先 LLM 法官，否则词法回退。"""

    def __init__(self, *, llm_judge: LLMJudge | None = None) -> None:
        self._judge = llm_judge

    def validate(self, answer: str, sources: Sequence[str]) -> ValidationResult:
        if not answer or not answer.strip():
            return ValidationResult(
                is_supported=False, confidence=0.0,
                mismatched_claims=["答案为空"], method="heuristic",
            )
        # 无源：任何方法都不能判支撑（设计文档明示 sources 空 → is_supported=False）
        if not sources:
            return ValidationResult(
                is_supported=False, confidence=0.0,
                mismatched_claims=["无引用源"], method="heuristic",
            )

        if self._judge is not None:
            try:
                return self._validate_llm(answer, sources)
            except Exception:
                # 法官挂了不抛——降级到回退（透明标 method=heuristic）
                pass
        return self._validate_heuristic(answer, sources)

    def _validate_llm(self, answer: str, sources: Sequence[str]) -> ValidationResult:
        raw = self._judge(answer, list(sources))  # type: ignore[misc]
        return ValidationResult(
            is_supported=bool(raw.get("is_supported", False)),
            confidence=float(raw.get("confidence", 0.0)),
            mismatched_claims=list(raw.get("mismatched_claims", []) or []),
            method="llm",
        )

    def _validate_heuristic(self, answer: str, sources: Sequence[str]) -> ValidationResult:
        ans_terms = [t for t in tokenize(answer) if len(t) > 1]
        if not ans_terms:
            # 答案无实义 token（如纯标点/单字）——不冒判支撑
            return ValidationResult(
                is_supported=False, confidence=0.0,
                mismatched_claims=["答案无可校验内容"], method="heuristic",
            )
        source_terms: set[str] = set()
        for src in sources:
            source_terms.update(tokenize(src))

        covered = [t for t in ans_terms if t in source_terms]
        uncovered = sorted(set(t for t in ans_terms if t not in source_terms))
        coverage = len(covered) / len(ans_terms)

        is_supported = coverage >= _SUPPORT_COVERAGE
        # 置信永不超过封顶；不支撑时给互补的低置信
        confidence = round(min(coverage, _HEURISTIC_CONF_CAP), 4)
        if not is_supported:
            confidence = round(min(coverage, _HEURISTIC_CONF_CAP), 4)

        return ValidationResult(
            is_supported=is_supported,
            confidence=confidence,
            mismatched_claims=uncovered[:20],
            method="heuristic",
        )
