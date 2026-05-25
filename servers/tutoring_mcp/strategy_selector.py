"""策略选择决策树。

合同来源: specs/teaching-strategy-formalism.md §策略选择决策树

决策顺序（前规则命中后即返回）:
1. cognitive_load 高(>overload) + 概念抽象 → analogy
2. cognitive_load 高(>overload) + 概念不抽象 → reduction（slower）
8. 降阶法 (jiangjie)：preferred_pace=="thorough" / 心流 SILENT / 中高负荷 → jiangjie
3. 概念抽象远超 learner tolerance → analogy
4. mastery 很低 → reduction
5. mid-mastery + transfer 高 → socratic
6. mid-mastery + 自评不准 → feynman
7. 全局 mastered_ratio 高 → pbl
default → reduction

规则 8（降阶法）置于 overload 规则之后：当负荷已过 overload 阈值时，
抽象概念仍优先 analogy（具象桥接）。降阶法承接的是「中高负荷但未到
overload」「学生偏好 thorough」「心流跌到 SILENT」这几类需要温和拆解、
重建安全感的情形——见 specs/jiangjie-strategy.md §4.1 与 §5。
"""
from __future__ import annotations

from shared.schemas import Concept, FlowLevel, LearnerProfile

from .pace_controller import OVERLOAD_THRESHOLD as _OVERLOAD_THRESHOLD

_ABSTRACT_AMPLIFIER = 1.2
_JIANGJIE_LOAD_THRESHOLD = 0.6


def select_strategy(
    *,
    concept: Concept,
    mastery: float,
    cognitive_load: float,
    profile: LearnerProfile,
    mastered_ratio: float,
    flow_level: FlowLevel | int | None = None,
) -> str:
    cog = profile.cognitive
    meta = profile.metacognitive

    abstract_level = concept.classification.abstract_level

    # 1+2: 认知负荷过高 → 看抽象度
    if cognitive_load > _OVERLOAD_THRESHOLD:
        if abstract_level > 0.5:
            return "analogy"
        return "reduction"

    # 8: 降阶法 — 学生抗拒/焦虑/初次接触高难度。
    #    preferred_pace=="thorough"，或心流跌到 SILENT，或负荷在 (0.6, overload]。
    if (
        profile.behavioral.preferred_pace == "thorough"
        or (flow_level is not None and int(flow_level) == int(FlowLevel.SILENT))
        or cognitive_load > _JIANGJIE_LOAD_THRESHOLD
    ):
        return "jiangjie"

    # 3: 概念抽象远超学生承受
    if abstract_level > cog.abstract_tolerance * _ABSTRACT_AMPLIFIER:
        return "analogy"

    # 4: 几乎不会 → 从头讲
    if mastery < 0.2:
        return "reduction"

    # 5: 中等 mastery + 学生能自主推理
    if 0.3 <= mastery < 0.6 and cog.transfer_ability > 0.5:
        return "socratic"

    # 6: 中等 mastery + 自评不准 → 让学生讲出来
    if 0.4 <= mastery < 0.7 and meta.self_assessment_accuracy < 0.5:
        return "feynman"

    # 7: 总体掌握度高 → 项目驱动
    if mastered_ratio > 0.6:
        return "pbl"

    return "reduction"
