"""端到端 host 编排演示 — 模拟 Claude Desktop 把 5 个 MCP server 串起来用。

完整工作流:
  1. sync.pull_homework_from_obsidian      看学生最近笔记
  2. knowledge.acquire_subject (file)      摄入选中的笔记
  3. knowledge.build_knowledge_graph       建概念图（depth=concept 走 LLM）
  4. knowledge.review_kg                   挑低置信概念
  5. knowledge.update_kg                   批准（或编辑）
  6. digest(formats=[mindmap,notes,quiz])  生成多模态产物
  7. sync.push_to_obsidian                 产物回到 Obsidian vault
  8. tutoring.start_learning_session       开教学会话
  9. tutoring.next_action × N              + transition_event + respond
 10. tutoring.learning_insight             跨会话报告
 11. tutoring.generate_review_plan         今日复习计划

不真启 MCP server 子进程 — 直接调内部函数模拟 host 编排（与真实 Claude Desktop
行为等价，但更快、可调试）。

用法:
    uv run python scripts/demo_full_workflow.py [--mock] [--md "<path>"]
    --mock: 用 MockLLMProvider，免 API key 免付费
    默认 vault = ~/Documents/GitHub/xbpd_obsidian
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import datetime
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


DEFAULT_VAULT = Path(r"C:\Users\yhn\Documents\GitHub\xbpd_obsidian")
DEFAULT_MD = DEFAULT_VAULT / "07.学习笔记/大一下/机器学习/机器学习笔记/4月24日-星期四-聚类.md"


def section(n: int, t: str) -> None:
    print(f"\n{'━' * 64}\n  STEP {n:2d}  {t}\n{'━' * 64}")


def _canned_enrichment(rng: random.Random, name: str) -> str:
    return json.dumps({
        "definition": f"{name}（Mock 自动填充的定义）",
        "informal_description": f"通俗解释 {name}",
        "examples": [{"text": f"{name} 的例子", "type": "computation"}],
        "common_misconceptions": [],
        "bloom_level": "understand",
        "confidence": round(rng.uniform(0.7, 0.95), 2),
    }, ensure_ascii=False)


def _canned_score(corr: str = "correct") -> str:
    score = {"correct": 0.9, "partial": 0.55, "incorrect": 0.1}[corr]
    return json.dumps({
        "correctness": corr, "raw_score": score,
        "evidence": "Mock 判分", "suggested_remediation": "",
    }, ensure_ascii=False)


def _canned_diagnosis() -> str:
    return json.dumps({
        "error_type": "concept_confusion",
        "evidence": ["Mock 诊断证据"],
        "remediation_suggestion": "回到前置概念再看一遍",
    }, ensure_ascii=False)


def _make_llm(use_mock: bool, n_concepts: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds, max_size=512), f"DeepSeek({ds.model})"
    # Mock canned 顺序：enrichment × n + scoring/diagnosis 备用
    rng = random.Random(42)
    canned = [_canned_enrichment(rng, f"c{i}") for i in range(n_concepts + 10)]
    canned += [_canned_score("correct")] * 5
    canned += [_canned_score("partial"), _canned_diagnosis()]
    canned += [_canned_score("incorrect"), _canned_diagnosis()]
    return MockLLMProvider(canned_responses=canned), "Mock"


async def main(md_path: Path, vault: Path, use_mock: bool, dry_push: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    from shared.models import Subject, User
    USER_ID, SUBJECT_ID = "yhn", "full-demo"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID, display_name="集成 demo"))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="full-demo"))
        s.commit()

    print(f"项目根:  {Path(__file__).resolve().parent.parent}")
    print(f"笔记:    {md_path}")
    print(f"vault:   {vault}")
    print(f"dry_push: {dry_push}")

    # ────────────────────────────────────────────────────── #
    # STEP 1: sync.pull_homework_from_obsidian
    # ────────────────────────────────────────────────────── #
    section(1, "sync.pull_homework_from_obsidian  ←  扫描 vault 最近 ml 笔记")
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian
    if vault.exists():
        found = pull_homework_from_obsidian(vault_path=vault, subject_id="机器学习", limit=3)
        for h in found:
            print(f"  · {h.modified_at.strftime('%Y-%m-%d')}  {h.relative_path}")
    else:
        print(f"  (vault 不存在，跳过；继续用 --md 指定的笔记)")

    # ────────────────────────────────────────────────────── #
    # STEP 2: knowledge.acquire_subject
    # ────────────────────────────────────────────────────── #
    section(2, "knowledge.acquire_subject(file)  ←  把 md 摄入到 corpus")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from shared.storage import FileStore
    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="full-demo", version="int",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID, file_store=fs, db=db,
    )
    md_corpus = Path(manifest.file_paths["markdown"])
    print(f"  corpus_id   = {corpus_id}")
    print(f"  chapters/sec = {manifest.total_chapters}/{manifest.total_sections}")

    # ────────────────────────────────────────────────────── #
    # STEP 3: knowledge.build_knowledge_graph(concept)
    # ────────────────────────────────────────────────────── #
    section(3, "knowledge.build_knowledge_graph(depth=concept)  ←  LLM 富化")
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    skeleton, _ = _build_toc(subject_slug="full-demo", markdown_path=md_corpus)
    n = len(skeleton)
    llm, label = _make_llm(use_mock, n)
    print(f"  provider    = {label}  ({n} concepts)")

    kg_result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="full-demo",
        markdown_path=md_corpus, db=db,
    )
    print(f"  kg_id       = {kg_result.kg_id}")
    print(f"  avg conf    = {kg_result.quality_report.avg_confidence:.3f}")

    # 把 kg_id 关联到 subject
    with db.session() as s:
        s.get(Subject, SUBJECT_ID).kg_id = kg_result.kg_id
        s.commit()

    # ────────────────────────────────────────────────────── #
    # STEP 4-5: knowledge.review_kg + update_kg
    # ────────────────────────────────────────────────────── #
    section(4, "knowledge.review_kg(quick)  ←  挑低置信概念")
    from servers.knowledge_mcp.kg_review import review_kg
    rv = review_kg(db=db, kg_id=kg_result.kg_id, mode="quick", limit=3)
    print(f"  低置信概念 ({len(rv.low_confidence_concepts)}):")
    for c in rv.low_confidence_concepts:
        print(f"    [{c.confidence:.2f}] {c.name}")

    section(5, "knowledge.update_kg  ←  批准全部（host 可在此让用户编辑）")
    from servers.knowledge_mcp.kg_update import update_kg
    from shared.schemas import KgEditAction
    upd = update_kg(db=db, kg_id=kg_result.kg_id, actions=[KgEditAction(op="approve_all")])
    print(f"  applied={upd.applied}  failed={upd.failed}")

    # ────────────────────────────────────────────────────── #
    # STEP 6: digest
    # ────────────────────────────────────────────────────── #
    section(6, "digest(formats=[mindmap,notes,quiz])  ←  多模态产物")
    from servers.digest_mcp.orchestrator import digest
    out_dir = (Path("data/output/digest") / kg_result.kg_id).resolve()
    run = digest(
        db=db, kg_id=kg_result.kg_id, out_dir=out_dir,
        formats=["mindmap", "notes", "quiz"],
    )
    for a in run.artifacts:
        size = a.size_bytes / 1024
        name = Path(a.uri.replace("file:///", "")).name
        print(f"  [{a.mime_type:24s}] {size:5.1f} KB  {name}")
    if run.warnings:
        for w in run.warnings:
            print(f"  ⚠ {w}")

    # ────────────────────────────────────────────────────── #
    # STEP 7: sync.push_to_obsidian
    # ────────────────────────────────────────────────────── #
    section(7, "sync.push_to_obsidian  ←  产物回到 Obsidian vault")
    if dry_push:
        print(f"  (dry_push=True) 跳过真实写入")
    elif vault.exists():
        from servers.sync_mcp.obsidian import push_to_obsidian
        push = push_to_obsidian(
            vault_path=vault, subject_id="full-demo",
            artifacts=run.artifacts, subdir="AI-Tutor",
        )
        print(f"  pushed={push.pushed_count}  to {push.target_dir}")
    else:
        print(f"  (vault 不存在: {vault})")

    # ────────────────────────────────────────────────────── #
    # STEP 8: tutoring.start_learning_session
    # ────────────────────────────────────────────────────── #
    section(8, "tutoring.start_learning_session(goal=48h_sprint)")
    from servers.tutoring_mcp import server as tserver
    start_fn = getattr(tserver.start_learning_session, "fn", tserver.start_learning_session)
    started = await start_fn(user_id=USER_ID, subject_id=SUBJECT_ID, goal="48h_sprint")
    print(f"  session_id     = {started.session_id}")
    print(f"  total_concepts = {started.teaching_plan['total_concepts']}")
    print(f"  first_action   = {started.current_action.type}: {started.current_action.content[:60]}")

    # ────────────────────────────────────────────────────── #
    # STEP 9: 多轮 next_action + respond
    # ────────────────────────────────────────────────────── #
    section(9, "tutoring.next_action × respond × 3 轮  ←  教学循环")
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore
    engine = TeachingEngine(db=db, sessions=SessionStore(db), llm=llm)
    sid = started.session_id

    sample_answers = [
        ("正确演示：词袋模型把文本变成词频向量，丢掉语序", "intro_done", "explain_done", 0.9),
        ("部分对：词袋统计词频", "intro_done", "explain_done", 0.5),
        ("完全不相关的答案 abc 123", "intro_done", "explain_done", 0.2),
    ]
    for i, (ans, ev1, ev2, prac_acc) in enumerate(sample_answers, start=1):
        print(f"\n  — Round {i} —")
        engine.transition_event(sid, event=ev1, payload={})
        engine.transition_event(sid, event=ev2, payload={})
        r = engine.respond(sid, answer=ans)
        print(f"  Answer:      {ans[:48]}...")
        print(f"  Correctness: {r.correctness}  Δmastery={r.mastery_update.change:+.3f}")
        print(f"  Feedback:    {r.feedback[:70]}")
        if r.error_analysis:
            print(f"  Error type:  {r.error_analysis.type}")
        # PRACTICE → NEXT → 切下一概念
        engine.transition_event(sid, event="practice_done", payload={"accuracy": prac_acc})
        engine.next_action(sid)  # 触发 concept 切换

    # ────────────────────────────────────────────────────── #
    # STEP 10: tutoring.learning_insight
    # ────────────────────────────────────────────────────── #
    section(10, "tutoring.learning_insight  ←  跨会话学习报告")
    insight_fn = getattr(tserver.learning_insight, "fn", tserver.learning_insight)
    insight = await insight_fn(user_id=USER_ID, subject_id=SUBJECT_ID)
    print(f"  overall_mastery   = {insight.overall_mastery:.3f}")
    print(f"  mastered/learning = {insight.concepts_mastered}/{insight.concepts_learning}")
    print(f"  strengths         = {insight.strengths}")
    print(f"  weaknesses ({len(insight.weaknesses)}):")
    for w in insight.weaknesses[:3]:
        print(f"    [{w['mastery']:.2f}] {w['name']:20s}  root: {w['root_cause'][:40]}")
    print(f"  recommended_focus = {insight.recommended_focus}")

    # ────────────────────────────────────────────────────── #
    # STEP 11: tutoring.generate_review_plan
    # ────────────────────────────────────────────────────── #
    section(11, "tutoring.generate_review_plan(30 min budget)")
    plan_fn = getattr(tserver.generate_review_plan, "fn", tserver.generate_review_plan)
    plan = await plan_fn(user_id=USER_ID, subject_id=SUBJECT_ID, available_time_today_min=30)
    print(f"  date       = {plan.date}")
    print(f"  total_min  = {plan.total_estimated_min}")
    print(f"  sections ({len(plan.sections)}):")
    for sec in plan.sections[:5]:
        print(f"    [{sec.priority:5.2f}] recall={sec.predicted_recall*100:3.0f}%  "
              f"{sec.estimated_minutes:2d}min  {sec.review_mode:14s}  {sec.concept_id}")

    # ────────────────────────────────────────────────────── #
    # 收尾
    # ────────────────────────────────────────────────────── #
    print(f"\n{'━' * 64}")
    print(f"  ✓ 完整 11-step 工作流跑通  ·  provider = {label}")
    if isinstance(llm, CachedLLMProvider):
        print(f"  LLM cache: {llm.stats()}")
    print(f"  数据库: {db.url}")
    print(f"{'━' * 64}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    use_mock = "--mock" in args
    dry_push = "--dry-push" in args
    args = [a for a in args if a not in ("--mock", "--dry-push")]

    md_path = DEFAULT_MD
    if "--md" in args:
        i = args.index("--md")
        md_path = Path(args[i + 1])
        args = args[:i] + args[i + 2:]

    vault = DEFAULT_VAULT
    if "--vault" in args:
        i = args.index("--vault")
        vault = Path(args[i + 1])

    if not md_path.exists():
        sys.exit(f"markdown 不存在: {md_path}")
    asyncio.run(main(md_path, vault, use_mock=use_mock, dry_push=dry_push))
