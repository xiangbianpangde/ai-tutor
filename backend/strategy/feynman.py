"""backend.strategy.feynman —— 费曼讲解评分（M-010，对应 v2 #10 拆分 / #12 费曼学习法）。

费曼学习法：让学生用**自己的话、简单地**讲清一个概念，从讲解里暴露理解缺口。本模块给
学生讲解打分——覆盖了概念的哪些关键点、有没有缺口、是不是在背定义而非自述。

务实落地（对齐 M-008 验证器哲学）：LLM 法官可注入走主路径；回退启发式**诚实不过度授信**
（关键点覆盖率 + 自述度），缺口如实列出。FeynmanScore 是 frozen 值对象（FDR-M-010-001）。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..rag.retriever import tokenize

_PASS_COVERAGE = 0.6
_HEURISTIC_CONF_CAP = 0.6
# 自述度：讲解与定义逐字重叠过高 = 在背书，费曼要自己的话
_PARROT_OVERLAP = 0.85


@dataclass(frozen=True)
class FeynmanScore:
    """费曼讲解评分（不可变值对象）。"""

    score: float  # [0,1] 综合分
    passed: bool
    coverage: float  # 关键点覆盖率
    gaps: tuple[str, ...] = field(default_factory=tuple)  # 未覆盖的关键点
    is_parroting: bool = False  # 是否在背定义
    method: str = "heuristic"

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 4),
            "passed": self.passed,
            "coverage": round(self.coverage, 4),
            "gaps": list(self.gaps),
            "is_parroting": self.is_parroting,
            "method": self.method,
        }


LLMJudge = Callable[[str, str, Sequence[str]], dict[str, Any]]


def extract_key_terms(definition: str, *, max_terms: int = 12) -> list[str]:
    """从概念定义抽关键点（含义性 token，去停用词，按出现序去重）。"""
    terms = [t for t in tokenize(definition) if len(t) > 1]
    return list(dict.fromkeys(terms))[:max_terms]


class FeynmanScorer:
    """评估学生对某概念的费曼式讲解。"""

    def __init__(self, *, llm_judge: LLMJudge | None = None) -> None:
        self._judge = llm_judge

    def score(
        self, *, explanation: str, concept_name: str, definition: str,
        key_terms: Sequence[str] | None = None,
    ) -> FeynmanScore:
        if not explanation or not explanation.strip():
            return FeynmanScore(score=0.0, passed=False, coverage=0.0,
                                gaps=tuple(key_terms or extract_key_terms(definition)),
                                method="heuristic")
        if self._judge is not None:
            try:
                return self._score_llm(explanation, concept_name, definition, key_terms)
            except Exception:
                pass
        return self._score_heuristic(explanation, definition, key_terms)

    def _score_llm(
        self, explanation: str, concept_name: str, definition: str,
        key_terms: Sequence[str] | None,
    ) -> FeynmanScore:
        raw = self._judge(explanation, concept_name, list(key_terms or []))  # type: ignore[misc]
        cov = float(raw.get("coverage", 0.0))
        return FeynmanScore(
            score=float(raw.get("score", cov)),
            passed=bool(raw.get("passed", cov >= _PASS_COVERAGE)),
            coverage=cov,
            gaps=tuple(raw.get("gaps", []) or []),
            is_parroting=bool(raw.get("is_parroting", False)),
            method="llm",
        )

    def _score_heuristic(
        self, explanation: str, definition: str, key_terms: Sequence[str] | None,
    ) -> FeynmanScore:
        terms = list(key_terms) if key_terms else extract_key_terms(definition)
        if not terms:
            return FeynmanScore(score=0.0, passed=False, coverage=0.0, method="heuristic")
        expl_tokens = set(tokenize(explanation))
        covered = [t for t in terms if t in expl_tokens]
        gaps = [t for t in terms if t not in expl_tokens]
        coverage = len(covered) / len(terms)

        # 自述度：讲解 token 有多大比例直接落在定义里（过高 = 背书）
        def_tokens = set(tokenize(definition))
        e_tokens = [t for t in tokenize(explanation) if len(t) > 1]
        overlap = (sum(1 for t in e_tokens if t in def_tokens) / len(e_tokens)) if e_tokens else 0.0
        is_parroting = overlap >= _PARROT_OVERLAP and len(e_tokens) > 3

        # 背书打折；启发式分封顶 0.6（不冒充 LLM 级判定），passed 另由覆盖率独立判定
        score = min(coverage * (0.7 if is_parroting else 1.0), _HEURISTIC_CONF_CAP)
        passed = coverage >= _PASS_COVERAGE and not is_parroting
        return FeynmanScore(
            score=round(score, 4), passed=passed, coverage=round(coverage, 4),
            gaps=tuple(gaps[:12]), is_parroting=is_parroting, method="heuristic",
        )
