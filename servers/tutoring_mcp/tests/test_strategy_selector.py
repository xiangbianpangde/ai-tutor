"""StrategySelector 决策树契约测试。

合同来源: specs/teaching-strategy-formalism.md §策略选择决策树

输入: concept + mastery + LearnerProfile（cognitive / metacognitive 等）
输出: strategy_name ∈ {reduction, feynman, socratic, analogy, pbl, spaced_repetition}

7 条决策规则:
1. cognitive_load > overload_threshold + abstract_level > 0.5 → analogy
2. cognitive_load > overload_threshold + 其他 → reduction (slower)
3. abstract_level > abstract_tolerance * 1.2 → analogy
4. mastery < 0.2 → reduction
5. 0.3 <= mastery < 0.6 且 transfer_ability > 0.5 → socratic
6. 0.4 <= mastery < 0.7 且 self_assessment_accuracy < 0.5 → feynman
7. mastered_count > 0.6 * total → pbl
default: reduction
"""
from __future__ import annotations

from shared.schemas import (
    BehavioralProfile,
    CognitiveProfile,
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    LearnerProfile,
    MetacognitiveProfile,
)


def _concept(abstract_level: float = 0.5) -> Concept:
    return Concept(
        id="d:1.1:x",
        names=["x"],
        category="definition",
        definition="...",
        classification=ConceptClassification(
            bloom_level="understand",
            abstract_level=abstract_level,
            domain="d",
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0,
            formula_density=0.1, coupling=0.1,
            cognitive_load_estimate=0.3, typical_learning_time_min=10,
        ),
        confidence=0.9,
    )


def _profile(
    abstract_tolerance: float = 0.6,
    transfer_ability: float = 0.4,
    self_assessment_accuracy: float = 0.6,
) -> LearnerProfile:
    return LearnerProfile(
        user_id="u",
        cognitive=CognitiveProfile(
            abstract_tolerance=abstract_tolerance,
            transfer_ability=transfer_ability,
        ),
        metacognitive=MetacognitiveProfile(
            self_assessment_accuracy=self_assessment_accuracy,
        ),
        behavioral=BehavioralProfile(),
    )


def test_default_falls_to_reduction() -> None:
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(),
        mastery=0.1,  # 很低
        cognitive_load=0.3,
        profile=_profile(),
        mastered_ratio=0.0,
    )
    assert name == "reduction"


def test_high_abstract_picks_analogy() -> None:
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.9),  # 远超 tolerance(0.6) * 1.2 = 0.72
        mastery=0.3,
        cognitive_load=0.2,
        profile=_profile(abstract_tolerance=0.6),
        mastered_ratio=0.0,
    )
    assert name == "analogy"


def test_overload_high_abstract_analogy() -> None:
    """cognitive_load 过高 + 概念抽象 → analogy。"""
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.7),
        mastery=0.5,
        cognitive_load=0.85,  # overload
        profile=_profile(),
        mastered_ratio=0.0,
    )
    assert name == "analogy"


def test_overload_low_abstract_reduction_slower() -> None:
    """cognitive_load 过高 + 概念不抽象 → reduction（慢速）。"""
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.3),
        mastery=0.5,
        cognitive_load=0.85,
        profile=_profile(),
        mastered_ratio=0.0,
    )
    assert name == "reduction"


def test_mid_mastery_high_transfer_picks_socratic() -> None:
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.4),
        mastery=0.45,  # 0.3-0.6
        cognitive_load=0.3,
        profile=_profile(transfer_ability=0.7),
        mastered_ratio=0.1,
    )
    assert name == "socratic"


def test_mid_mastery_low_self_assessment_picks_feynman() -> None:
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.4),
        mastery=0.55,  # 0.4-0.7
        cognitive_load=0.3,
        profile=_profile(transfer_ability=0.3, self_assessment_accuracy=0.3),
        mastered_ratio=0.2,
    )
    assert name == "feynman"


def test_high_overall_mastered_picks_pbl() -> None:
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.4),
        mastery=0.6,
        cognitive_load=0.3,
        profile=_profile(transfer_ability=0.6),
        mastered_ratio=0.7,  # > 0.6
    )
    assert name == "pbl"


def test_very_low_mastery_picks_reduction() -> None:
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.3),
        mastery=0.05,
        cognitive_load=0.3,
        profile=_profile(),
        mastered_ratio=0.0,
    )
    assert name == "reduction"


# --------------------------------------------------------------------------- #
# 规则 8（新增）：降阶法 (jiangjie)
# 触发：preferred_pace == "thorough" / 心流 SILENT / 中高认知负荷 (0.6, overload]
# --------------------------------------------------------------------------- #


def _thorough_profile() -> LearnerProfile:
    return LearnerProfile(
        user_id="u",
        cognitive=CognitiveProfile(abstract_tolerance=0.6, transfer_ability=0.4),
        metacognitive=MetacognitiveProfile(self_assessment_accuracy=0.6),
        behavioral=BehavioralProfile(preferred_pace="thorough"),
    )


def test_thorough_pace_picks_jiangjie() -> None:
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.3),
        mastery=0.5,
        cognitive_load=0.3,
        profile=_thorough_profile(),
        mastered_ratio=0.0,
    )
    assert name == "jiangjie"


def test_mid_high_load_band_picks_jiangjie() -> None:
    """认知负荷在 (0.6, overload] 区间但概念不抽象 → 降阶法温和拆解。"""
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.3),
        mastery=0.5,
        cognitive_load=0.7,  # > 0.6 但 < 0.75 overload
        profile=_profile(),
        mastered_ratio=0.0,
    )
    assert name == "jiangjie"


def test_silent_flow_picks_jiangjie() -> None:
    from shared.schemas import FlowLevel
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.3),
        mastery=0.5,
        cognitive_load=0.3,
        profile=_profile(),
        mastered_ratio=0.0,
        flow_level=FlowLevel.SILENT,
    )
    assert name == "jiangjie"


def test_overload_still_prefers_analogy_over_jiangjie() -> None:
    """认知负荷过高 + 概念抽象 → 仍走 analogy（overload 规则优先于降阶法）。"""
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(abstract_level=0.7),
        mastery=0.5,
        cognitive_load=0.85,
        profile=_thorough_profile(),
        mastered_ratio=0.0,
    )
    assert name == "analogy"


# ------------------- FIX-G：feynman 可达（#12 回归） ------------------- #


def test_default_profile_mid_mastery_picks_feynman() -> None:
    """默认画像（self_assessment_accuracy=0.6 尚未被证实）+ 中段掌握 → feynman。

    旧门槛 `< 0.5` 在默认画像下数学上不可达——feynman 永远选不中（#12 根因）。
    """
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(),
        mastery=0.5,
        cognitive_load=0.3,
        profile=_profile(),  # 全默认：transfer 0.4 / self_assess 0.6
        mastered_ratio=0.0,
    )
    assert name == "feynman"


def test_proven_accurate_self_assessor_skips_feynman() -> None:
    """自评准确度已被证实（>0.6）→ 不再强制费曼输出式检验。"""
    from servers.tutoring_mcp.strategy_selector import select_strategy

    name = select_strategy(
        concept=_concept(),
        mastery=0.5,
        cognitive_load=0.3,
        profile=_profile(self_assessment_accuracy=0.75),
        mastered_ratio=0.0,
    )
    assert name != "feynman"
