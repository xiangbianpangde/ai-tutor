"""端到端 demo: 拿一份真实 markdown 笔记跑通 Spine v0+v1+v2 全流程。

用法:
    uv run python scripts/run_e2e_demo.py "C:\\path\\to\\your-note.md"

或不带参数 → 使用 tests/fixtures/mini_subject.md
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Windows PowerShell 默认 GBK 控制台，强制 UTF-8 以正常输出中文
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.logging_config import configure_logging
from shared.models import Subject, User
from shared.storage import RelationalStore


HEADER = "─" * 60


def section(title: str) -> None:
    print(f"\n{HEADER}\n{title}\n{HEADER}")


async def main(md_path: Path) -> None:
    configure_logging("WARNING")  # 降噪
    db = RelationalStore.from_env()
    db.init_schema()

    # ---- 准备 user + subject ----
    USER_ID = "yhn"
    SUBJECT_ID = "demo-ml"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID, display_name="YHN"))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="机器学习 demo"))
        s.commit()

    # ---- 1. acquire ----
    section("① acquire_subject")
    from servers.knowledge_mcp import server as kserver
    acquire = getattr(kserver.acquire_subject, "fn", kserver.acquire_subject)
    a = await acquire(
        subject="机器学习 demo",
        sources=[{"type": "file", "uri": str(md_path)}],
        user_id=USER_ID,
        version="2026-04-24",
    )
    print(f"corpus_id           = {a.corpus_id}")
    print(f"total_chapters (#)  = {a.stats['total_chapters']}")
    print(f"total_sections (##) = {a.stats['total_sections']}")
    print(f"artifact            = {a.artifacts[0].uri if a.artifacts else '-'}")

    # ---- 2. build_knowledge_graph(toc) ----
    section("② build_knowledge_graph(depth=toc)")
    build = getattr(kserver.build_knowledge_graph, "fn", kserver.build_knowledge_graph)
    b = await build(corpus_id=a.corpus_id, depth="toc")
    print(f"kg_id          = {b.kg_id}")
    print(f"triples_count  = {b.triples_count}")
    print(f"quality        = {b.quality_report.overall}  "
          f"(isolated={b.quality_report.isolated_nodes}, "
          f"avg_conf={b.quality_report.avg_confidence:.2f})")
    if b.quality_report.warnings:
        print(f"warnings       = {b.quality_report.warnings}")

    # ---- 列出前 10 个 concept ----
    section("KG 节点（前 12 个）")
    from shared.models import ConceptRow, RelationRow
    with db.session() as s:
        nodes = (
            s.query(ConceptRow)
            .filter_by(kg_id=b.kg_id)
            .order_by(ConceptRow.id)
            .limit(12)
            .all()
        )
        for n in nodes:
            print(f"  {n.id:55s}  [{n.bloom_level:10s}]  {n.name_primary}")
        edge_count = s.query(RelationRow).filter_by(kg_id=b.kg_id).count()
        part_of = s.query(RelationRow).filter_by(kg_id=b.kg_id, type="part_of").count()
        prereq = s.query(RelationRow).filter_by(kg_id=b.kg_id, type="prerequisite_strong").count()
        print(f"\n  总边数 = {edge_count}  (part_of={part_of}, prerequisite_strong={prereq})")

    # ---- Mermaid 缩略 ----
    section("Mermaid（前 15 行）")
    if b.mermaid:
        for line in b.mermaid.splitlines()[:15]:
            print(f"  {line}")
        if len(b.mermaid.splitlines()) > 15:
            print(f"  ... (+{len(b.mermaid.splitlines()) - 15} more)")

    # ---- 3. 关联 KG 到 subject ----
    with db.session() as s:
        subj = s.get(Subject, SUBJECT_ID)
        subj.kg_id = b.kg_id
        s.commit()

    # ---- 4. start_learning_session ----
    section("③ start_learning_session(goal=48h_sprint)")
    from servers.tutoring_mcp import server as tserver
    start = getattr(tserver.start_learning_session, "fn", tserver.start_learning_session)
    started = await start(user_id=USER_ID, subject_id=SUBJECT_ID, goal="48h_sprint")
    print(f"session_id            = {started.session_id}")
    print(f"total_concepts        = {started.teaching_plan['total_concepts']}")
    print(f"estimated_hours       = {started.teaching_plan['estimated_hours']}")
    print(f"first concepts        = {started.teaching_plan['phases'][0]['concepts'][:5]} ...")
    print(f"\ncurrent_action.type   = {started.current_action.type}")
    print(f"current_action.content = {started.current_action.content}")

    # ---- 5. 两轮交互 ----
    next_fn = getattr(tserver.next_action, "fn", tserver.next_action)
    respond_fn = getattr(tserver.respond, "fn", tserver.respond)

    for round_n, ans in enumerate(
        [
            "词袋模型就是把文本变成词频向量，丢掉语序",
            "随便说一句",
        ],
        start=1,
    ):
        section(f"④.{round_n} next_action → respond  (answer = {ans!r})")
        action = await next_fn(session_id=started.session_id)
        print(f"  action.type   = {action.type}")
        print(f"  action.content = {action.content}")
        r = await respond_fn(session_id=started.session_id, answer=ans)
        print(f"\n  correctness  = {r.correctness}")
        print(f"  feedback     = {r.feedback}")
        if r.mastery_update:
            print(f"  mastery      = {r.mastery_update.new_mastery:.3f} "
                  f"(Δ={r.mastery_update.change:+.3f}) for {r.mastery_update.concept_id}")

    # ---- 6. 落库快照 ----
    section("⑤ 持久化校验（SQLite）")
    from shared.models import BKTParamRow, SessionRow
    with db.session() as s:
        sess = s.get(SessionRow, started.session_id)
        bkt_rows = s.query(BKTParamRow).filter_by(user_id=USER_ID).all()
        print(f"  session.status                = {sess.status}")
        print(f"  session.context['stats']      = "
              f"{sess.context_json['session_stats']}")
        print(f"  BKT rows for {USER_ID}          = {len(bkt_rows)}")
        for row in bkt_rows[:3]:
            print(f"    {row.concept_id:55s}  "
                  f"mastery={row.p_mastery:.3f}  n={row.n_observations}")

    print(f"\n[OK] Done. 数据库: {db.url}")
    print("     再跑一遍可累积学习记录；删 data/tutor.db 重置。")


if __name__ == "__main__":
    md_arg = sys.argv[1] if len(sys.argv) > 1 else None
    md_path = (
        Path(md_arg) if md_arg
        else Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "mini_subject.md"
    )
    if not md_path.exists():
        sys.exit(f"markdown 文件不存在: {md_path}")
    asyncio.run(main(md_path))
