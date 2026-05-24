"""冷启动摸底 (cold-start assessment) 核心逻辑测试。

规格来源: ai-tutor-system-design/specs/adopted-fixes.md 修正 2

要点:
- 选 10 道跨难度分布的摸底题（basic<0.3 ×3 / current 0.3-0.6 ×4 / abstract>0.6 ×3）
- 判分 → 每概念一个 BKT 先验 mastery
- 画像初值: abstract_tolerance / transfer_ability / self_assessment_accuracy
- recommended_starting_level
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.schemas import (
    ColdStartAnswer,
    ColdStartProbe,
    ColdStartResult,
    Concept,
    ConceptClassification,
    ConceptDifficulty,
)
from servers.tutoring_mcp import cold_start
from servers.tutoring_mcp.llm_scorer import ScoreResult


def _concept(idx: str, abstract: float, name: str | None = None) -> Concept:
    return Concept(
        id=f"sub:{idx}:c{idx.replace('.', '_')}",
        names=[name or f"概念{idx}"],
        category="definition",
        definition=f"概念{idx}的定义",
        informal_description=f"概念{idx}的解释",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=abstract, domain="d"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0,
            formula_density=0.1, coupling=0.1,
            cognitive_load_estimate=0.3, typical_learning_time_min=15,
        ),
        confidence=0.85,
    )


def _corpus() -> list[Concept]:
    """构造一组横跨难度的概念：5 basic + 6 current + 5 abstract。"""
    cs = []
    for i in range(5):
        cs.append(_concept(f"1.{i}", abstract=0.1 + i * 0.03))
    for i in range(6):
        cs.append(_concept(f"2.{i}", abstract=0.35 + i * 0.03))
    for i in range(5):
        cs.append(_concept(f"3.{i}", abstract=0.7 + i * 0.03))
    return cs


# --------------------------------------------------------------------------- #
# band 分类
# --------------------------------------------------------------------------- #


def test_band_of():
    assert cold_start.band_of(0.1) == "basic"
    assert cold_start.band_of(0.29) == "basic"
    assert cold_start.band_of(0.3) == "current"
    assert cold_start.band_of(0.6) == "current"
    assert cold_start.band_of(0.61) == "abstract"
    assert cold_start.band_of(0.9) == "abstract"


# --------------------------------------------------------------------------- #
# 选题
# --------------------------------------------------------------------------- #


def test_select_probe_concepts_distribution():
    sel = cold_start.select_probe_concepts(_corpus(), n=10)
    assert len(sel) == 10
    bands = [cold_start.band_of(c.classification.abstract_level) for c in sel]
    assert bands.count("basic") == 3
    assert bands.count("current") == 4
    assert bands.count("abstract") == 3


def test_select_probe_concepts_dedup_and_capped():
    sel = cold_start.select_probe_concepts(_corpus(), n=10)
    ids = [c.id for c in sel]
    assert len(ids) == len(set(ids))  # 无重复


def test_select_handles_fewer_concepts_than_n():
    small = [_concept("1.0", 0.1), _concept("2.0", 0.4), _concept("3.0", 0.8)]
    sel = cold_start.select_probe_concepts(small, n=10)
    assert len(sel) == 3  # 不超过可用数量
    assert {c.id for c in sel} == {c.id for c in small}


def test_select_fills_to_n_when_band_short():
    # 没有 abstract 概念时，仍尽量凑够 n
    cs = [_concept(f"1.{i}", 0.1 + i * 0.02) for i in range(8)] + [
        _concept(f"2.{i}", 0.4 + i * 0.02) for i in range(6)
    ]
    sel = cold_start.select_probe_concepts(cs, n=10)
    assert len(sel) == 10


# --------------------------------------------------------------------------- #
# 出题
# --------------------------------------------------------------------------- #


def test_build_probe_shape():
    c = _concept("2.1", 0.45, name="偏导数")
    probe = cold_start.build_probe(c)
    assert isinstance(probe, ColdStartProbe)
    assert probe.concept_id == c.id
    assert probe.concept_name == "偏导数"
    assert probe.band == "current"
    assert "偏导数" in probe.question


# --------------------------------------------------------------------------- #
# 先验映射
# --------------------------------------------------------------------------- #


def test_mastery_prior_ordering():
    p = cold_start.mastery_prior
    # 正确 > 部分 > 错误
    assert p("correct", "sure") > p("partial", "sure") > p("incorrect", "sure")
    # 同 correctness 下，自评越确定先验越高
    assert p("correct", "sure") > p("correct", "unsure") > p("correct", "dont_know")
    # correct 任意自评都达到"已掌握"阈值
    assert p("correct", "dont_know") >= cold_start.MASTERY_SKIP_THRESHOLD
    # incorrect 远低于阈值
    assert p("incorrect", "sure") < 0.3
    # 范围合法
    for corr in ("correct", "partial", "incorrect"):
        for sr in ("sure", "unsure", "dont_know"):
            assert 0.0 <= p(corr, sr) <= 1.0


# --------------------------------------------------------------------------- #
# 判分聚合
# --------------------------------------------------------------------------- #


@dataclass
class _FakeScorer:
    """按 concept_id 后缀决定 correctness，便于确定性测试。"""

    mapping: dict[str, ScoreResult]

    def score(self, *, concept, student_answer):
        return self.mapping.get(
            concept.id,
            ScoreResult(correctness="incorrect", raw_score=0.0, evidence="default"),
        )


def _sr(correctness, raw):
    return ScoreResult(correctness=correctness, raw_score=raw, evidence="t")


def test_grade_assessment_seeds_and_profiles():
    concepts = [
        _concept("1.0", 0.1),   # basic
        _concept("1.1", 0.2),   # basic
        _concept("2.0", 0.4),   # current
        _concept("3.0", 0.8),   # abstract
        _concept("3.1", 0.85),  # abstract
    ]
    by_id = {c.id: c for c in concepts}
    probes = [cold_start.build_probe(c) for c in concepts]
    answers = [
        ColdStartAnswer(concept_id=concepts[0].id, answer="对", self_report="sure"),
        ColdStartAnswer(concept_id=concepts[1].id, answer="对", self_report="sure"),
        ColdStartAnswer(concept_id=concepts[2].id, answer="一般", self_report="unsure"),
        ColdStartAnswer(concept_id=concepts[3].id, answer="不会", self_report="dont_know"),
        ColdStartAnswer(concept_id=concepts[4].id, answer="会", self_report="sure"),
    ]
    scorer = _FakeScorer({
        concepts[0].id: _sr("correct", 0.9),
        concepts[1].id: _sr("correct", 0.95),
        concepts[2].id: _sr("partial", 0.5),
        concepts[3].id: _sr("incorrect", 0.1),
        concepts[4].id: _sr("correct", 0.9),
    })

    result = cold_start.grade_assessment(
        probes=probes, answers=answers, concepts_by_id=by_id, scorer=scorer
    )
    assert isinstance(result, ColdStartResult)
    assert result.probes_graded == 5
    # 答对的进入 seeded_mastered，答错/部分不进
    assert concepts[0].id in result.seeded_mastered
    assert concepts[4].id in result.seeded_mastered
    assert concepts[2].id not in result.seeded_mastered
    assert concepts[3].id not in result.seeded_mastered
    # 每个概念都有先验
    assert set(result.mastery_priors) == set(by_id)
    # abstract 带：一对一错 → tolerance 中等偏低
    assert 0.0 <= result.abstract_tolerance_initial <= 1.0
    assert result.recommended_starting_level in ("beginner", "intermediate", "advanced")


def test_grade_assessment_missing_answer_treated_incorrect():
    c = _concept("1.0", 0.1)
    by_id = {c.id: c}
    probes = [cold_start.build_probe(c)]
    scorer = _FakeScorer({})  # 不会被调用（无答案）
    result = cold_start.grade_assessment(
        probes=probes, answers=[], concepts_by_id=by_id, scorer=scorer
    )
    assert result.probes_graded == 1
    assert c.id not in result.seeded_mastered
    assert result.mastery_priors[c.id] < cold_start.MASTERY_SKIP_THRESHOLD


def test_recommended_level_thresholds():
    # 全对 → advanced
    concepts = [_concept(f"1.{i}", 0.1 + i * 0.1) for i in range(4)]
    by_id = {c.id: c for c in concepts}
    probes = [cold_start.build_probe(c) for c in concepts]
    answers = [ColdStartAnswer(concept_id=c.id, answer="x", self_report="sure") for c in concepts]
    scorer = _FakeScorer({c.id: _sr("correct", 0.95) for c in concepts})
    res = cold_start.grade_assessment(
        probes=probes, answers=answers, concepts_by_id=by_id, scorer=scorer
    )
    assert res.recommended_starting_level == "advanced"

    # 全错 → beginner
    scorer2 = _FakeScorer({c.id: _sr("incorrect", 0.05) for c in concepts})
    res2 = cold_start.grade_assessment(
        probes=probes, answers=answers, concepts_by_id=by_id, scorer=scorer2
    )
    assert res2.recommended_starting_level == "beginner"
