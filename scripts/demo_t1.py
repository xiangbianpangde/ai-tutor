"""Slice T1 演示：完整教学循环。

展示 T1 升级:
1. ReductionStrategy 完整状态机：INTRO → EXPLAIN → CHECK → PRACTICE → NEXT
2. LLMScorer 语义判分（替代 spine v2 的 2-gram）
3. ErrorDiagnoser 在错答时给出错误类型 + 补救建议
4. 自动切换到下一个 concept（按拓扑序）
5. session 完成时自动 complete

默认走真实 DeepSeek（需要 .env 里有 DEEPSEEK_API_KEY），--mock 用模拟数据。
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
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
from shared.models import Subject, User
from shared.providers.deepseek import DeepSeekProvider
from shared.storage import RelationalStore


def section(t: str) -> None:
    print(f"\n{'─' * 60}\n{t}\n{'─' * 60}")


def _canned_enrichment(rng: random.Random, name: str) -> str:
    return json.dumps({
        "definition": f"{name}（Mock 填充）",
        "informal_description": f"通俗解释 {name}",
        "examples": [{"text": f"{name} 的例子", "type": "computation"}],
        "common_misconceptions": [f"误解 {name}"],
        "bloom_level": rng.choice(["remember", "understand", "apply"]),
        "confidence": round(rng.uniform(0.6, 0.95), 2),
    }, ensure_ascii=False)


def _canned_score(correctness: str = "correct", score: float = 0.85) -> str:
    return json.dumps({
        "correctness": correctness,
        "raw_score": score,
        "evidence": "Mock 判分",
        "suggested_remediation": "" if correctness == "correct" else "再读一遍定义",
    }, ensure_ascii=False)


def _canned_diagnosis() -> str:
    return json.dumps({
        "error_type": "concept_confusion",
        "root_concept_id": "demo:1:x",
        "surface_concept_id": "demo:1:x",
        "confidence": 0.8,
        "evidence": ["学生混淆了两个相关概念"],
        "remediation_suggestion": "对比两个概念的核心差异",
    }, ensure_ascii=False)


def _make_llm(use_mock: bool, n_concepts: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds, max_size=256), f"DeepSeek({ds.model})"
    rng = random.Random(42)
    canned = (
        [_canned_enrichment(rng, f"c{i}") for i in range(n_concepts + 5)]
        + [_canned_score("correct", 0.9)] * 20
        + [_canned_score("partial", 0.5), _canned_diagnosis()]
        + [_canned_score("incorrect", 0.1), _canned_diagnosis()]
    )
    return MockLLMProvider(canned_responses=canned), "Mock"


def main(md_path: Path, use_mock: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    USER_ID, SUBJECT_ID = "yhn", "demo-t1-ml"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="T1 demo"))
        s.commit()

    # ---- ① 建 KG（depth=concept）----
    section("① 建 KG (depth=concept)")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    from shared.storage import FileStore

    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="ml-t1", version="t1",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID, file_store=fs, db=db,
    )
    md_corpus = Path(manifest.file_paths["markdown"])
    skeleton, _ = _build_toc(subject_slug="ml-t1", markdown_path=md_corpus)
    n = len(skeleton)
    llm, label = _make_llm(use_mock, n)
    print(f"provider     = {label}")
    print(f"# concepts   = {n}")

    kg_result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="ml-t1",
        markdown_path=md_corpus, db=db,
    )
    with db.session() as s:
        subj = s.get(Subject, SUBJECT_ID)
        subj.kg_id = kg_result.kg_id
        s.commit()
    print(f"kg_id        = {kg_result.kg_id}")
    print(f"avg conf     = {kg_result.quality_report.avg_confidence:.3f}")

    # ---- ② 开学习会话 ----
    section("② start_learning_session")
    from servers.tutoring_mcp import server as tserver
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    start_fn = getattr(tserver.start_learning_session, "fn", tserver.start_learning_session)
    started = asyncio.run(start_fn(user_id=USER_ID, subject_id=SUBJECT_ID, goal="48h_sprint"))
    print(f"session_id           = {started.session_id}")
    print(f"total_concepts       = {started.teaching_plan['total_concepts']}")
    print(f"current_action.type  = {started.current_action.type}")
    print(f"current_action.body  = {started.current_action.content[:80]}")

    # ---- ③ 走一个完整的 INTRO→EXPLAIN→CHECK→PRACTICE→NEXT 循环 ----
    section("③ 完整 reduction 状态机循环（concept 1）")
    sessions = SessionStore(db)
    engine = TeachingEngine(db=db, sessions=sessions, llm=llm)

    sid = started.session_id

    def _dump_state(label: str) -> None:
        ctx = sessions.load(sid)
        print(f"  [{label}] strategy_state={ctx.current_strategy_state}  "
              f"current_concept={ctx.current_concept_id}")

    _dump_state("after start")

    # INTRO → EXPLAIN
    engine.transition_event(sid, event="intro_done", payload={})
    a = engine.next_action(sid)
    _dump_state("after intro_done")
    print(f"  → action: type={a.type}  '{a.content[:60]}...'")

    # EXPLAIN → CHECK
    engine.transition_event(sid, event="explain_done", payload={})
    a = engine.next_action(sid)
    _dump_state("after explain_done")
    print(f"  → action: type={a.type}  '{a.content[:60]}...'")

    # 学生回答（CHECK → PRACTICE）
    r = engine.respond(sid, answer="词袋模型把文本转成词频向量，忽略词序")
    _dump_state("after respond (CHECK→...)")
    print(f"  → correctness={r.correctness}  Δmastery={r.mastery_update.change:+.3f}")
    print(f"  → feedback: {r.feedback[:80]}")
    if r.error_analysis:
        print(f"  → error_type: {r.error_analysis.type}  remediation: {r.error_analysis.remediation[:60]}")

    # PRACTICE → NEXT
    engine.transition_event(sid, event="practice_done", payload={"accuracy": 0.9})
    _dump_state("after practice_done")

    # 触发自动切下一概念
    a = engine.next_action(sid)
    _dump_state("after next_action (concept 切换)")
    print(f"  → action: type={a.type}  '{a.content[:60]}...'")

    # ---- ④ 模拟一次错答 ----
    section("④ 模拟错答（看错误诊断 + 防火墙）")
    engine.transition_event(sid, event="intro_done", payload={})
    engine.transition_event(sid, event="explain_done", payload={})
    r = engine.respond(sid, answer="完全不相关的胡言乱语 XX YY ZZ")
    print(f"  correctness    = {r.correctness}")
    print(f"  feedback       = {r.feedback}")
    if r.error_analysis:
        print(f"  error_type     = {r.error_analysis.type}")
        print(f"  root_concept   = {r.error_analysis.root_concept}")
        print(f"  evidence       = {r.error_analysis.explanation[:80]}")
        print(f"  remediation    = {r.error_analysis.remediation[:80]}")
    # 防火墙检查：反馈不应含禁词
    forbidden = ["你错了", "太棒了", "你应该", "不对"]
    bad = [w for w in forbidden if w in r.feedback]
    print(f"  防火墙检查      = {'PASS' if not bad else 'FAIL: ' + ', '.join(bad)}")

    # ---- ⑤ 最终 session 状态 ----
    section("⑤ session 最终状态")
    ctx = sessions.load(sid)
    print(f"  status                = {ctx.status}")
    print(f"  position_in_plan      = {ctx.position_in_plan}")
    print(f"  questions_asked       = {ctx.session_stats.total_questions_asked}")
    print(f"  correct_rate          = {ctx.session_stats.correct_rate:.2f}")
    print(f"  errors_by_type        = {ctx.session_stats.errors_by_type}")

    if isinstance(llm, CachedLLMProvider):
        print(f"\nLLM cache stats: {llm.stats()}")
    print(f"\n[OK] Slice T1 demo 完成。provider = {label}")


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
