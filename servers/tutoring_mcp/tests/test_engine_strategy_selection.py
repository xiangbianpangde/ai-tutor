"""P1 #4：引擎动态选策略 + 心流调参 + 跨重建保留策略内部状态。

验证:
- 引擎按 LearnerProfile / 心流选策略（不再固定 reduction）
- 选中 jiangjie 时，其内部计数器（_atom_index）跨 respond 重建无损
- flow_regulator 的 pace 真的传进了策略
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import (
    KnowledgeGraphRow,
    LearnerProfileRow,
    Subject,
    User,
)
from shared.models import ConceptRow as ConceptRowORM
from shared.schemas import BehavioralProfile, FlowLevel, LearnerProfile
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _score(corr: str) -> str:
    return json.dumps({"correctness": corr, "raw_score": 0.9 if corr == "correct" else 0.1, "evidence": "x"}, ensure_ascii=False)


@pytest.fixture
def engine_env(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ce-shi", user_id="yhn", display_name="测试"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="测试", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    canned = [json.dumps({"definition": f"d{i}", "confidence": 0.85}, ensure_ascii=False) for i in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id, subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    with tmp_db.session() as s:
        first = s.query(ConceptRowORM).filter_by(kg_id=r.kg_id).order_by(ConceptRowORM.id).first()
        first_id = first.id
    return tmp_db, "ce-shi", first_id, r.kg_id


def _set_profile(db, user_id, **behavioral):
    profile = LearnerProfile(user_id=user_id, behavioral=BehavioralProfile(**behavioral))
    with db.session() as s:
        s.add(LearnerProfileRow(user_id=user_id, profile_json=profile.model_dump(mode="json")))
        s.commit()


def _new_session(db, subject_id, concept_id, kg_id):
    from servers.tutoring_mcp.session import SessionStore
    sessions = SessionStore(db)
    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = concept_id
    ctx.position_in_plan = 0
    ctx.teaching_plan_id = kg_id
    ctx.status = "active"
    sessions.save(ctx)
    return sessions, ctx.session_id


def test_default_selects_reduction(engine_env):
    """无画像、低 mastery、无历史 → 仍选 reduction（保持既有默认行为）。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_id, kg_id = engine_env
    engine = TeachingEngine(db=db, sessions=SessionStore(db))
    sessions, sid = _new_session(db, subject_id, first_id, kg_id)

    engine.next_action(sid)
    ctx = sessions.load(sid)
    assert ctx.current_strategy == "reduction"
    assert ctx.current_strategy_state == "INTRO"


def test_thorough_pace_selects_jiangjie(engine_env):
    """preferred_pace=thorough → 选降阶法。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_id, kg_id = engine_env
    _set_profile(db, "yhn", preferred_pace="thorough")
    engine = TeachingEngine(db=db, sessions=SessionStore(db))
    sessions, sid = _new_session(db, subject_id, first_id, kg_id)

    engine.next_action(sid)
    ctx = sessions.load(sid)
    assert ctx.current_strategy == "jiangjie"
    assert ctx.current_strategy_state == "GOAL"
    # pace 参数已存进策略内部快照
    assert "sub_step_count" in ctx.strategy_internal


def test_jiangjie_internal_counter_survives_reconstruction(engine_env):
    """选中 jiangjie 后，_atom_index 跨多次 respond 重建保持递增，不归零。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_id, kg_id = engine_env
    _set_profile(db, "yhn", preferred_pace="thorough")
    llm = MockLLMProvider(canned_responses=[_score("correct") for _ in range(20)])
    engine = TeachingEngine(db=db, sessions=SessionStore(db), llm=llm)
    sessions, sid = _new_session(db, subject_id, first_id, kg_id)

    engine.next_action(sid)  # 选 jiangjie，进入 GOAL
    engine.transition_event(sid, event="goal_understood", payload={})
    ctx = sessions.load(sid)
    assert ctx.current_strategy_state == "REDUCE"
    assert ctx.strategy_internal["_atom_index"] == 0

    engine.respond(sid, answer="答案1")
    ctx = sessions.load(sid)
    assert ctx.strategy_internal["_atom_index"] == 1, "第一次 respond 后原子计数应为 1"

    engine.respond(sid, answer="答案2")
    ctx = sessions.load(sid)
    assert ctx.strategy_internal["_atom_index"] == 2, "计数器没有被重建归零"


def test_silent_flow_pace_is_gentle(engine_env):
    """历史显示心流 SILENT → _compute_pace 给最温柔参数（sub_step_count=3）。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_id, kg_id = engine_env
    engine = TeachingEngine(db=db, sessions=SessionStore(db))
    sessions, sid = _new_session(db, subject_id, first_id, kg_id)
    ctx = sessions.load(sid)
    ctx.recent_history = [
        {"correctness": "incorrect", "flow_level": int(FlowLevel.SILENT)},
        {"correctness": "incorrect", "flow_level": int(FlowLevel.SILENT)},
    ]
    sessions.save(ctx)

    assert engine._current_flow_level(ctx) == FlowLevel.SILENT
    pace = engine._compute_pace(ctx)
    assert pace["sub_step_count"] == 3
    assert pace["scaffold_level"] == 3


def test_no_flow_at_session_start_returns_none(engine_env):
    """会话刚开始（历史不足）→ flow_level=None，不会误把默认 SILENT 当信号。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_id, kg_id = engine_env
    engine = TeachingEngine(db=db, sessions=SessionStore(db))
    sessions, sid = _new_session(db, subject_id, first_id, kg_id)
    ctx = sessions.load(sid)
    assert engine._current_flow_level(ctx) is None
