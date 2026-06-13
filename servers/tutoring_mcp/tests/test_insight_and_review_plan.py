"""learning_insight + generate_review_plan tool 真实实现契约测试。

learning_insight(user_id, subject_id) → InsightReport:
- overall_mastery, concepts_mastered/learning/unknown
- strengths (mastery > 0.85)
- weaknesses (mastery < 0.4 + 错误类型)
- recommended_focus (next plan 中概念名)
- next_review_plan: dict mode → [concept_id]

generate_review_plan(user_id, subject_id, available_time_today_min) → DailyReviewPlan:
- 调 ReviewScheduler
- 写入 review_plans 表（持久化）
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import (
    Subject,
    User,
)
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich(c: float = 0.85) -> str:
    return json.dumps({"definition": "x", "confidence": c}, ensure_ascii=False)


@pytest.fixture
def kg_and_records(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.tutoring_mcp.memory_store import MemoryStore

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
        subj = s.get(Subject, "ml")
        subj.kg_id = r.kg_id
        s.commit()

    # fixture 是高数笔记，真实 concept id 由 toc 抽取生成
    # 取前 3 个 concept 当测试样本
    from shared.models import ConceptRow
    with tmp_db.session() as s:
        rows = (
            s.query(ConceptRow)
            .filter_by(kg_id=r.kg_id)
            .order_by(ConceptRow.id)
            .all()
        )
        # 找一个 chapter 1 root、一个 sub、一个 sub-sub
        first_root = next((c for c in rows if c.id.count(":") == 2 and "." not in c.id.split(":")[1]), rows[0])
        first_sub = next((c for c in rows if "." in c.id.split(":")[1] and c.id.split(":")[1].count(".") == 1), rows[1])
        first_subsub = next((c for c in rows if c.id.split(":")[1].count(".") >= 2), rows[2])

    # 写 BKT
    from servers.tutoring_mcp.bkt_store import BKTStore
    from shared.schemas import BKTParams
    bkt = BKTStore(tmp_db)
    bkt.save("yhn", BKTParams(concept_id=first_root.id, p_mastery=0.92, n_observations=10))
    bkt.save("yhn", BKTParams(concept_id=first_sub.id, p_mastery=0.75, n_observations=5))
    bkt.save("yhn", BKTParams(concept_id=first_subsub.id, p_mastery=0.30, n_observations=3))

    # review history
    mem = MemoryStore(tmp_db)
    long_ago = datetime.utcnow() - timedelta(days=10)
    mem.record_review(
        user_id="yhn", concept_id=first_subsub.id,
        subject_id="ml", accuracy=0.3, review_mode="teach_back",
        review_date=long_ago, error_types=["concept_confusion"],
    )
    return tmp_db, r.kg_id, first_root.id, first_subsub.id


def test_insight_aggregates_bkt_mastery(kg_and_records) -> None:
    from servers.tutoring_mcp.insight import build_insight

    db, _, _root_id, _weak_id = kg_and_records
    insight = build_insight(db=db, user_id="yhn", subject_id="ml")
    assert insight.overall_mastery >= 0.0
    assert insight.concepts_mastered >= 1  # 92% 那个
    assert insight.concepts_learning >= 1  # 75% 那个


def test_insight_identifies_strengths(kg_and_records) -> None:
    from servers.tutoring_mcp.insight import build_insight

    db, _, root_id, _ = kg_and_records
    insight = build_insight(db=db, user_id="yhn", subject_id="ml")
    assert insight.strengths
    # root concept 是 92% mastery → 应在 strengths 里
    from shared.models import ConceptRow
    with db.session() as s:
        root_row = s.get(ConceptRow, root_id)
    assert root_row.name_primary in insight.strengths


def test_insight_identifies_weaknesses_with_root_cause(kg_and_records) -> None:
    from servers.tutoring_mcp.insight import build_insight

    db, _, _root, weak_id = kg_and_records
    insight = build_insight(db=db, user_id="yhn", subject_id="ml")
    assert insight.weaknesses
    weak_ids = [w.get("concept") for w in insight.weaknesses]
    assert weak_id in weak_ids
    # 错误类型应该体现
    weak_entry = next(w for w in insight.weaknesses if w["concept"] == weak_id)
    assert "concept_confusion" in weak_entry["root_cause"]


def test_insight_unknown_user_or_subject(tmp_db: RelationalStore) -> None:
    """完全空数据 → 返回合法但都是 0 的 InsightReport。"""
    from servers.tutoring_mcp.insight import build_insight

    with tmp_db.session() as s:
        s.add(User(id="ghost"))
        s.commit()
    insight = build_insight(db=tmp_db, user_id="ghost", subject_id="no-such")
    assert insight.overall_mastery == 0.0
    assert insight.concepts_mastered == 0


@pytest.mark.asyncio
async def test_learning_insight_tool_no_longer_stub(kg_and_records) -> None:
    """server.learning_insight 不再 raise DEPENDENCY_MISSING。"""
    from servers.tutoring_mcp import server as srv

    db, _, _root_id, _weak_id = kg_and_records
    # 注入 db 路径让 server 用同一个
    import os
    os.environ["DATABASE_URL"] = db.url
    fn = getattr(srv.learning_insight, "fn", srv.learning_insight)
    insight = await fn(user_id="yhn", subject_id="ml")
    assert insight.overall_mastery >= 0.0
    assert isinstance(insight.strengths, list)
    assert isinstance(insight.weaknesses, list)


def test_generate_review_plan_returns_plan(kg_and_records) -> None:
    """generate_review_plan tool 调通且返回 DailyReviewPlan。"""
    from servers.tutoring_mcp.memory_store import MemoryStore

    db, _, _root_id, _weak_id = kg_and_records
    # 让稀疏向量超期
    mem = MemoryStore(db)
    long_ago = datetime.utcnow() - timedelta(days=14)
    mem.record_review(
        user_id="yhn", concept_id="ml:1.1:yongfa", subject_id="ml",
        accuracy=0.6, review_mode="quick_quiz", review_date=long_ago,
    )

    from servers.tutoring_mcp.review_scheduler import schedule_review_plan
    plan = schedule_review_plan(
        db=db, user_id="yhn", subject_id="ml", available_minutes=30,
    )
    assert plan.user_id == "yhn"
    assert plan.subject_id == "ml"
    assert plan.total_estimated_min <= 30


@pytest.mark.asyncio
async def test_generate_review_plan_tool_no_longer_stub(kg_and_records) -> None:
    from servers.tutoring_mcp import server as srv
    from servers.tutoring_mcp.memory_store import MemoryStore

    db, _, _root_id, _weak_id = kg_and_records
    # 添加一个 due 的复习
    mem = MemoryStore(db)
    mem.record_review(
        user_id="yhn", concept_id="ml:1.2:xishuxiangliang_sparse_vector",
        subject_id="ml", accuracy=0.4, review_mode="teach_back",
        review_date=datetime.utcnow() - timedelta(days=8),
    )

    import os
    os.environ["DATABASE_URL"] = db.url
    fn = getattr(srv.generate_review_plan, "fn", srv.generate_review_plan)
    plan = await fn(user_id="yhn", subject_id="ml", available_time_today_min=20)
    assert plan.user_id == "yhn"
    assert isinstance(plan.sections, list)
