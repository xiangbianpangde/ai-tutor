"""冷启动摸底 (cold-start assessment) — 核心逻辑（纯函数，可单测）。

规格来源: ai-tutor-system-design/specs/adopted-fixes.md 修正 2

为什么需要：新用户 + 新科目时，BKT 先验默认 p_mastery=0.05，等于假设学生
什么都不会。结果是已掌握的 ~30% 内容被从头重讲，浪费 48h 预算里的大块时间。

做法：
1. 从 KG 选 10 个代表性概念，跨难度分布（basic<0.3 ×3 / current 0.3-0.6 ×4
   / abstract>0.6 ×3），探测先验掌握。
2. 每题判分（复用 LLMScorer，启发式 fallback）+ 学生自评（确定/不确定/不知道）。
3. correctness × self_report → BKT 先验 mastery。答对的概念种到 ≥ 阈值，
   引擎据此跳过（见 engine._is_mastered）。
4. 各 band 的表现 → LearnerProfile 初值（abstract_tolerance / transfer_ability /
   self_assessment_accuracy）+ recommended_starting_level。

本模块只做计算；落库（BKT 种子 + profile 初值）在 server.py 的 tool 里完成。
"""
from __future__ import annotations

from typing import Protocol

from shared.schemas import (
    ColdStartAnswer,
    ColdStartBand,
    ColdStartProbe,
    ColdStartResult,
    Concept,
    SelfReport,
    StartingLevel,
)

# 掌握度 ≥ 此阈值视为"已掌握"，引擎会跳过（与 engine.MASTERY_SKIP_THRESHOLD 一致）
MASTERY_SKIP_THRESHOLD = 0.8

# band 边界
_BASIC_MAX = 0.3      # < 0.3 → basic
_ABSTRACT_MIN = 0.6   # > 0.6 → abstract；之间 → current

# n=10 时的目标分布（基于难度比例 0.3/0.4/0.3）
_BAND_RATIO: dict[ColdStartBand, float] = {"basic": 0.3, "current": 0.4, "abstract": 0.3}
_BAND_ORDER: tuple[ColdStartBand, ...] = ("basic", "current", "abstract")

# self_report → 学生主观置信度
_CONFIDENCE: dict[SelfReport, float] = {"sure": 1.0, "unsure": 0.5, "dont_know": 0.0}

# correctness → 先验基线
_PRIOR_BASE: dict[str, float] = {"correct": 0.88, "partial": 0.5, "incorrect": 0.1}


class _Scorer(Protocol):
    def score(
        self, *, concept: Concept, student_answer: str, question: str | None = None
    ): ...


def band_of(abstract_level: float) -> ColdStartBand:
    if abstract_level < _BASIC_MAX:
        return "basic"
    if abstract_level > _ABSTRACT_MIN:
        return "abstract"
    return "current"


def _chapter_key(concept_id: str) -> tuple[int, ...]:
    """按章节号排序，让选题在章节间分散。"""
    try:
        return tuple(int(x) for x in concept_id.split(":")[1].split("."))
    except (IndexError, ValueError):
        return (10**9,)


def _evenly(items: list[Concept], k: int) -> list[Concept]:
    """从有序 items 里等距取 k 个，避免聚集在同一章。"""
    if k <= 0 or not items:
        return []
    if len(items) <= k:
        return list(items)
    step = len(items) / k
    return [items[int(i * step)] for i in range(k)]


def select_probe_concepts(concepts: list[Concept], n: int = 10) -> list[Concept]:
    """选 n 个代表性概念，尽量满足 band 分布；不足则就近补足并截断到可用数。"""
    if not concepts:
        return []
    ordered = sorted(concepts, key=lambda c: _chapter_key(c.id))
    buckets: dict[ColdStartBand, list[Concept]] = {b: [] for b in _BAND_ORDER}
    for c in ordered:
        buckets[band_of(c.classification.abstract_level)].append(c)

    # 目标配额（四舍五入），保证总和 = n
    targets: dict[ColdStartBand, int] = {}
    allocated = 0
    for b in _BAND_ORDER[:-1]:
        t = round(n * _BAND_RATIO[b])
        targets[b] = t
        allocated += t
    targets[_BAND_ORDER[-1]] = max(0, n - allocated)

    selected: list[Concept] = []
    chosen: set[str] = set()
    for b in _BAND_ORDER:
        for c in _evenly(buckets[b], targets[b]):
            if c.id not in chosen:
                selected.append(c)
                chosen.add(c.id)

    # 补足到 n（某些 band 概念不够时，从剩余概念里按章节序补）
    if len(selected) < min(n, len(ordered)):
        for c in ordered:
            if len(selected) >= n:
                break
            if c.id not in chosen:
                selected.append(c)
                chosen.add(c.id)

    selected.sort(key=lambda c: _chapter_key(c.id))
    return selected[:n]


def build_probe(concept: Concept) -> ColdStartProbe:
    """为一个概念生成一道摸底题（模板即可，难度由 band 体现）。"""
    name = concept.names[0]
    band = band_of(concept.classification.abstract_level)
    question = f"用一句话说明【{name}】是什么、它解决什么问题？（不确定可以直说）"
    return ColdStartProbe(
        concept_id=concept.id,
        concept_name=name,
        abstract_level=concept.classification.abstract_level,
        band=band,
        question=question,
    )


def mastery_prior(correctness: str, self_report: SelfReport) -> float:
    """correctness × 自评 → BKT 先验掌握度。

    correctness 决定基线，自评在基线附近微调（±0.075）。
    答对（任意自评）都达到 MASTERY_SKIP_THRESHOLD，可被引擎跳过。
    """
    base = _PRIOR_BASE.get(correctness, 0.1)
    conf = _CONFIDENCE.get(self_report, 0.5)
    prior = base + (conf - 0.5) * 0.15
    return round(max(0.02, min(0.97, prior)), 3)


def _level_for(mean_score: float) -> StartingLevel:
    if mean_score < 0.4:
        return "beginner"
    if mean_score < 0.75:
        return "intermediate"
    return "advanced"


def grade_assessment(
    *,
    probes: list[ColdStartProbe],
    answers: list[ColdStartAnswer],
    concepts_by_id: dict[str, Concept],
    scorer: _Scorer,
) -> ColdStartResult:
    """判分 + 计算画像初值 + 生成 BKT 先验种子。

    无对应答案的题按 incorrect / dont_know 处理（raw_score=0）。
    """
    answer_by_id = {a.concept_id: a for a in answers}

    mastery_priors: dict[str, float] = {}
    seeded_mastered: list[str] = []

    band_scores: dict[ColdStartBand, list[float]] = {b: [] for b in _BAND_ORDER}
    all_scores: list[float] = []
    calib_gaps: list[float] = []  # |置信度 - 实际表现|

    for probe in probes:
        concept = concepts_by_id.get(probe.concept_id)
        ans = answer_by_id.get(probe.concept_id)

        if ans is None or not ans.answer.strip() or concept is None:
            correctness, raw = "incorrect", 0.0
            self_report: SelfReport = ans.self_report if ans else "dont_know"
        else:
            sr = scorer.score(
                concept=concept, student_answer=ans.answer, question=probe.question
            )
            correctness, raw = sr.correctness, float(sr.raw_score)
            self_report = ans.self_report

        prior = mastery_prior(correctness, self_report)
        mastery_priors[probe.concept_id] = prior
        if prior >= MASTERY_SKIP_THRESHOLD:
            seeded_mastered.append(probe.concept_id)

        band_scores[probe.band].append(raw)
        all_scores.append(raw)
        calib_gaps.append(abs(_CONFIDENCE.get(self_report, 0.5) - raw))

    def _mean(xs: list[float], default: float) -> float:
        return round(sum(xs) / len(xs), 3) if xs else default

    # abstract_tolerance：抽象题的表现
    abstract_tolerance = _mean(band_scores["abstract"], 0.5)
    # transfer_ability：把基础迁移到中高难度的能力 = current+abstract 表现
    transfer = _mean(band_scores["current"] + band_scores["abstract"], 0.4)
    # self_assessment_accuracy：自评与实际的吻合度
    self_acc = round(1.0 - (sum(calib_gaps) / len(calib_gaps)), 3) if calib_gaps else 0.6
    self_acc = max(0.0, min(1.0, self_acc))

    overall = sum(all_scores) / len(all_scores) if all_scores else 0.0

    return ColdStartResult(
        abstract_tolerance_initial=abstract_tolerance,
        transfer_ability_initial=transfer,
        self_assessment_accuracy_initial=self_acc,
        recommended_starting_level=_level_for(overall),
        probes_graded=len(probes),
        mastery_priors=mastery_priors,
        seeded_mastered=seeded_mastered,
    )
