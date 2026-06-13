"""状态面板只读数据层测试。

get_dashboard_state(db) 从同一 SQLite 拼出面板所需状态：当前概念/心流/策略 +
掌握度分桶 + 最近交互 + 48h Phase 进度。只读，不改任何生产数据。
"""
from __future__ import annotations

import pytest

from servers.dashboard.state import get_dashboard_state
from shared.models import (
    BKTParamRow,
    ConceptRow,
    KnowledgeGraphRow,
    Subject,
    User,
)
from shared.schemas import FlowLevel
from shared.storage import RelationalStore


def _concept_json(cid: str, name: str, time_min: int = 20) -> dict:
    return {
        "id": cid, "names": [name], "category": "definition",
        "definition": f"{name}的定义", "informal_description": "",
        "classification": {"bloom_level": "understand", "abstract_level": 0.5, "domain": "math"},
        "difficulty": {"prereq_count": 0, "prereq_max_depth": 0, "formula_density": 0.3,
                       "coupling": 0.2, "cognitive_load_estimate": 0.4, "typical_learning_time_min": time_min},
        "confidence": 0.8,
    }


def _concept_row(cid: str, name: str) -> ConceptRow:
    fj = _concept_json(cid, name)
    return ConceptRow(
        id=cid, kg_id="kg1", base_id=cid, name_primary=name, names_json=[name],
        category="definition", definition=fj["definition"], informal_description="",
        abstract_level=0.5, bloom_level="understand", domain="math",
        cognitive_load_estimate=0.4, typical_learning_time_min=20,
        prereq_count=0, prereq_max_depth=0, formula_density=0.3, coupling=0.2,
        confidence=0.8, full_json=fj,
    )


@pytest.fixture
def seeded(tmp_db: RelationalStore) -> RelationalStore:
    concepts = [
        ("gs:1:ch1", "第一章"), ("gs:1.1:a", "概念A"), ("gs:1.2:b", "概念B"),
        ("gs:2:ch2", "第二章"), ("gs:2.1:c", "概念C"),
    ]
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="gaoshu", user_id="yhn", display_name="高数", kg_id="kg1"))
        s.add(KnowledgeGraphRow(kg_id="kg1", subject_id="gaoshu", corpus_id="c1",
                                version="concept-v1", node_count=5, edge_count=4, manifest_json={}))
        for cid, name in concepts:
            s.add(_concept_row(cid, name))
        # BKT：A 已掌握(0.9)、B 学习中(0.55)、C 弱(0.1)
        s.add(BKTParamRow(user_id="yhn", concept_id="gs:1.1:a", p_mastery=0.9))
        s.add(BKTParamRow(user_id="yhn", concept_id="gs:1.2:b", p_mastery=0.55))
        s.add(BKTParamRow(user_id="yhn", concept_id="gs:2.1:c", p_mastery=0.1))
        s.commit()
    return tmp_db


def _save_session(db, ctx_overrides: dict) -> None:
    from servers.tutoring_mcp.session import SessionStore
    sessions = SessionStore(db)
    ctx = sessions.create(user_id="yhn", subject_id="gaoshu")
    for k, v in ctx_overrides.items():
        setattr(ctx, k, v)
    sessions.save(ctx)


def test_idle_when_no_session(seeded):
    state = get_dashboard_state(seeded)
    assert state["status"] == "idle"


def test_active_session_core_fields(seeded):
    _save_session(seeded, {
        "current_concept_id": "gs:1.2:b", "current_strategy": "jiangjie",
        "current_strategy_state": "REDUCE", "status": "active",
        "teaching_plan_id": "kg1",
        "strategy_internal": {"sub_step_count": 5, "_atom_index": 3},
        "recent_history": [
            {"correctness": "correct", "flow_level": int(FlowLevel.FLUENT), "concept_id": "gs:1.2:b"},
        ],
    })
    st = get_dashboard_state(seeded)
    assert st["status"] != "idle"
    assert st["current_concept_id"] == "gs:1.2:b"
    assert st["current_concept_name"] == "概念B"
    assert st["strategy"] == "jiangjie"
    assert st["strategy_state"] == "REDUCE"
    assert st["flow_level"] == int(FlowLevel.FLUENT)
    assert st["current_mastery"] == pytest.approx(0.55)
    # strategy_internal 透传给步骤条
    assert st["strategy_internal"]["_atom_index"] == 3


def test_mastery_buckets(seeded):
    _save_session(seeded, {"current_concept_id": "gs:1.1:a", "status": "active", "teaching_plan_id": "kg1"})
    st = get_dashboard_state(seeded)
    # A 0.9 mastered, B 0.55 learning, C 0.1 weak（其余概念无 BKT 记录→默认低→weak）
    assert st["mastery"]["mastered"] == 1
    assert st["mastery"]["learning"] == 1
    assert st["mastery"]["weak"] >= 1


def test_recent_history_capped(seeded):
    hist = [{"correctness": "correct", "flow_level": 2, "concept_id": "gs:1.1:a"} for _ in range(15)]
    _save_session(seeded, {"current_concept_id": "gs:1.1:a", "status": "active",
                           "teaching_plan_id": "kg1", "recent_history": hist})
    st = get_dashboard_state(seeded)
    assert len(st["recent_history"]) <= 10


def test_plan_progress_present(seeded):
    _save_session(seeded, {"current_concept_id": "gs:1.2:b", "status": "active", "teaching_plan_id": "kg1"})
    st = get_dashboard_state(seeded)
    prog = st["plan_progress"]
    assert prog["concepts_total"] == 5
    assert prog["concepts_mastered"] == 1   # 只有 A 掌握
    assert len(prog["phases"]) == 2          # 两章 → 两 Phase
    assert prog["current_phase"] in (1, 2)
