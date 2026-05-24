"""Slice T1+ 演示：interrupt + checkpoint 完整。

模拟一个真实场景：
1. 开会话 → 教第 1 个 concept
2. 学生打断："我有点晕了"      → cognitive_overload → 建议休息
3. 学生打断："什么是 X？"      → concept_question → 给定义
4. 学生打断："太慢了，能跳吗"  → pace_complaint → 提供节奏选项
5. 学生打断："今天天气真好"    → distraction → 温和拉回
6. 学生 checkpoint："基本都懂了" → 对比 BKT 实际，校准元认知
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
from shared.providers.deepseek import DeepSeekProvider
from shared.storage import RelationalStore


def section(t: str) -> None:
    print(f"\n{'━' * 60}\n  {t}\n{'━' * 60}")


def _enrich(rng: random.Random, name: str) -> str:
    return json.dumps({"definition": f"{name}（Mock）", "confidence": round(rng.uniform(0.7, 0.95), 2)}, ensure_ascii=False)


def _intent(name: str) -> str:
    return json.dumps({"intent": name, "confidence": 0.9, "evidence": "test"}, ensure_ascii=False)


def _make_llm(use_mock: bool, n: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds), f"DeepSeek({ds.model})"
    rng = random.Random(42)
    # 预备：enrichment × N + 5 个 intent 分类 + 1 个 self_score
    canned = [_enrich(rng, f"c{i}") for i in range(n + 5)]
    canned += [_intent("cognitive_overload"), _intent("concept_question"),
               _intent("pace_complaint"), _intent("distraction")]
    canned += [json.dumps({"self_score": 0.85, "confidence": 0.7}, ensure_ascii=False)]
    return MockLLMProvider(canned_responses=canned), "Mock"


async def main(md_path: Path, use_mock: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    from shared.models import Subject, User
    USER_ID, SUBJECT_ID = "yhn", "demo-t1plus"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="T1+ demo"))
        s.commit()

    # ① 建 KG
    section("① 建 KG + 开会话")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    from shared.storage import FileStore
    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="demo-t1plus", version="v1",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID, file_store=fs, db=db,
    )
    md_corpus = Path(manifest.file_paths["markdown"])
    skeleton, _ = _build_toc(subject_slug="demo-t1plus", markdown_path=md_corpus)
    llm, label = _make_llm(use_mock, len(skeleton))
    print(f"provider = {label} · {len(skeleton)} concepts")

    kg = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="demo-t1plus",
        markdown_path=md_corpus, db=db,
    )
    with db.session() as s:
        s.get(Subject, SUBJECT_ID).kg_id = kg.kg_id
        s.commit()

    from servers.tutoring_mcp import server as ts
    start_fn = getattr(ts.start_learning_session, "fn", ts.start_learning_session)
    started = await start_fn(user_id=USER_ID, subject_id=SUBJECT_ID, goal="48h_sprint")
    sid = started.session_id
    print(f"session_id   = {sid}")
    print(f"first action = {started.current_action.content[:60]}")

    # ② 4 次打断
    int_fn = getattr(ts.interrupt, "fn", ts.interrupt)

    for label2, q in [
        ("cognitive_overload", "我有点晕了，信息太多"),
        ("concept_question",   "什么是词袋模型？"),
        ("pace_complaint",     "太慢了，能跳过吗"),
        ("distraction",        "今天天气真好"),
    ]:
        section(f"② interrupt — 学生说：'{q}'  (期望 intent: {label2})")
        r = await int_fn(session_id=sid, question=q)
        print(f"  type            = {r.type}")
        print(f"  content         = {r.content[:90]}")
        print(f"  resume_prompt   = {r.resume_prompt}")
        print(f"  suggested       = {r.suggested_action}")
        print(f"  checkpoint_saved= {r.checkpoint_saved}")

    # ③ 模拟 1-2 轮 respond，让 BKT 有数据
    section("③ 一轮答题（让 BKT 有数据）")
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore
    engine = TeachingEngine(db=db, sessions=SessionStore(db), llm=llm)
    engine.transition_event(sid, event="intro_done", payload={})
    engine.transition_event(sid, event="explain_done", payload={})
    r = engine.respond(sid, answer="词袋模型把文本变成词频向量")
    print(f"  correctness = {r.correctness}  Δmastery = {r.mastery_update.change:+.3f}")

    # ④ checkpoint
    section("④ checkpoint — 学生自评 '基本都懂了'  (期望 self_score≈0.85)")
    cp_fn = getattr(ts.checkpoint, "fn", ts.checkpoint)
    res = await cp_fn(session_id=sid, kind="self_summary", content="基本都懂了")
    print(f"  self_score             = {res['self_score']}")
    print(f"  actual_mastery_avg     = {res['actual_mastery_avg']}")
    print(f"  self_assessment_accuracy = {res['self_assessment_accuracy']}")
    print(f"  suggestions:")
    for s in res["suggestions"]:
        print(f"    - {s}")
    print(f"  current_mastery_map: {len(res['current_mastery_map'])} concepts")

    # ⑤ session 状态确认
    section("⑤ session 持久化状态")
    from servers.tutoring_mcp.session import SessionStore as SS
    ctx = SS(db).load(sid)
    print(f"  status              = {ctx.status}")
    print(f"  interrupt_count     = {ctx.meta.interrupt_count}")
    print(f"  checkpoint_count    = {ctx.meta.checkpoint_count}")
    print(f"  current_strategy    = {ctx.current_strategy} ({ctx.current_strategy_state})")
    print(f"  interrupt_checkpoint? {ctx.interrupt_checkpoint is not None}")

    # ⑥ LearnerProfile.metacognitive 已经被更新
    section("⑥ LearnerProfile 元认知更新")
    from shared.models import LearnerProfileRow
    with db.session() as s:
        row = s.get(LearnerProfileRow, USER_ID)
        meta = (row.profile_json or {}).get("metacognitive", {})
        print(f"  self_assessment_accuracy = {meta.get('self_assessment_accuracy')}")

    print(f"\n[OK] Slice T1+ demo 完成。provider = {label}")
    print("     tutoring-mcp 现在 8/8 tool 全部实现")


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
        sys.exit(f"markdown 不存在: {md_path}")
    asyncio.run(main(md_path, use_mock=use_mock))
