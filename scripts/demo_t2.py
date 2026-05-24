"""Slice T2 演示：L3 长期记忆（遗忘曲线 + 复习调度）。

展示:
1. 模拟多日学习：让某些 concept 在不同时间被复习 N 次，accuracy 不一
2. 拟合个性化遗忘曲线 → 看 λ 是否在合理范围
3. 调 learning_insight tool → 看跨会话聚合的洞察报告
4. 调 generate_review_plan tool → 按 30 min 预算给出今日复习清单

用法:
    uv run python scripts/demo_t2.py "<你的-md>"
    uv run python scripts/demo_t2.py "<md>" --mock
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import load_env
from shared.llm_cache import CachedLLMProvider
from shared.llm_client import LLMProvider, MockLLMProvider
from shared.logging_config import configure_logging
from shared.providers.deepseek import DeepSeekProvider
from shared.storage import RelationalStore


def section(t: str) -> None:
    print(f"\n{'─' * 60}\n{t}\n{'─' * 60}")


def _canned(rng: random.Random, name: str) -> str:
    return json.dumps({
        "definition": f"{name}（Mock）",
        "confidence": round(rng.uniform(0.6, 0.95), 2),
    }, ensure_ascii=False)


def _make_llm(use_mock: bool, n: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds), f"DeepSeek({ds.model})"
    rng = random.Random(42)
    return (
        MockLLMProvider(canned_responses=[_canned(rng, f"c{i}") for i in range(n + 10)]),
        "Mock",
    )


def main(md_path: Path, use_mock: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    USER_ID, SUBJECT_ID = "yhn", "demo-t2-ml"
    from shared.models import Subject, User
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="T2 demo"))
        s.commit()

    # ---- ① 建 KG ----
    section("① 建 KG (depth=concept)")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    from shared.storage import FileStore

    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="demo-t2-ml", version="t2",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID, file_store=fs, db=db,
    )
    md_corpus = Path(manifest.file_paths["markdown"])
    skeleton, _ = _build_toc(subject_slug="demo-t2-ml", markdown_path=md_corpus)
    llm, label = _make_llm(use_mock, len(skeleton))
    print(f"provider = {label} · concepts = {len(skeleton)}")

    kg_result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="demo-t2-ml",
        markdown_path=md_corpus, db=db,
    )
    with db.session() as s:
        s.get(Subject, SUBJECT_ID).kg_id = kg_result.kg_id
        s.commit()

    # ---- ② 模拟多日学习记录 ----
    section("② 模拟 14 天学习历史（注入 review_history）")
    from servers.tutoring_mcp.memory_store import MemoryStore
    from servers.tutoring_mcp.bkt_store import BKTStore
    from shared.schemas import BKTParams
    from shared.models import ConceptRow

    with db.session() as s:
        concepts = (
            s.query(ConceptRow)
            .filter_by(kg_id=kg_result.kg_id)
            .order_by(ConceptRow.id)
            .limit(5)
            .all()
        )
        concept_ids = [c.id for c in concepts]
        concept_names = {c.id: c.name_primary for c in concepts}

    mem = MemoryStore(db)
    bkt = BKTStore(db)
    now = datetime.utcnow()

    # 给前 5 个 concept 不同的学习曲线
    profiles = [
        # (concept_idx, [(days_ago, accuracy), ...], final_mastery)
        (0, [(14, 0.4), (10, 0.6), (7, 0.75), (3, 0.85), (1, 0.9)], 0.92),   # 复习稳定
        (1, [(12, 0.6), (8, 0.7), (4, 0.8)], 0.78),                            # 不错但久未复习
        (2, [(10, 0.5), (5, 0.4), (1, 0.3)], 0.32),                            # 一直困难
        (3, [(8, 0.85)], 0.85),                                                # 一次学得很好但单次
        (4, [], 0.55),                                                          # 没记录
    ]
    for idx, samples, mastery in profiles:
        if idx >= len(concept_ids):
            continue
        cid = concept_ids[idx]
        bkt.save(USER_ID, BKTParams(concept_id=cid, p_mastery=mastery, n_observations=len(samples)))
        for days_ago, acc in samples:
            err_types = ["concept_confusion"] if acc < 0.4 else None
            mem.record_review(
                user_id=USER_ID, concept_id=cid, subject_id=SUBJECT_ID,
                accuracy=acc, review_mode="quick_quiz" if acc > 0.7 else "teach_back",
                review_date=now - timedelta(days=days_ago),
                error_types=err_types,
            )

    # ---- ③ 看遗忘曲线拟合结果 ----
    section("③ 个性化遗忘曲线（λ 和 next_review_at）")
    print(f"{'概念':28s}  λ      R²    n_pts  下次复习")
    for cid in concept_ids:
        curve = mem.load_curve(user_id=USER_ID, concept_id=cid)
        name = concept_names.get(cid, cid)[:24]
        r2 = f"{curve.r_squared:.2f}" if curve.r_squared is not None else "  -  "
        next_at = curve.next_review_at.strftime("%m-%d %H:%M") if curve.next_review_at else "  - "
        print(f"  {name:24s}  {curve.lambda_param:.3f}  {r2}   {curve.n_data_points:3d}    {next_at}")

    # ---- ④ learning_insight tool ----
    section("④ learning_insight 跨会话聚合报告")
    from servers.tutoring_mcp import server as tserver
    fn = getattr(tserver.learning_insight, "fn", tserver.learning_insight)
    insight = asyncio.run(fn(user_id=USER_ID, subject_id=SUBJECT_ID))
    print(f"overall_mastery     = {insight.overall_mastery:.3f}")
    print(f"concepts_mastered   = {insight.concepts_mastered}  (mastery > 0.85)")
    print(f"concepts_learning   = {insight.concepts_learning}  (0.4 < m <= 0.85)")
    print(f"strengths           = {insight.strengths}")
    print(f"\nweaknesses ({len(insight.weaknesses)}):")
    for w in insight.weaknesses:
        print(f"  [{w['mastery']:.2f}] {w['name']:28s}  root_cause: {w['root_cause'][:50]}")
    print(f"\nrecommended_focus   = {insight.recommended_focus}")
    print(f"next_review_plan    = {insight.next_review_plan}")

    # ---- ⑤ generate_review_plan tool ----
    section("⑤ generate_review_plan (30 分钟预算)")
    fn2 = getattr(tserver.generate_review_plan, "fn", tserver.generate_review_plan)
    plan = asyncio.run(fn2(user_id=USER_ID, subject_id=SUBJECT_ID, available_time_today_min=30))
    print(f"date              = {plan.date}")
    print(f"total_estimated   = {plan.total_estimated_min} min")
    print(f"sections ({len(plan.sections)}):")
    for sec in plan.sections:
        name = concept_names.get(sec.concept_id, sec.concept_id)[:24]
        print(f"  [{sec.priority:5.2f}] {name:24s} "
              f"recall={sec.predicted_recall*100:3.0f}%  "
              f"{sec.estimated_minutes:2d}min  {sec.review_mode}")
        print(f"           {sec.urgency_context}")
    if plan.tips:
        print(f"\ntips:")
        for t in plan.tips:
            print(f"  - {t}")

    print(f"\n[OK] Slice T2 demo 完成。provider = {label}")


if __name__ == "__main__":
    args = sys.argv[1:]
    use_mock = "--mock" in args
    args = [a for a in args if a != "--mock"]
    md_arg = args[0] if args else None
    md_path = (
        Path(md_arg) if md_arg
        else Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "mini_subject.md"
    )
    if not md_path.exists():
        sys.exit(f"markdown 文件不存在: {md_path}")
    main(md_path, use_mock=use_mock)
