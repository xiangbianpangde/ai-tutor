"""时间校准 (P1 #8) 测试。

estimate_time_min：用概念的内在特征（认知负荷/公式密度/抽象度/前置）算学习时长，
替代恒定 30min。calibrate_time：将来有真实答题时长时把公式估计与观测做置信度加权。
"""
from __future__ import annotations

import pytest

from servers.knowledge_mcp.time_estimator import calibrate_time, estimate_time_min
from shared.schemas import Concept, ConceptClassification, ConceptDifficulty


def _c(*, load=0.3, formula=0.2, abstract=0.3, prereq=1, depth=1) -> Concept:
    return Concept(
        id="s:1.1:c",
        names=["概念"],
        category="definition",
        definition="定义",
        classification=ConceptClassification(bloom_level="understand", abstract_level=abstract, domain="d"),
        difficulty=ConceptDifficulty(
            prereq_count=prereq, prereq_max_depth=depth,
            formula_density=formula, coupling=0.2,
            cognitive_load_estimate=load, typical_learning_time_min=30,
        ),
        confidence=0.85,
    )


# --------------------------------------------------------------------------- #
# estimate_time_min
# --------------------------------------------------------------------------- #


def test_in_schema_range():
    for load in (0.0, 0.5, 1.0):
        t = estimate_time_min(_c(load=load, formula=load, abstract=load, prereq=int(load * 12), depth=int(load * 8)))
        assert 1 <= t <= 120
        assert isinstance(t, int)


def test_harder_concept_takes_longer():
    easy = estimate_time_min(_c(load=0.05, formula=0.0, abstract=0.0, prereq=0, depth=0))
    hard = estimate_time_min(_c(load=0.95, formula=1.0, abstract=1.0, prereq=10, depth=8))
    assert hard > easy
    assert easy < 15  # 简单概念明显短
    assert hard > 30  # 难概念明显长


@pytest.mark.parametrize("feature", ["load", "formula", "abstract", "prereq", "depth"])
def test_monotonic_in_each_feature(feature):
    lo = estimate_time_min(_c(**{feature: 0.0 if feature in ("load", "formula", "abstract") else 0}))
    hi_val = 1.0 if feature in ("load", "formula", "abstract") else 10
    hi = estimate_time_min(_c(**{feature: hi_val}))
    assert hi >= lo


def test_not_flat_30():
    """不同概念给出不同估计（不再恒 30）。"""
    times = {
        estimate_time_min(_c(load=0.1, formula=0.1, abstract=0.1)),
        estimate_time_min(_c(load=0.5, formula=0.5, abstract=0.5)),
        estimate_time_min(_c(load=0.9, formula=0.9, abstract=0.9)),
    }
    assert len(times) == 3
    assert 30 not in times or len(times) > 1  # 至少有区分度


# --------------------------------------------------------------------------- #
# calibrate_time
# --------------------------------------------------------------------------- #


def test_calibrate_no_observation_returns_estimate():
    assert calibrate_time(estimated_min=20, observed_minutes=[]) == 20


def test_calibrate_blends_toward_observed():
    """少量观测 → 偏向估计；大量观测 → 偏向实测均值。"""
    few = calibrate_time(estimated_min=20, observed_minutes=[40.0])
    many = calibrate_time(estimated_min=20, observed_minutes=[40.0] * 20)
    assert 20 < few < many <= 41
    assert abs(many - 40) <= 3  # 大样本接近实测


def test_calibrate_clamped_and_int():
    v = calibrate_time(estimated_min=10, observed_minutes=[999.0] * 50)
    assert isinstance(v, int)
    assert 1 <= v <= 120
