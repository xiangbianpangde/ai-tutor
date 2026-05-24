"""Smoke test: 所有核心 Pydantic 模型可实例化、关键校验生效。

如果这个文件挂，说明 schemas.py 的合同被破坏。
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from shared.schemas import (
    BKTParams,
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    DailyReviewPlan,
    DailyReviewSection,
    FlowLevel,
    FlowSignals,
    InterruptCheckpoint,
    KgEditAction,
    Relation,
    ResponseResult,
    SessionContext,
    SessionMeta,
    SourceRef,
    TeachingAction,
)


# --------------------------------------------------------------------------- #
# Concept.id 格式校验（adopted-fixes 修正 3）
# --------------------------------------------------------------------------- #


def _concept(cid: str) -> Concept:
    return Concept(
        id=cid,
        names=["x"],
        category="definition",
        definition="...",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.5, domain="d"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0,
            prereq_max_depth=0,
            formula_density=0.1,
            coupling=0.1,
            cognitive_load_estimate=0.1,
            typical_learning_time_min=10,
        ),
        confidence=0.9,
    )


@pytest.mark.parametrize(
    "good_id",
    [
        "gaoshu-v8:2.1.1:limit_epsilon_delta",
        "linalg:1.1:vector_space",
        "phy101:3.2.4.1:newton_second_law",
    ],
)
def test_concept_id_accepts_legal(good_id: str) -> None:
    c = _concept(good_id)
    assert c.id == good_id


@pytest.mark.parametrize(
    "bad_id",
    [
        "no-colon-at-all",
        "Subject:1.1:slug",          # subject 含大写
        "subject:1.1:Slug",          # slug 含大写
        "subject:1.1:slug with space",
        "subject:1.1:",              # 空 slug
        ":1.1:slug",                 # 空 subject
        "subject:abc:slug",          # 非数字章节
    ],
)
def test_concept_id_rejects_illegal(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        _concept(bad_id)


# --------------------------------------------------------------------------- #
# Relation 不允许自环
# --------------------------------------------------------------------------- #


def test_relation_rejects_self_loop() -> None:
    with pytest.raises(ValidationError):
        Relation(
            from_id="x:1.1:a",
            to_id="x:1.1:a",
            type="is_a",
            weight=1.0,
            explanation="self loop should fail",
            confidence=0.9,
        )


# --------------------------------------------------------------------------- #
# BKT 参数概率范围
# --------------------------------------------------------------------------- #


def test_bkt_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        BKTParams(concept_id="x:1.1:a", p_init=1.5)


def test_bkt_defaults() -> None:
    p = BKTParams(concept_id="x:1.1:a")
    assert 0.0 <= p.p_mastery <= 1.0
    assert p.n_observations == 0


# --------------------------------------------------------------------------- #
# 拒绝未知字段（extra="forbid"）
# --------------------------------------------------------------------------- #


def test_session_context_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        SessionContext(
            session_id="s1",
            user_id="u1",
            subject_id="x",
            meta=SessionMeta(started_at=datetime.utcnow()),
            unknown_typo=True,  # type: ignore[call-arg]
        )


# --------------------------------------------------------------------------- #
# FlowLevel IntEnum 可比较 + 序列化
# --------------------------------------------------------------------------- #


def test_flow_level_order() -> None:
    assert FlowLevel.SILENT < FlowLevel.SHALLOW < FlowLevel.FLUENT < FlowLevel.DEEP < FlowLevel.IMMERSED


def test_flow_signals_default() -> None:
    s = FlowSignals()
    assert not any(
        [
            s.answer_length_growth,
            s.depth_increasing,
            s.withdrawal_pattern,
        ]
    )


# --------------------------------------------------------------------------- #
# TeachingAction 枚举范围
# --------------------------------------------------------------------------- #


def test_teaching_action_accepts_known_types() -> None:
    a = TeachingAction(type="explain", content="hello")
    assert a.type == "explain"


def test_teaching_action_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        TeachingAction(type="dance", content="x")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# KgEditAction 各 op 可实例化
# --------------------------------------------------------------------------- #


def test_kg_edit_action_variants() -> None:
    KgEditAction(op="approve_all")
    KgEditAction(op="edit_definition", concept_id="x:1.1:a", new_definition="new")
    KgEditAction(op="delete_concept", concept_id="x:1.1:b")
