"""checkpoint() 实现契约测试。

handle_checkpoint(session_id, kind="self_summary", content="...") → dict

设计:
- LLM 把学生自评文本映射到 0-1 score（"我都会了" → 0.9, "完全不懂" → 0.1）
- 对比 BKT 实际 mastery（avg over current session 的 concepts_covered）
- 算 self_assessment_accuracy = 1 - |self - actual|
- 更新 LearnerProfile.metacognitive.self_assessment_accuracy
- 返回 current_mastery_map + cognitive_load + suggestions
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider, StubLLMProvider
from shared.models import ConceptRow as ConceptRowORM
from shared.models import (
    LearnerProfileRow,
    Subject,
    User,
)
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich() -> str:
    return json.dumps({"definition": "x", "confidence": 0.85}, ensure_ascii=False)


def _self_score(score: float, confidence: float = 0.9) -> str:
    return json.dumps({"self_score": score, "confidence": confidence}, ensure_ascii=False)


@pytest.fixture
def env(tmp_db: RelationalStore, tmp_filestore):
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
    llm_kg = MockLLMProvider(canned_responses=[_enrich() for _ in range(50)])
    r = ConceptKGBuilder(llm=llm_kg).build(
        corpus_id=corpus_id, subject_slug="ml",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )

    # 拿前 3 个 concept 写 BKT
    from servers.tutoring_mcp.bkt_store import BKTStore
    from shared.schemas import BKTParams
    bkt = BKTStore(tmp_db)
    with tmp_db.session() as s:
        rows = (
            s.query(ConceptRowORM)
            .filter_by(kg_id=r.kg_id)
            .order_by(ConceptRowORM.id)
            .limit(3)
            .all()
        )
        ids = [c.id for c in rows]

    # 让 mastery 平均约 0.7
    bkt.save("yhn", BKTParams(concept_id=ids[0], p_mastery=0.85, n_observations=5))
    bkt.save("yhn", BKTParams(concept_id=ids[1], p_mastery=0.65, n_observations=4))
    bkt.save("yhn", BKTParams(concept_id=ids[2], p_mastery=0.55, n_observations=3))

    return tmp_db, ids, r.kg_id


def _start_session(db, ids):
    from servers.tutoring_mcp.session import SessionStore
    sessions = SessionStore(db)
    ctx = sessions.create(user_id="yhn", subject_id="ml")
    ctx.current_concept_id = ids[0]
    ctx.status = "active"
    ctx.session_stats.concepts_covered = ids  # 跑过的 3 个
    sessions.save(ctx)
    return sessions, ctx


def test_checkpoint_returns_mastery_map(env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine

    db, ids, _ = env
    sessions, ctx = _start_session(db, ids)

    llm = MockLLMProvider(canned_responses=[_self_score(0.7)])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    result = engine.handle_checkpoint(
        ctx.session_id, kind="self_summary",
        content="我感觉基本都懂了，少数地方还不太确定",
    )
    assert "current_mastery_map" in result
    mm = result["current_mastery_map"]
    assert ids[0] in mm
    assert ids[1] in mm
    assert ids[2] in mm


def test_checkpoint_computes_self_assessment_accuracy(env) -> None:
    """学生说 0.7，实际 avg(0.85+0.65+0.55)/3 = 0.68 → accuracy = 1 - |0.7-0.68| ≈ 0.98。"""
    from servers.tutoring_mcp.engine import TeachingEngine

    db, ids, _ = env
    sessions, ctx = _start_session(db, ids)

    llm = MockLLMProvider(canned_responses=[_self_score(0.7)])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    result = engine.handle_checkpoint(ctx.session_id, content="还行吧大约 70%")
    assert "self_assessment_accuracy" in result
    assert result["self_assessment_accuracy"] > 0.9


def test_checkpoint_low_accuracy_when_student_overconfident(env) -> None:
    """学生自评 0.95，实际 0.68 → 低 accuracy。"""
    from servers.tutoring_mcp.engine import TeachingEngine

    db, ids, _ = env
    sessions, ctx = _start_session(db, ids)
    llm = MockLLMProvider(canned_responses=[_self_score(0.95)])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    result = engine.handle_checkpoint(ctx.session_id, content="我全都懂了")
    assert result["self_assessment_accuracy"] < 0.8


def test_checkpoint_persists_profile_update(env) -> None:
    """更新 LearnerProfile.metacognitive.self_assessment_accuracy 到 DB。"""
    from servers.tutoring_mcp.engine import TeachingEngine

    db, ids, _ = env
    sessions, ctx = _start_session(db, ids)
    llm = MockLLMProvider(canned_responses=[_self_score(0.7)])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    engine.handle_checkpoint(ctx.session_id, content="差不多 70%")

    with db.session() as s:
        row = s.get(LearnerProfileRow, "yhn")
    assert row is not None
    # profile_json 是 dict（SQLAlchemy JSON 列）
    profile = row.profile_json
    assert profile["metacognitive"]["self_assessment_accuracy"] is not None


def test_checkpoint_falls_back_when_llm_unavailable(env) -> None:
    """StubLLM 时降级为启发式（关键词 / 长度），不抛错。"""
    from servers.tutoring_mcp.engine import TeachingEngine

    db, ids, _ = env
    sessions, ctx = _start_session(db, ids)
    engine = TeachingEngine(db=db, sessions=sessions, llm=StubLLMProvider())
    result = engine.handle_checkpoint(ctx.session_id, content="我觉得我都会了")
    assert "self_assessment_accuracy" in result
    assert "current_mastery_map" in result


def test_checkpoint_returns_suggestions(env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine

    db, ids, _ = env
    sessions, ctx = _start_session(db, ids)
    llm = MockLLMProvider(canned_responses=[_self_score(0.95)])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    result = engine.handle_checkpoint(ctx.session_id, content="全会了")
    suggestions = result.get("suggestions") or []
    assert isinstance(suggestions, list)
    # over-confidence → 应至少给一条建议
    assert len(suggestions) >= 1


def test_checkpoint_empty_session_concepts(env) -> None:
    """concepts_covered 空 → 用所有有 BKT 记录的 concept 兜底。"""
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, ids, _ = env
    sessions = SessionStore(db)
    ctx = sessions.create(user_id="yhn", subject_id="ml")
    ctx.current_concept_id = ids[0]
    ctx.status = "active"
    # session_stats.concepts_covered 默认空
    sessions.save(ctx)

    llm = MockLLMProvider(canned_responses=[_self_score(0.5)])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    result = engine.handle_checkpoint(ctx.session_id, content="一般般")
    # 应仍能给出 mastery_map（基于本用户所有 BKT）
    assert "current_mastery_map" in result


@pytest.mark.asyncio
async def test_checkpoint_tool_no_longer_stub(env) -> None:
    from servers.tutoring_mcp import server as srv
    from shared.errors import TutorError

    db, ids, _ = env
    sessions, ctx = _start_session(db, ids)

    import os
    os.environ["DATABASE_URL"] = db.url

    fn = getattr(srv.checkpoint, "fn", srv.checkpoint)
    try:
        out = await fn(session_id=ctx.session_id, content="还行")
        assert "current_mastery_map" in out
    except TutorError as exc:
        assert exc.code != "DEPENDENCY_MISSING"
