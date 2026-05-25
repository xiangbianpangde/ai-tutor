"""逐层数据层 get_layer_*_state 测试。

全部只读、不抛错；空库返回合理空态，有数据时拼出该层视图。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from servers.dashboard.layer_state import (
    LAYER_FUNCS,
    get_layer_l1_state,
    get_layer_l2_state,
    get_layer_l3_state,
    get_layer_l4_state,
    get_layer_l5_state,
    get_layer_l6_state,
    get_layer_l7_state,
    get_layer_pgfga_state,
)
from shared.models import (
    BKTParamRow,
    ConceptRow,
    ForgettingCurveRow,
    KnowledgeGraphRow,
    RelationRow,
    ReviewHistoryRow,
    Subject,
    User,
)
from shared.schemas import FlowLevel
from shared.storage import RelationalStore


def _concept_json(cid: str, name: str, load: float = 0.4) -> dict:
    return {
        "id": cid, "names": [name], "category": "definition",
        "definition": f"{name}的定义", "informal_description": "",
        "classification": {"bloom_level": "understand", "abstract_level": 0.5, "domain": "math"},
        "difficulty": {"prereq_count": 0, "prereq_max_depth": 0, "formula_density": 0.3,
                       "coupling": 0.2, "cognitive_load_estimate": load, "typical_learning_time_min": 20},
        "confidence": 0.8,
    }


def _concept_row(cid: str, name: str, load: float = 0.4) -> ConceptRow:
    fj = _concept_json(cid, name, load)
    return ConceptRow(
        id=cid, kg_id="kg1", base_id=cid, name_primary=name, names_json=[name],
        category="definition", definition=fj["definition"], informal_description="",
        abstract_level=0.5, bloom_level="understand", domain="math",
        cognitive_load_estimate=load, typical_learning_time_min=20,
        prereq_count=0, prereq_max_depth=0, formula_density=0.3, coupling=0.2,
        confidence=0.8, full_json=fj,
    )


@pytest.fixture
def seeded(tmp_db: RelationalStore) -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="gaoshu", user_id="yhn", display_name="高数", kg_id="kg1"))
        s.add(KnowledgeGraphRow(kg_id="kg1", subject_id="gaoshu", corpus_id="c1",
                                version="concept-v1", node_count=3, edge_count=1,
                                quality_json={"overall": "pass_with_warnings"}, manifest_json={}))
        s.add(_concept_row("gs:1:a", "概念A", load=0.2))   # easy
        s.add(_concept_row("gs:2:b", "概念B", load=0.5))   # medium
        s.add(_concept_row("gs:3:c", "概念C", load=0.8))   # hard
        s.add(RelationRow(kg_id="kg1", from_id="gs:2:b", to_id="gs:1:a",
                          type="prerequisite_strong", weight=0.6, explanation="x", confidence=0.5))
        s.add(BKTParamRow(user_id="yhn", concept_id="gs:1:a", p_mastery=0.9, n_observations=4))
        s.add(BKTParamRow(user_id="yhn", concept_id="gs:3:c", p_mastery=0.1, n_observations=2))
        # 复习历史 + 遗忘曲线
        s.add(ReviewHistoryRow(user_id="yhn", concept_id="gs:1:a", subject_id="gaoshu",
                               review_date=datetime.utcnow().date(), days_since_last=1,
                               accuracy=1.0, review_mode="quick_quiz", error_types=[]))
        s.add(ReviewHistoryRow(user_id="yhn", concept_id="gs:3:c", subject_id="gaoshu",
                               review_date=datetime.utcnow().date(), days_since_last=2,
                               accuracy=0.0, review_mode="teach_back",
                               error_types=["concept_confusion"]))
        s.add(ForgettingCurveRow(user_id="yhn", concept_id="gs:1:a", subject_id="gaoshu",
                                 lambda_param=0.3, r_squared=0.9, n_data_points=4,
                                 next_review_at=datetime.utcnow() - timedelta(days=1),  # 已到期
                                 review_streak=2))
        s.commit()
    return tmp_db


def _save_session(db, overrides: dict) -> None:
    from servers.tutoring_mcp.session import SessionStore
    sessions = SessionStore(db)
    ctx = sessions.create(user_id="yhn", subject_id="gaoshu")
    for k, v in overrides.items():
        setattr(ctx, k, v)
    sessions.save(ctx)


# ----------------------------- L1 ----------------------------- #

def test_l1_table_counts(seeded):
    st = get_layer_l1_state(seeded)
    assert st["tables"]["concepts"] == 3
    assert st["tables"]["relations"] == 1
    assert st["tables"]["bkt_params"] == 2
    assert st["total_rows"] >= 6
    assert st["plugin_health"]["persisted"] is False


def test_l1_empty_db(tmp_db):
    st = get_layer_l1_state(tmp_db)
    assert st["total_rows"] == 0


# ----------------------------- L2 ----------------------------- #

def test_l2_sessions(seeded):
    _save_session(seeded, {"current_concept_id": "gs:1:a", "status": "active"})
    st = get_layer_l2_state(seeded)
    assert st["active_count"] == 1
    assert len(st["sessions"]) == 1
    assert st["sessions"][0]["current_concept_id"] == "gs:1:a"


def test_l2_empty(tmp_db):
    assert get_layer_l2_state(tmp_db)["active_count"] == 0


# ----------------------------- L3 ----------------------------- #

def test_l3_curves_and_due(seeded):
    st = get_layer_l3_state(seeded)
    assert st["tracked_concepts"] == 1
    assert st["due_count"] == 1  # next_review_at 在过去 → 到期
    assert st["total_reviews"] == 2
    assert st["review_mode_distribution"] == {"quick_quiz": 1, "teach_back": 1}


# ----------------------------- L4 ----------------------------- #

def test_l4_topology_and_distribution(seeded):
    _save_session(seeded, {"current_concept_id": "gs:1:a", "status": "active", "teaching_plan_id": "kg1"})
    st = get_layer_l4_state(seeded)
    assert st["active_kg_id"] == "kg1"
    assert st["concept_count"] == 3
    assert st["difficulty_distribution"] == {"easy": 1, "medium": 1, "hard": 1}
    assert st["relation_types"] == {"prerequisite_strong": 1}
    assert "graph TD" in st["mermaid"]
    assert len(st["graphs"]) == 1


def test_l4_no_session_falls_back_to_latest_kg(seeded):
    st = get_layer_l4_state(seeded)
    assert st["active_kg_id"] == "kg1"  # 无会话 → 取最新 KG


# ----------------------------- L5 ----------------------------- #

def test_l5_bkt_and_errors(seeded):
    _save_session(seeded, {"current_concept_id": "gs:1:a", "status": "active"})
    st = get_layer_l5_state(seeded)
    assert st["bkt_count"] == 2
    assert st["bkt"][0]["p_mastery"] == 0.9  # 按掌握度降序
    assert st["error_types"] == {"concept_confusion": 1}


# ----------------------------- L6 ----------------------------- #

def test_l6_strategy_and_flow(seeded):
    _save_session(seeded, {
        "current_concept_id": "gs:1:a", "status": "active",
        "current_strategy": "jiangjie", "current_strategy_state": "REDUCE",
        "recent_history": [
            {"flow_level": int(FlowLevel.SILENT), "concept_id": "gs:1:a"},
            {"flow_level": int(FlowLevel.FLUENT), "concept_id": "gs:1:a"},
        ],
    })
    st = get_layer_l6_state(seeded)
    assert st["strategy"] == "jiangjie"
    assert st["strategy_state"] == "REDUCE"
    assert st["flow_series"] == [int(FlowLevel.SILENT), int(FlowLevel.FLUENT)]
    assert st["gain_loop"]["persisted"] is False


def test_l6_idle(tmp_db):
    assert get_layer_l6_state(tmp_db)["status"] == "idle"


# ----------------------------- L7 ----------------------------- #

def test_l7_dialogue(seeded):
    _save_session(seeded, {
        "current_concept_id": "gs:1:a", "status": "active",
        "recent_history": [
            {"answer": "我的回答", "correctness": "correct", "concept_id": "gs:1:a"},
        ],
    })
    st = get_layer_l7_state(seeded)
    assert st["turn_count"] == 1
    assert st["dialogue"][0]["answer"] == "我的回答"


# ----------------------------- pgfga ----------------------------- #

def test_pgfga_flow_trend_rising(seeded):
    _save_session(seeded, {
        "current_concept_id": "gs:1:a", "status": "active",
        "recent_history": [
            {"flow_level": 0, "concept_id": "gs:1:a"},
            {"flow_level": 3, "concept_id": "gs:1:a"},
        ],
    })
    st = get_layer_pgfga_state(seeded)
    assert st["flow_trend"] == "rising"
    assert st["current_flow_level"] == 3
    assert st["firewall"]["persisted"] is False


def test_pgfga_idle(tmp_db):
    assert get_layer_pgfga_state(tmp_db)["flow_trend"] == "unknown"


# ----------------------------- 注册表 ----------------------------- #

def test_layer_funcs_registry_complete(seeded):
    assert set(LAYER_FUNCS) == {"L1", "L2", "L3", "L4", "L5", "L6", "L7", "pgfga"}
    for fn in LAYER_FUNCS.values():
        out = fn(seeded)
        assert isinstance(out, dict)  # 每个都返回 dict，不抛错
