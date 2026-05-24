"""Engine T1 集成测试：LLMScorer + ErrorDiagnoser + 状态推进 + 自动切概念。

预期升级:
- respond 用 LLMScorer 替代 2-gram
- respond 在 partial/incorrect 时填 ResponseResult.error_analysis
- engine 用真实 ReductionStrategy 状态机：next_action 内容随状态变化
- strategy 到达 NEXT 状态时自动切到下一个 concept
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import KnowledgeGraphRow, Subject, User
from shared.models import ConceptRow as ConceptRowORM
from shared.schemas import ResponseResult, TeachingAction
from shared.storage import RelationalStore


FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich(name: str = "x") -> str:
    return json.dumps({"definition": f"{name} 的定义", "confidence": 0.85}, ensure_ascii=False)


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
    canned = [_enrich() for _ in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id, subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )

    with tmp_db.session() as s:
        first = (
            s.query(ConceptRowORM)
            .filter_by(kg_id=r.kg_id)
            .order_by(ConceptRowORM.id)
            .first()
        )
        first_id = first.id
    return tmp_db, "ce-shi", first_id, r.kg_id


def test_engine_uses_llm_scorer_when_provided(engine_env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept, _kg_id = engine_env
    sessions = SessionStore(db)

    # 给 engine 注入 MockLLM：让它故意判 incorrect
    llm = MockLLMProvider(canned_responses=[
        json.dumps({"correctness": "incorrect", "raw_score": 0.1, "evidence": "完全错"}, ensure_ascii=False),
        # 错误诊断的回复
        json.dumps({"error_type": "concept_confusion", "remediation_suggestion": "回到前置"}, ensure_ascii=False),
    ])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    engine.next_action(ctx.session_id)
    result = engine.respond(ctx.session_id, answer="任何内容")
    assert result.correctness == "incorrect"
    assert result.error_analysis is not None
    assert result.error_analysis.type == "concept_confusion"
    assert result.error_analysis.remediation


def test_engine_next_action_advances_through_states(engine_env) -> None:
    """重复 next_action + respond → strategy state 真的在变化。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept, _ = engine_env
    sessions = SessionStore(db)
    # LLM 给 correct
    llm_correct = MockLLMProvider(canned_responses=[
        json.dumps({"correctness": "correct", "raw_score": 0.9, "evidence": "ok"}, ensure_ascii=False)
        for _ in range(10)
    ])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm_correct)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    a1 = engine.next_action(ctx.session_id)
    assert a1.type == "explain"
    state1 = sessions.load(ctx.session_id).current_strategy_state
    assert state1 == "INTRO"

    # 触发 intro → EXPLAIN
    engine.transition_event(ctx.session_id, event="intro_done", payload={})
    a2 = engine.next_action(ctx.session_id)
    assert a2.type in ("show_example", "explain")
    state2 = sessions.load(ctx.session_id).current_strategy_state
    assert state2 == "EXPLAIN"

    engine.transition_event(ctx.session_id, event="explain_done", payload={})
    a3 = engine.next_action(ctx.session_id)
    assert a3.type == "ask_question"
    state3 = sessions.load(ctx.session_id).current_strategy_state
    assert state3 == "CHECK"

    # 答对 → PRACTICE
    engine.respond(ctx.session_id, answer="正确答案")
    state4 = sessions.load(ctx.session_id).current_strategy_state
    assert state4 == "PRACTICE"


def test_engine_advances_to_next_concept_on_reduction_next(engine_env) -> None:
    """strategy 达到 NEXT 状态 + practice_done → current_concept_id 切到下一个。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept, kg_id = engine_env
    sessions = SessionStore(db)
    llm = MockLLMProvider(canned_responses=[
        json.dumps({"correctness": "correct", "raw_score": 0.9, "evidence": "ok"}, ensure_ascii=False)
        for _ in range(20)
    ])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.position_in_plan = 0
    ctx.status = "active"
    ctx.teaching_plan_id = kg_id
    sessions.save(ctx)

    engine.next_action(ctx.session_id)
    engine.transition_event(ctx.session_id, event="intro_done", payload={})
    engine.transition_event(ctx.session_id, event="explain_done", payload={})
    engine.respond(ctx.session_id, answer="正确")  # CHECK→PRACTICE
    # PRACTICE_done(高准确率) → NEXT
    engine.transition_event(ctx.session_id, event="practice_done", payload={"accuracy": 0.9})
    # 再调一次 next_action → engine 应该检测到 NEXT 状态、切到下一概念
    engine.next_action(ctx.session_id)

    new_ctx = sessions.load(ctx.session_id)
    assert new_ctx.current_concept_id != first_concept
    assert new_ctx.position_in_plan == 1
    assert new_ctx.current_strategy_state == "INTRO"  # 新 concept 从头开始


def test_engine_marks_session_complete_when_plan_exhausted(engine_env) -> None:
    """所有 concept 走完后 session.status='completed'。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, _first, kg_id = engine_env
    sessions = SessionStore(db)
    llm = MockLLMProvider(canned_responses=[
        json.dumps({"correctness": "correct", "raw_score": 0.9, "evidence": "ok"}, ensure_ascii=False)
        for _ in range(50)
    ])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    # 让 plan 只有最后一个 concept
    with db.session() as s:
        last_concept = (
            s.query(ConceptRowORM)
            .filter_by(kg_id=kg_id)
            .order_by(ConceptRowORM.id.desc())
            .first()
        )
        last_id = last_concept.id

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = last_id
    # position 指向"已经在最后一个概念"
    ctx.position_in_plan = 999  # 故意越界
    ctx.status = "active"
    ctx.teaching_plan_id = kg_id
    sessions.save(ctx)

    engine.next_action(ctx.session_id)
    engine.transition_event(ctx.session_id, event="intro_done", payload={})
    engine.transition_event(ctx.session_id, event="explain_done", payload={})
    engine.respond(ctx.session_id, answer="正确")
    engine.transition_event(ctx.session_id, event="practice_done", payload={"accuracy": 0.9})
    engine.next_action(ctx.session_id)

    new_ctx = sessions.load(ctx.session_id)
    assert new_ctx.status == "completed"


def test_engine_skips_mastered_first_concept(engine_env) -> None:
    """冷启动种了高 mastery 的首概念 → next_action 跳过它，直接教下一个。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, _first, kg_id = engine_env
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)

    order = engine._topo_order(kg_id)
    assert len(order) >= 2

    # 种第一个概念为已掌握
    engine.bkt.seed_prior(user_id="yhn", concept_id=order[0], mastery=0.9)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = order[0]
    ctx.position_in_plan = 0
    ctx.teaching_plan_id = kg_id
    ctx.status = "active"
    sessions.save(ctx)

    engine.next_action(ctx.session_id)
    new_ctx = sessions.load(ctx.session_id)
    assert new_ctx.current_concept_id == order[1]   # 跳过了 order[0]
    assert new_ctx.position_in_plan == 1


def test_engine_skips_consecutive_mastered(engine_env) -> None:
    """连续多个已掌握 → 一次跳到第一个未掌握。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, _first, kg_id = engine_env
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)

    order = engine._topo_order(kg_id)
    assert len(order) >= 3
    engine.bkt.seed_prior(user_id="yhn", concept_id=order[0], mastery=0.9)
    engine.bkt.seed_prior(user_id="yhn", concept_id=order[1], mastery=0.95)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = order[0]
    ctx.position_in_plan = 0
    ctx.teaching_plan_id = kg_id
    ctx.status = "active"
    sessions.save(ctx)

    engine.next_action(ctx.session_id)
    new_ctx = sessions.load(ctx.session_id)
    assert new_ctx.current_concept_id == order[2]
    assert new_ctx.position_in_plan == 2


def test_engine_does_not_skip_in_progress_concept(engine_env) -> None:
    """概念教到一半（state=INTRO）即便被标记掌握也不打断。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, _first, kg_id = engine_env
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)

    order = engine._topo_order(kg_id)
    engine.bkt.seed_prior(user_id="yhn", concept_id=order[0], mastery=0.9)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = order[0]
    ctx.position_in_plan = 0
    ctx.teaching_plan_id = kg_id
    ctx.current_strategy = "reduction"
    ctx.current_strategy_state = "INTRO"  # 进行中
    ctx.status = "active"
    sessions.save(ctx)

    engine.next_action(ctx.session_id)
    new_ctx = sessions.load(ctx.session_id)
    assert new_ctx.current_concept_id == order[0]  # 没被跳过


def test_engine_all_mastered_completes(engine_env) -> None:
    """全部概念已掌握 → 直接 completed。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, _first, kg_id = engine_env
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)

    order = engine._topo_order(kg_id)
    for cid in order:
        engine.bkt.seed_prior(user_id="yhn", concept_id=cid, mastery=0.9)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = order[0]
    ctx.position_in_plan = 0
    ctx.teaching_plan_id = kg_id
    ctx.status = "active"
    sessions.save(ctx)

    action = engine.next_action(ctx.session_id)
    new_ctx = sessions.load(ctx.session_id)
    assert new_ctx.status == "completed"
    assert action.type == "reflection"


def test_engine_enriches_action_content_with_generation_llm(engine_env) -> None:
    """provider.supports_generation=True → next_action 的讲解内容被 LLM 改写。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept, _ = engine_env
    sessions = SessionStore(db)
    llm = MockLLMProvider(
        canned_responses=["这是 LLM 生成的生动讲解，配了一个具体例子。"],
        supports_generation=True,
    )
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    action = engine.next_action(ctx.session_id)
    assert action.content == "这是 LLM 生成的生动讲解，配了一个具体例子。"
    assert action.metadata.get("generated") is True
    assert len(llm.calls) == 1


def test_engine_polishes_feedback_with_generation_llm(engine_env) -> None:
    """provider.supports_generation=True → respond 的反馈被 LLM 润色（L3）。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept, _ = engine_env
    sessions = SessionStore(db)
    # 答对：scorer 用第 1 个 canned，无诊断，feedback_gen 用第 2 个 canned
    llm = MockLLMProvider(
        canned_responses=[
            json.dumps({"correctness": "correct", "raw_score": 0.9, "evidence": "ok"}, ensure_ascii=False),
            "你把定义和直觉对上了，这一步很关键，我们继续看下一个。",
        ],
        supports_generation=True,
    )
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    result = engine.respond(ctx.session_id, answer="极限是无限接近的值")
    assert result.feedback == "你把定义和直觉对上了，这一步很关键，我们继续看下一个。"


def test_engine_default_llm_keeps_template_content(engine_env) -> None:
    """无生成能力（默认 Stub）→ next_action 内容保持策略模板，不调 LLM 生成。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept, _ = engine_env
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)  # StubLLM

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    action = engine.next_action(ctx.session_id)
    assert action.metadata.get("generated") is not True
    assert action.content  # 模板内容仍在


def test_engine_default_llm_falls_back_to_heuristic_scoring(engine_env) -> None:
    """没传 llm 时仍能工作（用 stub→启发式）。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept, _ = engine_env
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)  # 不传 llm

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    engine.next_action(ctx.session_id)
    result = engine.respond(ctx.session_id, answer="任何内容")
    # 没 llm → 走启发式判分；不会抛错
    assert isinstance(result, ResponseResult)
    assert result.feedback
