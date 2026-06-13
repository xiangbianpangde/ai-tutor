"""Engine T3 集成测试：心流追踪 + 回路检测。

期望升级:
- engine.respond 每轮算 FlowSignals → 更新 ctx.meta（用 dict 字段存 flow_level）
- recent_history 记录 turn（answer/correctness/timestamp）
- 检测到回路断裂 → ResponseResult.next_action = repair action
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import ConceptRow as ConceptRowORM
from shared.models import Subject, User
from shared.schemas import FlowLevel
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich() -> str:
    return json.dumps({"definition": "x", "confidence": 0.85}, ensure_ascii=False)


@pytest.fixture
def engine_env(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.tutoring_mcp.session import SessionStore

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
        first_id = (
            s.query(ConceptRowORM).filter_by(kg_id=r.kg_id)
            .order_by(ConceptRowORM.id).first().id
        )

    sessions = SessionStore(tmp_db)
    ctx = sessions.create(user_id="yhn", subject_id="ml")
    ctx.current_concept_id = first_id
    ctx.status = "active"
    ctx.current_strategy = "reduction"
    ctx.current_strategy_state = "CHECK"
    sessions.save(ctx)

    return tmp_db, sessions, ctx, llm


def test_respond_records_turn_in_recent_history(engine_env) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine

    db, sessions, ctx, llm = engine_env
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    engine.respond(ctx.session_id, answer="一个回答")

    reloaded = sessions.load(ctx.session_id)
    # recent_history 至少多了一条
    assert len(reloaded.recent_history) >= 1
    last = reloaded.recent_history[-1]
    assert last["answer"] == "一个回答"
    assert "correctness" in last


def test_flow_level_persisted_in_session(engine_env) -> None:
    """每次 respond 后应把 FlowLevel 存到 session（recent_history 或单独字段）。"""
    from servers.tutoring_mcp.engine import TeachingEngine

    db, sessions, ctx, llm = engine_env
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)
    engine.respond(ctx.session_id, answer="任何答案")

    reloaded = sessions.load(ctx.session_id)
    # 借 session_stats.errors_by_type 这种 dict 是不行的 — 用 focus.last_action_type 或 recent_history meta
    # 约定：把 flow_level 存进 recent_history 最新条目的 metadata
    last = reloaded.recent_history[-1]
    assert "flow_level" in last


def test_progressive_growth_raises_flow_level(engine_env) -> None:
    """多轮表现好的回答应让 flow_level 提升。"""
    from servers.tutoring_mcp.engine import TeachingEngine

    db, sessions, ctx, llm = engine_env
    # 用 MockLLM 总判 correct
    correct_llm = MockLLMProvider(canned_responses=[
        json.dumps({"correctness": "correct", "raw_score": 0.9, "evidence": "ok"}, ensure_ascii=False)
        for _ in range(20)
    ])
    engine = TeachingEngine(db=db, sessions=sessions, llm=correct_llm)

    for ans in [
        "数列极限",
        "因为有界且单调，所以收敛",
        "我想再试试更难的，比如 ε-δ 定义的具体例子",
    ]:
        engine.respond(ctx.session_id, answer=ans)
        # 复位到 CHECK 才能再触发 respond
        c2 = sessions.load(ctx.session_id)
        if c2.current_strategy_state != "CHECK":
            c2.current_strategy_state = "CHECK"
            sessions.save(c2)

    final = sessions.load(ctx.session_id)
    last_flow = final.recent_history[-1].get("flow_level")
    assert last_flow is not None
    # 应高于 SILENT
    assert int(last_flow) >= int(FlowLevel.SHALLOW)


def test_withdrawal_triggers_gain_loop_repair(engine_env) -> None:
    """连续 3 轮极短答案 → 回路检测到 student_withdrawal → next_action 是 break_suggestion。"""
    from servers.tutoring_mcp.engine import TeachingEngine

    db, sessions, ctx, llm = engine_env
    # 用 LLM 判 incorrect
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    short_answers = ["嗯", "不会", "..."]
    last_result = None
    for ans in short_answers:
        last_result = engine.respond(ctx.session_id, answer=ans)
        c = sessions.load(ctx.session_id)
        # 强制把 strategy 状态拨回 CHECK 让下一轮也能 respond
        if c.current_strategy_state != "CHECK":
            c.current_strategy_state = "CHECK"
            sessions.save(c)

    # 第 3 轮后应触发回路修复
    assert last_result is not None
    assert (
        last_result.next_action is not None
        and last_result.next_action.type == "break_suggestion"
    )


def test_recent_history_capped_at_max(engine_env) -> None:
    """recent_history 不应无限增长（≤ 20 条）。"""
    from servers.tutoring_mcp.engine import TeachingEngine

    db, sessions, ctx, llm = engine_env
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    for i in range(25):
        engine.respond(ctx.session_id, answer=f"answer {i}")
        c = sessions.load(ctx.session_id)
        if c.current_strategy_state != "CHECK":
            c.current_strategy_state = "CHECK"
            sessions.save(c)

    final = sessions.load(ctx.session_id)
    assert len(final.recent_history) <= 20


# ------------------- FIX-F：连续学习时长 → 休息建议（#10） ------------------- #
# 答案掺因果词（因为/所以）保持正向心流信号，避免 detect_break 的
# 情绪平/退场分支抢占优先级，专测墙钟触发。


def test_long_streak_triggers_break_suggestion(engine_env) -> None:
    """连续学习 ≥50 分钟 → respond 主动插入休息建议（无须答错任何题）。"""
    from datetime import timedelta

    from freezegun import freeze_time

    from servers.tutoring_mcp.engine import TeachingEngine

    db, sessions, ctx, llm = engine_env
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    triggers: list[str | None] = []
    with freeze_time("2026-06-12 10:00:00") as frozen:
        for i in range(6):  # 每 10 分钟一轮，第 6 轮时连续时长达 50 分钟
            r = engine.respond(
                ctx.session_id,
                answer=f"因为词频统计是核心，所以第{i}轮我认为定义成立",
            )
            triggers.append(
                (r.next_action.metadata or {}).get("trigger") if r.next_action else None
            )
            frozen.tick(timedelta(minutes=10))

    assert "study_streak" in triggers
    reloaded = sessions.load(ctx.session_id)
    assert reloaded.meta.last_break_suggested_at is not None
    assert reloaded.meta.active_time_min >= 50


def test_rest_gap_resets_streak_no_break(engine_env) -> None:
    """中途休息（间隔 >15 分钟）重置连续段——两段各 30 分钟不触发休息建议。"""
    from datetime import timedelta

    from freezegun import freeze_time

    from servers.tutoring_mcp.engine import TeachingEngine

    db, sessions, ctx, llm = engine_env
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    triggers: list[str | None] = []
    with freeze_time("2026-06-12 10:00:00") as frozen:
        for i, minutes in enumerate((10, 10, 10, 20, 10, 10, 10)):  # 第 4 步隔 20 分钟
            r = engine.respond(
                ctx.session_id,
                answer=f"因为定义包含两个要点，所以第{i}轮回答仍然成立",
            )
            triggers.append(
                (r.next_action.metadata or {}).get("trigger") if r.next_action else None
            )
            frozen.tick(timedelta(minutes=minutes))

    assert "study_streak" not in triggers
