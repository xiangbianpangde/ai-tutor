"""interrupt() 实现契约测试。

调用模式:
    engine.handle_interrupt(session_id, question) → InterruptResult

工作流（spec interrupt §4）:
  1. 保存 SessionContext.interrupt_checkpoint
  2. IntentClassifier 分 5 类
  3. 不同分支:
     concept_question    → type=context_aware_answer + 调 KG 给定义
     prereq_gap          → type=prereq_tutorial + 提示前置概念
     pace_complaint      → type=pace_adjustment + 降速/跳过建议
     distraction         → type=redirect + 温和拉回
     cognitive_overload  → type=pace_adjustment + 建议休息
  4. 返回 InterruptResult.resume_prompt 让学生回来
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import KnowledgeGraphRow, Subject, User
from shared.models import ConceptRow as ConceptRowORM
from shared.schemas import InterruptResult
from shared.storage import RelationalStore


FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich(c: float = 0.85) -> str:
    return json.dumps({"definition": "x", "confidence": c}, ensure_ascii=False)


def _intent_resp(intent: str) -> str:
    return json.dumps({"intent": intent, "confidence": 0.9, "evidence": "test"}, ensure_ascii=False)


@pytest.fixture
def engine_env(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ml", user_id="yhn", display_name="ML"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ml", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    llm = MockLLMProvider(canned_responses=[_enrich() for _ in range(50)])
    r = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="ml",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    with tmp_db.session() as s:
        s.get(Subject, "ml").kg_id = r.kg_id
        first = (
            s.query(ConceptRowORM)
            .filter_by(kg_id=r.kg_id)
            .order_by(ConceptRowORM.id)
            .first()
        )
        first_id = first.id
    return tmp_db, "ml", first_id


def _start_session(db, subject_id: str, concept_id: str):
    from servers.tutoring_mcp.session import SessionStore
    sessions = SessionStore(db)
    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = concept_id
    ctx.status = "active"
    ctx.current_strategy = "reduction"
    ctx.current_strategy_state = "EXPLAIN"
    sessions.save(ctx)
    return sessions, ctx


def test_interrupt_concept_question(engine_env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, concept_id = engine_env
    sessions, ctx = _start_session(db, subject_id, concept_id)

    # 第一次调 LLM = 意图分类；第二次 = 概念回答（如果 LLM 路径还要二次调）
    llm = MockLLMProvider(canned_responses=[
        _intent_resp("concept_question"),
    ])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    result = engine.handle_interrupt(ctx.session_id, question="什么是词袋模型？")
    assert isinstance(result, InterruptResult)
    assert result.type == "context_aware_answer"
    assert result.content  # 非空回复
    assert result.checkpoint_saved is True
    assert result.resume_prompt  # 应有恢复提示


def test_interrupt_prereq_gap(engine_env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, concept_id = engine_env
    sessions, ctx = _start_session(db, subject_id, concept_id)
    llm = MockLLMProvider(canned_responses=[_intent_resp("prereq_gap")])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    result = engine.handle_interrupt(ctx.session_id, question="向量是什么？")
    assert result.type == "prereq_tutorial"
    assert result.suggested_action in ("resume", "explore_further")


def test_interrupt_pace_complaint(engine_env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine

    db, subject_id, concept_id = engine_env
    sessions, ctx = _start_session(db, subject_id, concept_id)
    llm = MockLLMProvider(canned_responses=[_intent_resp("pace_complaint")])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    result = engine.handle_interrupt(ctx.session_id, question="太慢了，能跳过吗")
    assert result.type == "pace_adjustment"
    # PGFGA: 让学生自主决定
    assert result.suggested_action in ("change_topic", "resume")


def test_interrupt_cognitive_overload_recommends_break(engine_env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine

    db, subject_id, concept_id = engine_env
    sessions, ctx = _start_session(db, subject_id, concept_id)
    llm = MockLLMProvider(canned_responses=[_intent_resp("cognitive_overload")])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    result = engine.handle_interrupt(ctx.session_id, question="我有点晕了")
    assert result.type == "pace_adjustment"
    # 应建议休息
    assert "休息" in result.content or "break" in result.content.lower()


def test_interrupt_distraction_gentle_redirect(engine_env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine

    db, subject_id, concept_id = engine_env
    sessions, ctx = _start_session(db, subject_id, concept_id)
    llm = MockLLMProvider(canned_responses=[_intent_resp("distraction")])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    result = engine.handle_interrupt(ctx.session_id, question="今天天气真好")
    assert result.type == "redirect"
    # PGFGA 防火墙：不含禁词
    forbidden = ["你应该", "不对", "回到正题", "想太多"]
    for w in forbidden:
        assert w not in result.content


def test_interrupt_saves_checkpoint_to_session(engine_env) -> None:
    """interrupt 应把当前 strategy state + concept 写入 session.interrupt_checkpoint。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, concept_id = engine_env
    sessions, ctx = _start_session(db, subject_id, concept_id)
    llm = MockLLMProvider(canned_responses=[_intent_resp("distraction")])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    engine.handle_interrupt(ctx.session_id, question="今天天气好")

    reloaded = sessions.load(ctx.session_id)
    cp = reloaded.interrupt_checkpoint
    assert cp is not None
    assert cp.current_concept_id == concept_id
    assert cp.strategy == "reduction"
    assert cp.strategy_state == "EXPLAIN"


def test_interrupt_session_meta_count_incremented(engine_env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine

    db, subject_id, concept_id = engine_env
    sessions, ctx = _start_session(db, subject_id, concept_id)
    before = ctx.meta.interrupt_count
    llm = MockLLMProvider(canned_responses=[_intent_resp("distraction")])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    engine.handle_interrupt(ctx.session_id, question="天气好")

    reloaded = sessions.load(ctx.session_id)
    assert reloaded.meta.interrupt_count == before + 1


@pytest.mark.asyncio
async def test_interrupt_tool_no_longer_stub(engine_env) -> None:
    from servers.tutoring_mcp import server as srv
    from shared.errors import TutorError

    db, subject_id, concept_id = engine_env
    sessions, ctx = _start_session(db, subject_id, concept_id)

    import os
    os.environ["DATABASE_URL"] = db.url

    fn = getattr(srv.interrupt, "fn", srv.interrupt)
    # 没真实 LLM key → 走启发式（distraction），不应抛 DEPENDENCY_MISSING
    try:
        result = await fn(session_id=ctx.session_id, question="今天天气好")
        assert result.type in ("context_aware_answer", "prereq_tutorial",
                                "pace_adjustment", "redirect")
    except TutorError as exc:
        assert exc.code != "DEPENDENCY_MISSING"
