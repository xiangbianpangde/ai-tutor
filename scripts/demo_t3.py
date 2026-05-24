"""Slice T3 演示：PGFGA 心流追踪 + 增益回路修复。

场景:
1. 学生开始静默/答短（SILENT）
2. 慢慢答得长，含因果词（→ SHALLOW → FLUENT）
3. 主动提出更难的题（→ DEEP）
4. 突然连续 3 轮敷衍答 "嗯" / "不会" / "..." → 触发 student_withdrawal 修复
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


def section(t: str) -> None:
    print(f"\n{'━' * 60}\n  {t}\n{'━' * 60}")


def _enrich(rng: random.Random, name: str) -> str:
    return json.dumps({"definition": f"{name}（Mock）", "confidence": round(rng.uniform(0.7, 0.95), 2)}, ensure_ascii=False)


def _score(corr: str) -> str:
    return json.dumps({"correctness": corr, "raw_score": 0.9 if corr == "correct" else 0.4,
                       "evidence": "Mock"}, ensure_ascii=False)


def _make_llm(use_mock: bool, n: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds), f"DeepSeek({ds.model})"
    rng = random.Random(42)
    canned = [_enrich(rng, f"c{i}") for i in range(n + 5)]
    # 前 4 轮判 correct（升 flow level），后 3 轮判 incorrect（withdraw）
    canned += [_score("correct")] * 4
    canned += [_score("incorrect")] * 3
    return MockLLMProvider(canned_responses=canned), "Mock"


def main(md_path: Path, use_mock: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    from shared.models import Subject, User
    USER_ID, SUBJECT_ID = "yhn", "demo-t3"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="T3 demo"))
        s.commit()

    # ① 建 KG
    section("① 建 KG + 开会话")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    from shared.storage import FileStore
    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="demo-t3", version="v1",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID, file_store=fs, db=db,
    )
    md_corpus = Path(manifest.file_paths["markdown"])
    skeleton, _ = _build_toc(subject_slug="demo-t3", markdown_path=md_corpus)
    llm, label = _make_llm(use_mock, len(skeleton))
    print(f"  provider = {label}")

    kg = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="demo-t3",
        markdown_path=md_corpus, db=db,
    )
    with db.session() as s:
        s.get(Subject, SUBJECT_ID).kg_id = kg.kg_id
        s.commit()

    from servers.tutoring_mcp import server as ts
    start_fn = getattr(ts.start_learning_session, "fn", ts.start_learning_session)
    started = asyncio.run(start_fn(user_id=USER_ID, subject_id=SUBJECT_ID, goal="48h_sprint"))
    sid = started.session_id

    # ② 模拟从 SILENT 升到高 FlowLevel（4 轮渐入佳境）
    section("② 渐入佳境（4 轮表现越来越好）")
    from servers.tutoring_mcp.engine import TeachingEngine
    from servers.tutoring_mcp.session import SessionStore

    engine = TeachingEngine(db=db, sessions=SessionStore(db), llm=llm)

    progression = [
        "数列极限就是有界且单调",                              # SILENT → 起步
        "因为有界，所以一定收敛；这里的关键是单调性",        # 因果词 → 深度
        "我想试试更难的：ε-δ 定义具体怎么用？",            # 主动 → DEEP
        "用 ε-δ 证明：取 N=1/ε 时 |a_n - L| < ε 恒成立",  # 自纠 + 深度
    ]
    for i, ans in enumerate(progression, start=1):
        engine.transition_event(sid, event="intro_done", payload={})
        engine.transition_event(sid, event="explain_done", payload={})
        r = engine.respond(sid, answer=ans)
        c = SessionStore(db).load(sid)
        last_flow = c.recent_history[-1].get("flow_level")
        print(f"  Round {i}: correctness={r.correctness}  flow_level={last_flow}  "
              f"({['SILENT','SHALLOW','FLUENT','DEEP','IMMERSED'][int(last_flow)]})")
        if c.current_strategy_state != "CHECK":
            c.current_strategy_state = "CHECK"
            SessionStore(db).save(c)

    # ③ 突然敷衍 → 触发 GainLoopMonitor
    section("③ 突然敷衍 3 轮 → 触发回路修复")
    withdraw = ["嗯", "不会", "..."]
    final_action = None
    for i, ans in enumerate(withdraw, start=1):
        r = engine.respond(sid, answer=ans)
        c = SessionStore(db).load(sid)
        last_flow = c.recent_history[-1].get("flow_level")
        print(f"  Round {i+4}: '{ans}'  flow_level={last_flow}  "
              f"next_action={r.next_action.type if r.next_action else 'None'}")
        if r.next_action is not None:
            final_action = r.next_action
            break
        if c.current_strategy_state != "CHECK":
            c.current_strategy_state = "CHECK"
            SessionStore(db).save(c)

    section("④ 回路修复触发")
    if final_action:
        print(f"  type     = {final_action.type}")
        print(f"  content  = {final_action.content}")
        print(f"  metadata = {final_action.metadata}")
    else:
        print(f"  未触发；可能 withdrawal 信号不够强")

    print(f"\n[OK] Slice T3 demo 完成。provider = {label}")


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
    main(md_path, use_mock=use_mock)
