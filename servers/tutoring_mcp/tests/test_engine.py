"""TeachingEngine 决策循环契约测试。

Engine 职责（spine v2 范围）:
- next_action(session_id): 加载 session → 选 strategy → strategy.get_action() → 返回
- respond(session_id, answer):
    * 启发式判分（spine: 含关键词→correct，否则 incorrect；真实 NLP 在 Slice T1）
    * 触发 strategy.transition()
    * 通过 BKTStore.record_observation 更新掌握度
    * 反馈先过 NonJudgmentFirewall，违规则回退到安全模板
    * 返回 ResponseResult，含 mastery_update

后续切片:
- 策略选择决策树（spec §teaching-strategy-formalism §策略选择决策树）
- L5 错误诊断
- L3 复习节点插入
- L6 完整 state machine（CHECK / FLAG_DIFFICULT / 等）
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.models import ConceptRow as ConceptRowORM
from shared.models import Subject, User
from shared.schemas import ResponseResult, TeachingAction
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


@pytest.fixture
def db_with_kg(tmp_db: RelationalStore, tmp_filestore) -> tuple[RelationalStore, str, str]:
    """建用户 + 科目 + 跑 fixture 的 toc KG → 返回 (db, subject_id, first_concept_id)。"""
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import TocKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ce-shi", user_id="yhn", display_name="测试"))
        s.commit()

    manifest, corpus_id = acquire(
        subject="测试",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=tmp_db,
    )
    result = TocKGBuilder().build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]),
        db=tmp_db,
    )
    # 取第一个 concept id
    with tmp_db.session() as s:
        first = s.query(ConceptRowORM).filter_by(kg_id=result.kg_id).first()
        assert first is not None
        first_id = first.id
    return tmp_db, "ce-shi", first_id


def test_next_action_returns_teaching_action(db_with_kg) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept = db_with_kg
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    action = engine.next_action(ctx.session_id)
    assert isinstance(action, TeachingAction)
    assert action.content
    assert action.type in {
        "explain", "ask_question", "show_example", "give_exercise",
        "request_explanation", "provide_hint", "reveal_answer",
        "review", "checkpoint", "break_suggestion", "reflection",
    }


def test_respond_correct_updates_bkt_upward(db_with_kg) -> None:
    from servers.tutoring_mcp.bkt_store import BKTStore
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept = db_with_kg
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)
    bkt = BKTStore(db)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    before = bkt.load("yhn", first_concept).p_mastery
    # 调用 engine.next_action 让 strategy 进入"问问题"状态再 respond
    _ = engine.next_action(ctx.session_id)

    result = engine.respond(ctx.session_id, answer="极限就是数列无限接近一个值")
    assert isinstance(result, ResponseResult)
    after = bkt.load("yhn", first_concept).p_mastery
    if result.correctness == "correct":
        assert after > before
    # 任何情况都至少写过一次 BKT
    assert bkt.load("yhn", first_concept).n_observations >= 1


def test_respond_increments_session_stats(db_with_kg) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept = db_with_kg
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    engine.next_action(ctx.session_id)
    engine.respond(ctx.session_id, answer="任何答案")

    reloaded = sessions.load(ctx.session_id)
    assert reloaded.session_stats.total_questions_asked >= 1


def test_respond_strips_firewall_violations_from_feedback(db_with_kg) -> None:
    """如果 strategy 反馈带了禁词，最终 ResponseResult.feedback 不能含禁词。"""
    from unittest.mock import patch

    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_concept = db_with_kg
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_concept
    ctx.status = "active"
    sessions.save(ctx)

    engine.next_action(ctx.session_id)

    # 注入一段会被防火墙拦截的反馈
    with patch.object(engine, "_build_raw_feedback", return_value="你错了，太棒了！"):
        result = engine.respond(ctx.session_id, answer="...")

    assert "你错了" not in result.feedback
    assert "太棒了" not in result.feedback
    # 必须有替代措辞
    assert result.feedback.strip()


def test_next_action_without_current_concept_raises(db_with_kg) -> None:
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore
    from shared.errors import TutorError

    db, subject_id, _first_concept = db_with_kg
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions)

    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    # 故意不设 current_concept_id

    with pytest.raises(TutorError) as exc:
        engine.next_action(ctx.session_id)
    assert exc.value.code in ("KG_NOT_FOUND", "DEPENDENCY_MISSING", "SESSION_NOT_FOUND")
