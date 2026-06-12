"""冷启动摸底 MCP tools 的集成 smoke test：cold_start_probe + submit_cold_start。

验证:
- 出题 → 判分 → 种 BKT 先验 + 写画像初值
- 已摸底用户 already_assessed=True
- 摸底后 start_learning_session 把已掌握概念从教学路径跳过
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from servers.tutoring_mcp import server as srv
from shared.llm_client import MockLLMProvider
from shared.models import BKTParamRow, LearnerProfileRow, Subject, User
from shared.models import ConceptRow as ConceptRowORM
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _unwrap(tool_obj):
    return getattr(tool_obj, "fn", None) or getattr(tool_obj, "func", None) or tool_obj


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

    fs = FileStore(tmp_path / "data")
    manifest, corpus_id = acquire(
        subject="测试", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=fs, db=store,
    )
    canned = [json.dumps({"definition": f"定义{i}", "confidence": 0.85}, ensure_ascii=False) for i in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id, subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]), db=store,
    )
    with store.session() as s:
        s.get(Subject, "ce-shi").kg_id = r.kg_id
        s.commit()
        concept_ids = [c.id for c in s.query(ConceptRowORM).filter_by(kg_id=r.kg_id).all()]
        names = {
            c.id: c.full_json["names"][0]
            for c in s.query(ConceptRowORM).filter_by(kg_id=r.kg_id).all()
        }
    return store, "ce-shi", concept_ids, names


@pytest.mark.asyncio
async def test_tools_registered(env) -> None:
    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    assert "cold_start_probe" in names
    assert "submit_cold_start" in names


@pytest.mark.asyncio
async def test_probe_returns_questions(env) -> None:
    _store, subject_id, concept_ids, _names = env
    probe_fn = _unwrap(srv.cold_start_probe)

    probe_set = await probe_fn(user_id="yhn", subject_id=subject_id, num_questions=10)
    assert not probe_set.already_assessed
    assert 1 <= len(probe_set.probes) <= min(10, len(concept_ids))
    assert all(p.question for p in probe_set.probes)
    assert all(p.concept_id in concept_ids for p in probe_set.probes)


def _judge_correct() -> str:
    """冷启动判分 LLM 的 canned 响应（FIX-L 后启发式封顶 partial，
    种"已掌握"必须经真实判分器判 correct，测试里用 Mock LLM 显式给出）。"""
    return json.dumps(
        {"correctness": "correct", "raw_score": 0.9, "evidence": "测试 canned 判分"},
        ensure_ascii=False,
    )


@pytest.mark.asyncio
async def test_submit_seeds_bkt_and_profile(env, monkeypatch: pytest.MonkeyPatch) -> None:
    store, subject_id, _concept_ids, names = env
    monkeypatch.setattr(
        srv, "_llm", lambda: MockLLMProvider(canned_responses=[_judge_correct()] * 12)
    )
    probe_fn = _unwrap(srv.cold_start_probe)
    submit_fn = _unwrap(srv.submit_cold_start)

    probe_set = await probe_fn(user_id="yhn", subject_id=subject_id, num_questions=6)
    # 判分器判 correct → 种为已掌握
    answers = [
        {"concept_id": p.concept_id, "answer": names[p.concept_id], "self_report": "sure"}
        for p in probe_set.probes
    ]
    result = await submit_fn(user_id="yhn", subject_id=subject_id, answers=answers)

    assert result.probes_graded == len(probe_set.probes)
    assert result.seeded_mastered  # 至少种了一个已掌握
    assert result.recommended_starting_level in ("beginner", "intermediate", "advanced")

    # BKT 先验落库
    with store.session() as s:
        rows = s.query(BKTParamRow).filter_by(user_id="yhn").all()
        assert len(rows) == len(probe_set.probes)
        assert any(r.p_mastery >= 0.8 for r in rows)
        # 画像初值落库
        prof = s.get(LearnerProfileRow, "yhn")
        assert prof is not None
        assert "cognitive" in prof.profile_json


@pytest.mark.asyncio
async def test_probe_already_assessed_after_submit(env, monkeypatch: pytest.MonkeyPatch) -> None:
    _store, subject_id, _concept_ids, names = env
    monkeypatch.setattr(
        srv, "_llm", lambda: MockLLMProvider(canned_responses=[_judge_correct()] * 12)
    )
    probe_fn = _unwrap(srv.cold_start_probe)
    submit_fn = _unwrap(srv.submit_cold_start)

    probe_set = await probe_fn(user_id="yhn", subject_id=subject_id, num_questions=5)
    answers = [
        {"concept_id": p.concept_id, "answer": names[p.concept_id], "self_report": "sure"}
        for p in probe_set.probes
    ]
    await submit_fn(user_id="yhn", subject_id=subject_id, answers=answers)

    again = await probe_fn(user_id="yhn", subject_id=subject_id, num_questions=5)
    assert again.already_assessed
    assert again.probes == []


@pytest.mark.asyncio
async def test_no_llm_name_parrot_seeds_nothing_mastered(env) -> None:
    """FIX-L 回归：LLM 不可用（默认 Stub→启发式）时，用概念名复读作答
    不得再种出"已掌握"先验——启发式封顶 partial（先验 ≤ 0.575 < 0.8）。
    修复前：含名作答 → 启发式 correct 0.7 → 白拿 0.88 先验。"""
    store, subject_id, _concept_ids, names = env
    probe_fn = _unwrap(srv.cold_start_probe)
    submit_fn = _unwrap(srv.submit_cold_start)

    probe_set = await probe_fn(user_id="yhn", subject_id=subject_id, num_questions=6)
    answers = [
        {"concept_id": p.concept_id, "answer": names[p.concept_id], "self_report": "sure"}
        for p in probe_set.probes
    ]
    result = await submit_fn(user_id="yhn", subject_id=subject_id, answers=answers)

    assert result.probes_graded == len(probe_set.probes)  # 判分流程本身不受影响
    assert result.seeded_mastered == []  # 无 LLM 不发掌握认证
    with store.session() as s:
        rows = s.query(BKTParamRow).filter_by(user_id="yhn").all()
        assert rows  # 先验仍落库（partial 档）
        assert all(r.p_mastery < 0.8 for r in rows)


@pytest.mark.asyncio
async def test_start_session_skips_mastered_after_cold_start(
    env, monkeypatch: pytest.MonkeyPatch
) -> None:
    _store, subject_id, _concept_ids, names = env
    monkeypatch.setattr(
        srv, "_llm", lambda: MockLLMProvider(canned_responses=[_judge_correct()] * 12)
    )
    probe_fn = _unwrap(srv.cold_start_probe)
    submit_fn = _unwrap(srv.submit_cold_start)
    start_fn = _unwrap(srv.start_learning_session)

    probe_set = await probe_fn(user_id="yhn", subject_id=subject_id, num_questions=8)
    answers = [
        {"concept_id": p.concept_id, "answer": names[p.concept_id], "self_report": "sure"}
        for p in probe_set.probes
    ]
    result = await submit_fn(user_id="yhn", subject_id=subject_id, answers=answers)

    started = await start_fn(user_id="yhn", subject_id=subject_id, goal="48h_sprint")
    plan = started.teaching_plan
    # 摸底种下的已掌握概念，反映在 Phase 化教学计划的 concepts_mastered 上
    assert plan["concepts_mastered"] == len(result.seeded_mastered)
    assert 0 < plan["concepts_mastered"] < plan["total_concepts"]
    assert plan["overall_mastery_ratio"] > 0
    # 至少有一个 Phase 出现已掌握进度
    assert any(ph["concepts_mastered"] > 0 for ph in plan["phases"])


@pytest.mark.asyncio
async def test_start_session_hints_when_not_assessed(env) -> None:
    _store, subject_id, _concept_ids, _names = env
    start_fn = _unwrap(srv.start_learning_session)
    started = await start_fn(user_id="yhn", subject_id=subject_id, goal="48h_sprint")
    assert started.pre_session_insight is not None
    assert "摸底" in started.pre_session_insight
