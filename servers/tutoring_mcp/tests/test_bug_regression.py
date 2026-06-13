"""code-review 出 4 个高严重 bug 的回归测试。

BUG.1 engine.py:95   attempt_count 永远是 0 → FLAG_DIFFICULT 不可达
BUG.2 engine.py:331  errors_by_type['avoidance'] 永不存在 → avoidance_pattern 不可达
BUG.3 kg_update._clone_kg full_json 保留 base id → versioned 质量报告全部 isolated
BUG.4 obsidian_watch.watch() utcnow vs local mtime 时区错位

这些测试是 RED → 修复后 GREEN → 不允许再回退。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import (
    ConceptRow as ConceptRowORM,
)
from shared.models import (
    KnowledgeGraphRow,
    Subject,
    User,
)
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich() -> str:
    return json.dumps({"definition": "x", "confidence": 0.85}, ensure_ascii=False)


def _score(corr: str) -> str:
    return json.dumps({"correctness": corr, "raw_score": 0.1, "evidence": "fail"}, ensure_ascii=False)


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
        first_id = (
            s.query(ConceptRowORM).filter_by(kg_id=r.kg_id)
            .order_by(ConceptRowORM.id).first().id
        )
    return tmp_db, "ml", first_id, r.kg_id


# --------------------------------------------------------------------------- #
# BUG.1 — attempt_count 永远是 0
# --------------------------------------------------------------------------- #


def test_bug1_repeated_incorrect_should_reach_flag_difficult(engine_env) -> None:
    """连续 incorrect 应在 max_attempts=2 后触发 FLAG_DIFFICULT。

    旧 bug：每次 respond 都新建 strategy 且 attempt_count 死代码 reset 为 0，
    永远到不了 2 次 → strategy_state 永远在 EXPLAIN。
    """
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_id, _ = engine_env
    sessions = SessionStore(db)
    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_id
    ctx.status = "active"
    ctx.current_strategy = "reduction"
    ctx.current_strategy_state = "CHECK"
    sessions.save(ctx)

    # MockLLM 总判 incorrect
    incorrect_llm = MockLLMProvider(canned_responses=[
        _score("incorrect") for _ in range(20)
    ])
    engine = TeachingEngine(db=db, sessions=sessions, llm=incorrect_llm)

    # Round 1: CHECK → EXPLAIN（attempt=1）
    engine.respond(ctx.session_id, answer="错答 1")
    c = sessions.load(ctx.session_id)
    assert c.current_strategy_state == "EXPLAIN"

    # 推到下一轮 CHECK
    engine.transition_event(ctx.session_id, event="explain_done", payload={})
    c = sessions.load(ctx.session_id)
    assert c.current_strategy_state == "CHECK"

    # Round 2: CHECK → 期望 FLAG_DIFFICULT（attempt 应到 2）
    engine.respond(ctx.session_id, answer="错答 2")
    c = sessions.load(ctx.session_id)
    assert c.current_strategy_state == "FLAG_DIFFICULT", (
        f"应在第 2 次 incorrect 后 FLAG_DIFFICULT，实际 {c.current_strategy_state}"
    )


# --------------------------------------------------------------------------- #
# BUG.2 — avoidance_pattern 不可达
# --------------------------------------------------------------------------- #


def test_bug2_skipping_concepts_triggers_avoidance_pattern(engine_env) -> None:
    """学生连续 3 次"跳过/换主题"应触发 avoidance_pattern 修复。

    旧 bug：detect_break 读 errors_by_type['avoidance']，但这个 key 永远不写。
    """
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    db, subject_id, first_id, _ = engine_env
    sessions = SessionStore(db)
    ctx = sessions.create(user_id="yhn", subject_id=subject_id)
    ctx.current_concept_id = first_id
    ctx.status = "active"
    sessions.save(ctx)

    # mock LLM 把 question 分类为 pace_complaint with suggested_action='change_topic'
    pace_resp = json.dumps({"intent": "pace_complaint", "confidence": 0.9, "evidence": "skip"}, ensure_ascii=False)
    llm = MockLLMProvider(canned_responses=[pace_resp, pace_resp, pace_resp, _score("incorrect")])
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    # 3 次跳过
    for _ in range(3):
        engine.handle_interrupt(ctx.session_id, question="太慢了，跳过吧")
        c = sessions.load(ctx.session_id)
        c.status = "active"  # interrupt 把它改成 'interrupted'，下一轮要重置
        sessions.save(c)

    # 此后再答错一次，detect_break 应能看到 skipped_count >= 3
    result = engine.respond(ctx.session_id, answer="还是不会")
    assert result.next_action is not None, "应触发回路修复"
    assert result.next_action.metadata.get("break_type") == "avoidance_pattern", (
        f"应是 avoidance_pattern，实际 {result.next_action.metadata}"
    )


# --------------------------------------------------------------------------- #
# BUG.3 — versioned _clone_kg 的 full_json["id"] 未更新
# --------------------------------------------------------------------------- #


def test_bug3_versioned_clone_does_not_misreport_all_isolated(engine_env) -> None:
    """versioned 模式 clone 后，quality 报告的 isolated_nodes 必须基于 ORM
    id 空间正确计算，而不是 base-id 全集（导致 100% 误报）。

    旧 bug：_compute_quality 比较 Concept.id (base) vs Relation 端点 (@v 后缀)，
    两套 id 不交，全部概念误判为 isolated。修复后：versioned 模式末尾用 ORM
    id 重算 isolated 覆盖到 quality_json。
    """
    from servers.knowledge_mcp.kg_update import update_kg
    from shared.schemas import KgEditAction

    db, subject_id, first_id, kg_id = engine_env

    # 父 KG 的 isolated_nodes（基线）
    with db.session() as s:
        parent_kg = s.get(KnowledgeGraphRow, kg_id)
        parent_isolated = (parent_kg.quality_json or {}).get("isolated_nodes", 0)
        parent_count = parent_kg.node_count

    result = update_kg(
        db=db, kg_id=kg_id,
        actions=[KgEditAction(op="approve_all")],
        mode="versioned",
    )
    new_kg_id = result.kg_id
    assert new_kg_id != kg_id

    with db.session() as s:
        kg_row = s.get(KnowledgeGraphRow, new_kg_id)
        q = kg_row.quality_json or {}
        new_isolated = q.get("isolated_nodes", -1)
        # 关键不变量：versioned KG 的 isolated 数应等于父 KG 的（结构未变）
        assert new_isolated == parent_isolated, (
            f"clone 不应改变 isolated 数：父={parent_isolated} 子={new_isolated}"
        )
        # 而绝不应等于 node_count（100% 误报）
        assert new_isolated < kg_row.node_count or parent_count == parent_isolated, (
            f"全部节点都被误判为 isolated：{q}（应 == 父 {parent_isolated}）"
        )


# --------------------------------------------------------------------------- #
# BUG.4 — watch() 时区错位
# --------------------------------------------------------------------------- #


def test_bug6_merge_concepts_syncs_full_json(engine_env) -> None:
    """merge_concepts 后 tgt_row.full_json['names'] 应包含 src 的别名，
    name_primary 应保持非空；否则下游 Concept.model_validate(full_json) 拿不到。
    """
    from servers.knowledge_mcp.kg_update import update_kg
    from shared.schemas import KgEditAction

    db, _, _, kg_id = engine_env
    with db.session() as s:
        rows = s.query(ConceptRowORM).filter_by(kg_id=kg_id).limit(2).all()
        if len(rows) < 2:
            pytest.skip("KG 不足 2 个 concept，无法测 merge")
        src_id, tgt_id = rows[0].id, rows[1].id
        src_name = rows[0].name_primary
        tgt_name = rows[1].name_primary

    # 注意 schema: source = concept_id, target = merge_target_id
    update_kg(
        db=db, kg_id=kg_id,
        actions=[KgEditAction(op="merge_concepts", concept_id=src_id, merge_target_id=tgt_id)],
        mode="in_place",
    )
    with db.session() as s:
        merged = s.get(ConceptRowORM, tgt_id)
        assert merged is not None
        # full_json 必须同步：包含 src 的别名
        full_names = (merged.full_json or {}).get("names", [])
        assert src_name in full_names, (
            f"merge 后 full_json['names']={full_names} 应包含 src 的 '{src_name}'"
        )
        assert merged.name_primary, "name_primary 不应为空"


def test_bug7_concept_question_beats_prereq_when_both_keywords_present() -> None:
    """复合句 '为什么不会用这个公式' 应分为 concept_question（重心是 '为什么'），
    而不是 prereq_gap（被 '不会' 误命中）。
    """
    from servers.tutoring_mcp.intent_classifier import _heuristic_classify

    r = _heuristic_classify("为什么不会用这个公式？")
    assert r.intent == "concept_question", (
        f"复合问应优先 concept_question，实际 {r.intent}（evidence: {r.evidence}）"
    )
    # 单独 "不懂" 仍走 prereq_gap
    r2 = _heuristic_classify("我连基础都不懂")
    assert r2.intent == "prereq_gap"


def test_bug5_student_withdrawal_takes_priority_over_surface(engine_env=None) -> None:
    """同时具备 withdrawal_pattern + emotional_flatness + help_seeking_spike 时，
    应按 spec 优先级命中 student_withdrawal（含 emotional_flatness 的"退场"信号
    比 help_seeking 的"求助"信号更紧迫；docstring 明确 withdrawal #2、surface #3）。

    旧 bug：代码顺序倒置，surface_responses 先命中。
    """
    from servers.tutoring_mcp.gain_loop_monitor import detect_break
    from shared.schemas import FlowSignals

    signals = FlowSignals(
        withdrawal_pattern=True,
        emotional_flatness=True,
        help_seeking_spike=True,  # 同时有
    )
    brk = detect_break(signals=signals, recent_skipped_count=0)
    assert brk is not None
    assert brk.type == "student_withdrawal", (
        f"docstring 优先级要求 withdrawal > surface，实际命中 {brk.type}"
    )


def test_bug4_watch_initial_last_ts_matches_mtime_timezone(tmp_path: Path) -> None:
    """watch() 的 last_ts 应与 poll_changes 内 mtime（local fromtimestamp）使用
    相同的"时间起点"语义，不应有时区错位。

    用一次 poll_changes(since_ts=watch_internal_last_ts) 在静止 vault 上必须返回 [].
    """
    from servers.sync_mcp.obsidian_watch import _now_ref, poll_changes

    vault = tmp_path / "vault"
    vault.mkdir()
    # 写一个 ml 文件并把 mtime 拨到 1 秒前
    f = vault / "ml-old.md"
    f.write_text("x", encoding="utf-8")
    import os
    one_sec_ago = (_now_ref()).timestamp() - 1.0
    os.utime(f, (one_sec_ago, one_sec_ago))

    # watch 的"现在"参考时间
    last_ts = _now_ref()
    # vault 没新变化 → poll_changes(since=last_ts) 应返回 []
    changes = poll_changes(vault_path=vault, subject_id="ml", since_ts=last_ts)
    assert changes == [], (
        f"watch 的 last_ts 与 poll 的 mtime 时区不一致：返回了 {len(changes)} 个伪变更"
    )
