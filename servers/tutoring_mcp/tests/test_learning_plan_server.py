"""多 Session 调度 MCP tools 集成测试（P0 #3）：get_learning_progress + resume_learning。

验证跨 Session 续学：第 1 次会话学掉一些概念 → 进度持久化 → 第 2 次 resume 从下一个继续。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from servers.tutoring_mcp import server as srv
from servers.tutoring_mcp.bkt_store import BKTStore
from shared.llm_client import MockLLMProvider
from shared.models import Subject, User
from shared.models import ConceptRow as ConceptRowORM
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _fn(t):
    return getattr(t, "fn", None) or getattr(t, "func", None) or t


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tut.db'}")
    monkeypatch.setenv("AI_TUTOR_DATA_ROOT", str(tmp_path / "data"))
    store = RelationalStore.from_env()
    store.init_schema()
    with store.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ce-shi", user_id="yhn", display_name="测试"))
        s.commit()
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from shared.storage import FileStore

    man, cid = acquire(
        subject="测试", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=FileStore(tmp_path / "data"), db=store,
    )
    canned = [json.dumps({"definition": f"d{i}", "confidence": 0.85}, ensure_ascii=False) for i in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=cid, subject_slug="ce-shi",
        markdown_path=Path(man.file_paths["markdown"]), db=store,
    )
    with store.session() as s:
        s.get(Subject, "ce-shi").kg_id = r.kg_id
        s.commit()
        ids = [c.id for c in s.query(ConceptRowORM).filter_by(kg_id=r.kg_id).order_by(ConceptRowORM.id).all()]
    return store, "ce-shi", r.kg_id, ids


@pytest.mark.asyncio
async def test_tools_registered(env):
    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    assert "get_learning_progress" in names
    assert "resume_learning" in names


@pytest.mark.asyncio
async def test_progress_fresh(env):
    store, subject_id, _kg, _ids = env
    prog = await _fn(srv.get_learning_progress)(user_id="yhn", subject_id=subject_id)
    assert prog.concepts_total > 0
    assert prog.concepts_mastered == 0
    assert prog.current_phase == 1
    assert prog.next_concept_id is not None
    assert not prog.completed
    assert len(prog.phases) >= 1
    # 计划被持久化
    from shared.models import LearningPlanRow
    with store.session() as s:
        assert s.get(LearningPlanRow, ("yhn", subject_id)) is not None


@pytest.mark.asyncio
async def test_progress_reflects_mastery(env):
    store, subject_id, kg, _ids = env
    # 先建计划，拿到第 1 个 Phase 的概念
    prog0 = await _fn(srv.get_learning_progress)(user_id="yhn", subject_id=subject_id)
    phase1_ids = prog0.phases[0]
    # 把第 1 个 Phase 全部种成已掌握
    from servers.tutoring_mcp import learning_plan as lp
    plan = lp.LearningPlanStore(store).load("yhn", subject_id)
    bkt = BKTStore(store)
    for cid in plan.phases[0].concept_ids:
        bkt.seed_prior(user_id="yhn", concept_id=cid, mastery=0.9)

    prog = await _fn(srv.get_learning_progress)(user_id="yhn", subject_id=subject_id)
    assert prog.concepts_mastered == len(plan.phases[0].concept_ids)
    assert prog.phases[0].status == "done"
    if len(prog.phases) > 1:
        assert prog.current_phase == 2


@pytest.mark.asyncio
async def test_resume_creates_session_when_none(env):
    store, subject_id, _kg, _ids = env
    started = await _fn(srv.resume_learning)(user_id="yhn", subject_id=subject_id)
    assert started.session_id
    assert started.current_action.content
    assert started.pre_session_insight is not None
    assert "继续" in started.pre_session_insight or "掌握" in started.pre_session_insight


@pytest.mark.asyncio
async def test_resume_reuses_open_session(env):
    store, subject_id, _kg, _ids = env
    s1 = await _fn(srv.start_learning_session)(user_id="yhn", subject_id=subject_id)
    again = await _fn(srv.resume_learning)(user_id="yhn", subject_id=subject_id)
    assert again.session_id == s1.session_id  # 复用同一个未结束会话
    assert again.pre_session_insight.startswith("接着上次")


@pytest.mark.asyncio
async def test_cross_session_continuity(env):
    """第 1 次会话掌握部分概念 → 第 2 次（新会话）从下一个未掌握继续。"""
    store, subject_id, _kg, _ids = env
    plan_store_progress = await _fn(srv.get_learning_progress)(user_id="yhn", subject_id=subject_id)
    first_concept = plan_store_progress.next_concept_id

    # 模拟第 1 次会话：把第一个概念学会
    BKTStore(store).seed_prior(user_id="yhn", concept_id=first_concept, mastery=0.9)

    prog = await _fn(srv.get_learning_progress)(user_id="yhn", subject_id=subject_id)
    assert prog.next_concept_id != first_concept  # 下一个该学的已经前移
    assert prog.concepts_mastered >= 1
