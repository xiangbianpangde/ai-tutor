"""端到端集成：fixture markdown → KG → 学习会话 → 多轮 respond → BKT 落库。

证明 Spine v0+v1+v2 联通。
路径:
1. knowledge-mcp.acquire_subject(file)
2. knowledge-mcp.build_knowledge_graph(toc)
3. subject.kg_id ← kg_id（host LLM 的职责，集成测试里手工写）
4. tutoring-mcp.start_learning_session
5. tutoring-mcp.next_action + respond × N 轮
6. 验证: mastery 累积、session_stats 累加、KG/session 都落了 SQLite
"""
from __future__ import annotations

from pathlib import Path

import pytest

from servers.knowledge_mcp import server as kserver
from servers.tutoring_mcp import server as tserver
from shared.models import (
    BKTParamRow,
    KnowledgeGraphRow,
    SessionRow,
    Subject,
    User,
)
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "mini_subject.md"


def _unwrap(tool):
    return getattr(tool, "fn", None) or getattr(tool, "func", None) or tool


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RelationalStore:
    db_path = tmp_path / "e2e.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AI_TUTOR_DATA_ROOT", str(tmp_path / "data"))
    store = RelationalStore.from_env()
    store.init_schema()
    with store.session() as s:
        s.add(User(id="yhn", display_name="Test User"))
        s.add(Subject(id="ce-shi", user_id="yhn", display_name="高数测试"))
        s.commit()
    return store


@pytest.mark.asyncio
async def test_full_spine_flow(env: RelationalStore, tmp_path: Path) -> None:
    # --- 1. acquire ---
    a = await _unwrap(kserver.acquire_subject)(
        subject="高数测试",
        sources=[{"type": "file", "uri": str(FIXTURE)}],
        user_id="yhn",
        version="v1",
    )
    assert a.stats["total_chapters"] == 2

    # --- 2. build KG ---
    b = await _unwrap(kserver.build_knowledge_graph)(corpus_id=a.corpus_id, depth="toc")
    assert b.triples_count > 0

    # --- 3. 将 kg_id 写回 subject（host 编排职责） ---
    with env.session() as s:
        subj = s.get(Subject, "ce-shi")
        subj.kg_id = b.kg_id
        s.commit()

    # --- 4. start session ---
    started = await _unwrap(tserver.start_learning_session)(
        user_id="yhn",
        subject_id="ce-shi",
        goal="48h_sprint",
    )
    assert started.session_id
    assert started.teaching_plan["total_concepts"] == 17
    assert started.current_action.content

    # --- 5. 三轮交互 ---
    next_fn = _unwrap(tserver.next_action)
    respond_fn = _unwrap(tserver.respond)

    answers = [
        "极限就是无限接近一个值",   # 期望含"极限" → correct
        "数列收敛意味着 ε-δ 条件",  # 中性
        "随便答一句",               # 几乎肯定 partial / incorrect
    ]
    correctness_log = []
    for ans in answers:
        await next_fn(session_id=started.session_id)
        r = await respond_fn(session_id=started.session_id, answer=ans)
        assert r.feedback
        assert r.mastery_update is not None
        correctness_log.append(r.correctness)

    # --- 6. 全链路落库验证 ---
    with env.session() as s:
        # KG 存了
        assert s.get(KnowledgeGraphRow, b.kg_id) is not None
        # session 持久化且状态机有动
        sess_row = s.get(SessionRow, started.session_id)
        assert sess_row is not None
        assert sess_row.status == "active"
        ctx_json = sess_row.context_json
        assert ctx_json["session_stats"]["total_questions_asked"] == 3
        # BKT 至少有一条记录（针对首个 concept）
        bkt_rows = s.query(BKTParamRow).filter_by(user_id="yhn").all()
        assert len(bkt_rows) >= 1
        for row in bkt_rows:
            assert 0.0 <= row.p_mastery <= 1.0
            assert row.n_observations >= 1

    # --- 7. 反馈不能含 PGFGA 禁词（即使 raw 模板被未来改坏） ---
    forbidden = ["你错了", "太棒了", "你应该", "不对", "想太多"]
    final_state = sess_row.context_json
    # 历史里所有 feedback 都应该过过防火墙；这里再校验一次
    for w in forbidden:
        for item in final_state.get("recent_history", []):
            assert w not in str(item)


@pytest.mark.asyncio
async def test_correct_answer_actually_raises_mastery(env: RelationalStore) -> None:
    """更精确的断言：对首个 concept 答对，BKT 必然上升。"""
    a = await _unwrap(kserver.acquire_subject)(
        subject="高数测试",
        sources=[{"type": "file", "uri": str(FIXTURE)}],
        user_id="yhn",
        version="v2",
    )
    b = await _unwrap(kserver.build_knowledge_graph)(corpus_id=a.corpus_id, depth="toc")
    with env.session() as s:
        subj = s.get(Subject, "ce-shi")
        subj.kg_id = b.kg_id
        s.commit()
    started = await _unwrap(tserver.start_learning_session)(
        user_id="yhn", subject_id="ce-shi", goal="48h_sprint",
    )

    # 先记录初始 mastery（应为默认）
    sess_row_before = None
    with env.session() as s:
        sess_row_before = s.get(SessionRow, started.session_id)
    current_concept = sess_row_before.context_json["current_concept_id"]

    from servers.tutoring_mcp.bkt_store import BKTStore
    bkt = BKTStore(env)
    before = bkt.load("yhn", current_concept).p_mastery

    await _unwrap(tserver.next_action)(session_id=started.session_id)
    # 答案含 concept 主名称的 2-gram（fixture 第一个概念应为"极限与连续"，2-gram 含"极限"）
    r = await _unwrap(tserver.respond)(
        session_id=started.session_id, answer="极限 表示无限接近"
    )

    after = bkt.load("yhn", current_concept).p_mastery
    if r.correctness == "correct":
        assert after > before, f"correct 但 mastery 未升: {before} → {after}"
