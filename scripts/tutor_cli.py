"""AI-Tutor 统一命令行入口 — 不写脚本跑完整学习流程（#8 需人引导 的 v1 缓解）。

任何新科目都用同一套命令，省略 --corpus/--kg/--session 时自动沿用上一步结果
（记录在 data/cli_state.json）。

    # ① 采集（web 主题 / 本地文件可混合，多源自动合并进一个语料库）
    uv run python scripts/tutor_cli.py acquire --subject "FastAPI 后端开发" \
        --web "FastAPI 路由与请求处理" --web "FastAPI 依赖注入" --deepen

    # ② 建图（自动关联 subject.kg_id，不再需要手工建 User/Subject 行）
    uv run python scripts/tutor_cli.py build --depth full

    # ③ 质检（quality gate + 低置信概念 + 随机抽样概念名，人工确认噪声率）
    uv run python scripts/tutor_cli.py review --sample 30

    # ④ 复习产物（study_pack / mindmap / notes / quiz ...）
    uv run python scripts/tutor_cli.py digest --formats study_pack

    # ⑤ 开课/续学 + 教学交互
    uv run python scripts/tutor_cli.py learn
    uv run python scripts/tutor_cli.py next              # 看当前教学动作
    uv run python scripts/tutor_cli.py advance           # 讲解类动作后推进
    uv run python scripts/tutor_cli.py answer "我的回答"  # 提问/练习类动作后作答
    uv run python scripts/tutor_cli.py ask "中途提问"     # 打断提问
    uv run python scripts/tutor_cli.py progress          # 跨会话进度
    uv run python scripts/tutor_cli.py status            # 最近 corpus/kg/session 与科目列表
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Windows 控制台默认 GBK，强制 UTF-8 以正常显示中文
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001 — 非关键路径
    pass

from shared.config import load_env  # noqa: E402

load_env()

from shared.errors import TutorError  # noqa: E402
from shared.logging_config import configure_logging  # noqa: E402

STATE_PATH = ROOT / "data" / "cli_state.json"
RULE = "─" * 64


def _fn(tool):
    """fastmcp @mcp.tool() 包装对象 → 原函数。"""
    return getattr(tool, "fn", tool)


def _state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _remember(**kw) -> None:
    st = _state()
    st.update({k: v for k, v in kw.items() if v is not None})
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def _need(args_value: str | None, state_key: str, flag: str) -> str:
    """优先取命令行参数，否则取 state；都没有则报错并提示先跑哪一步。"""
    v = args_value or _state().get(state_key)
    if not v:
        sys.exit(f"[错误] 缺 {flag}：命令行未给，data/cli_state.json 也没有记录。"
                 f"先跑前置步骤，或显式传 {flag}。")
    return v


def _section(title: str) -> None:
    print(f"\n{RULE}\n{title}\n{RULE}")


def _print_action(action, label: str = "当前动作") -> None:
    print(f"\n[{label}] type={action.type}  预计 {action.estimated_duration_min} min")
    content = action.content or ""
    if len(content) > 6000:
        content = content[:6000] + f"\n…（截断，共 {len(action.content)} 字）"
    print(content)
    meta = {k: v for k, v in (action.metadata or {}).items()
            if k in ("question", "options", "hint", "concept_id", "strategy")}
    if meta:
        print(f"[metadata] {json.dumps(meta, ensure_ascii=False, default=str)[:800]}")


def _print_quality(q) -> None:
    print(f"quality   = {q.overall}  (chapter_coverage={q.chapter_coverage:.2f}, "
          f"isolated={q.isolated_nodes}, cycles={q.cycles}, avg_conf={q.avg_confidence:.2f})")
    for w in q.warnings:
        print(f"  [warning] {w}")
    for s in q.suggestions:
        print(f"  [suggest] {s}")


# --------------------------------------------------------------------------- #
# 知识工程：acquire / build / review / digest
# --------------------------------------------------------------------------- #


async def cmd_acquire(args) -> None:
    from servers.knowledge_mcp import server as k

    sources: list[dict[str, str]] = []
    for topic in args.web or []:
        s = {"type": "web", "uri": topic}
        if args.deepen:
            s["deepen"] = "true"
        sources.append(s)
    for f in args.file or []:
        s = {"type": "file", "uri": str(Path(f).resolve())}
        if args.translate:
            s["translate"] = "true"
        sources.append(s)
    if not sources:
        sys.exit("[错误] 至少给一个 --web 主题或 --file 文件。")

    _section(f"acquire_subject · {args.subject} · {len(sources)} 个来源"
             + ("（deepen 多面采集）" if args.deepen else ""))
    r = await _fn(k.acquire_subject)(
        subject=args.subject, sources=sources, user_id=args.user, version=args.version,
    )
    print(f"corpus_id = {r.corpus_id}")
    print(f"stats     = {json.dumps(r.stats, ensure_ascii=False, default=str)}")
    for a in r.artifacts:
        print(f"artifact  = {a.uri}  ({a.size_bytes / 1024:.1f} KB)")
    _remember(corpus_id=r.corpus_id, subject_display=args.subject, user_id=args.user)
    print("\n下一步：uv run python scripts/tutor_cli.py build --depth full")


async def cmd_build(args) -> None:
    from servers.knowledge_mcp import server as k
    from shared.models import Corpus, Subject, User
    from shared.storage import RelationalStore

    corpus_id = _need(args.corpus, "corpus_id", "--corpus")
    _section(f"build_knowledge_graph · corpus={corpus_id} · depth={args.depth}")
    r = await _fn(k.build_knowledge_graph)(corpus_id=corpus_id, depth=args.depth)
    print(f"kg_id         = {r.kg_id}")
    print(f"triples_count = {r.triples_count}")
    _print_quality(r.quality_report)

    # 接线：User / Subject 行 + subject.kg_id（曾经是每次都要手写的胶水脚本）
    db = RelationalStore.from_env()
    db.init_schema()
    with db.session() as s:
        corpus = s.get(Corpus, corpus_id)
        subject_id, user_id = corpus.subject_id, corpus.user_id
        display = (corpus.manifest_json or {}).get("subject") or subject_id
        if s.get(User, user_id) is None:
            s.add(User(id=user_id, display_name=user_id))
        subj = s.get(Subject, subject_id)
        if subj is None:
            subj = Subject(id=subject_id, user_id=user_id, display_name=display)
            s.add(subj)
        subj.kg_id = r.kg_id
        s.commit()
    print(f"已关联 subject[{subject_id}].kg_id = {r.kg_id}")
    _remember(kg_id=r.kg_id, subject_id=subject_id, user_id=user_id)
    print("\n下一步：uv run python scripts/tutor_cli.py review --sample 30")


async def cmd_review(args) -> None:
    from servers.knowledge_mcp import server as k
    from shared.models import ConceptRow, RelationRow
    from shared.storage import RelationalStore

    kg_id = _need(args.kg, "kg_id", "--kg")
    _section(f"review_kg · kg={kg_id} · mode={args.mode}")
    r = await _fn(k.review_kg)(kg_id=kg_id, mode=args.mode, limit=args.limit)
    for w in r.warnings:
        print(f"[warning] {w}")
    for sgst in r.suggestions:
        print(f"[suggest] {sgst}")
    if r.low_confidence_concepts:
        print(f"\n低置信概念（{len(r.low_confidence_concepts)} 个）:")
        for c in r.low_confidence_concepts:
            print(f"  {c.confidence:.2f}  {c.name}  — {c.definition_preview[:60]}")

    db = RelationalStore.from_env()
    with db.session() as s:
        rows = s.query(ConceptRow).filter_by(kg_id=kg_id).all()
        n_rel = s.query(RelationRow).filter_by(kg_id=kg_id).count()
        print(f"\n概念总数 = {len(rows)}，关系总数 = {n_rel}")
        if args.sample and rows:
            picked = random.sample(rows, min(args.sample, len(rows)))
            print(f"\n随机抽样 {len(picked)} 个概念名（人工确认噪声率）:")
            for i, c in enumerate(sorted(picked, key=lambda x: x.id), 1):
                print(f"  {i:2d}. [{c.category:8s}] {c.name_primary}")


async def cmd_digest(args) -> None:
    from servers.digest_mcp import server as d

    kg_id = _need(args.kg, "kg_id", "--kg")
    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    _section(f"digest · kg={kg_id} · formats={formats}")
    r = await _fn(d.digest)(kg_id=kg_id, formats=formats)
    if not r.artifacts:
        print("（无产物）")
    for a in r.artifacts:
        print(f"artifact = {a.uri}  ({a.size_bytes / 1024:.1f} KB)")


# --------------------------------------------------------------------------- #
# 教学：learn / next / advance / answer / ask / progress
# --------------------------------------------------------------------------- #


async def cmd_learn(args) -> None:
    from servers.tutoring_mcp import server as t

    subject_id = _need(args.subject_id, "subject_id", "--subject-id")
    user_id = args.user or _state().get("user_id", "default")
    _section(f"resume_learning · user={user_id} · subject={subject_id} · goal={args.goal}")
    r = await _fn(t.resume_learning)(user_id=user_id, subject_id=subject_id, goal=args.goal)
    print(f"session_id = {r.session_id}")
    if r.pre_session_insight:
        print(f"insight    = {r.pre_session_insight}")
    plan = r.teaching_plan or {}
    print(f"plan       = 概念 {plan.get('total_concepts', '?')} 个 / "
          f"预计 {plan.get('estimated_hours', '?')} 小时 / "
          f"{len(plan.get('phases', []))} 个 Phase")
    _remember(session_id=r.session_id, subject_id=subject_id, user_id=user_id)
    _print_action(r.current_action)


async def cmd_next(args) -> None:
    from servers.tutoring_mcp import server as t

    session_id = _need(args.session, "session_id", "--session")
    action = await _fn(t.next_action)(session_id=session_id)
    _print_action(action)


async def cmd_advance(args) -> None:
    from servers.tutoring_mcp import server as t

    session_id = _need(args.session, "session_id", "--session")
    action = await _fn(t.advance)(session_id=session_id)
    _print_action(action, label="推进后动作")


async def cmd_answer(args) -> None:
    from servers.tutoring_mcp import server as t

    session_id = _need(args.session, "session_id", "--session")
    r = await _fn(t.respond)(session_id=session_id, answer=args.text)
    print(f"\n[判分] correctness = {r.correctness}")
    print(f"[反馈] {r.feedback}")
    if r.error_analysis and r.error_analysis.type:
        print(f"[诊断] {r.error_analysis.type}: {r.error_analysis.explanation}")
    if r.mastery_update:
        print(f"[掌握] {r.mastery_update.concept_id}: "
              f"{r.mastery_update.new_mastery:.3f} ({r.mastery_update.change:+.3f})")
    if r.next_action:
        _print_action(r.next_action, label="下一动作")


async def cmd_ask(args) -> None:
    from servers.tutoring_mcp import server as t

    session_id = _need(args.session, "session_id", "--session")
    r = await _fn(t.interrupt)(session_id=session_id, question=args.text)
    print(f"\n[打断响应] type={r.type}")
    print(r.content)
    if r.resume_prompt:
        print(f"[回归提示] {r.resume_prompt}")


async def cmd_progress(args) -> None:
    from servers.tutoring_mcp import server as t

    subject_id = _need(args.subject_id, "subject_id", "--subject-id")
    user_id = args.user or _state().get("user_id", "default")
    r = await _fn(t.get_learning_progress)(user_id=user_id, subject_id=subject_id)
    _section(f"学习进度 · {subject_id}")
    print(f"总体掌握 = {r.overall_mastery_ratio:.1%}  "
          f"({r.concepts_mastered}/{r.concepts_total} 概念)")
    print(f"当前阶段 = Phase {r.current_phase}: {r.current_phase_title}")
    print(f"下一概念 = {r.next_concept_name} ({r.next_concept_id})")
    for p in r.phases:
        print(f"  Phase {p.phase} {p.title}: {p.concepts_mastered}/{p.concepts_total} ({p.status})")


async def cmd_status(args) -> None:  # noqa: ARG001 — argparse 统一签名
    from shared.models import SessionRow, Subject
    from shared.storage import RelationalStore

    _section("CLI 状态（data/cli_state.json）")
    st = _state()
    print(json.dumps(st, ensure_ascii=False, indent=2) if st else "（空 — 还没跑过任何步骤）")

    db = RelationalStore.from_env()
    db.init_schema()
    with db.session() as s:
        subjects = s.query(Subject).all()
        if subjects:
            print("\n科目列表:")
            for subj in subjects:
                n_active = (s.query(SessionRow)
                            .filter_by(subject_id=subj.id, status="active").count())
                print(f"  {subj.id:42s} kg={subj.kg_id or '-':46s} active_sessions={n_active}")


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tutor_cli",
        description="AI-Tutor 命令行入口：采集→建图→质检→产物→教学，全程免写脚本。",
    )
    parser.add_argument("--verbose", action="store_true", help="输出 INFO 级日志")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("acquire", help="采集语料（web 主题 / 本地文件，多源合并）")
    p.add_argument("--subject", required=True, help="科目显示名")
    p.add_argument("--web", action="append", help="web 检索主题，可多次")
    p.add_argument("--file", action="append", help="本地文件路径（md/pdf），可多次")
    p.add_argument("--deepen", action="store_true", help="web 主题 LLM 拆面深挖（FIX-I）")
    p.add_argument("--translate", action="store_true", help="外文 PDF 先译中文（pdf2zh 核）")
    p.add_argument("--user", default="yhn")
    p.add_argument("--version", default=None, help="教材版本字符串")
    p.set_defaults(func=cmd_acquire, default_log="INFO")

    p = sub.add_parser("build", help="语料 → 知识图谱（并自动关联 subject.kg_id）")
    p.add_argument("--corpus", default=None, help="corpus_id（默认上次 acquire 的）")
    p.add_argument("--depth", default="full", choices=["toc", "concept", "full"])
    p.set_defaults(func=cmd_build, default_log="INFO")

    p = sub.add_parser("review", help="KG 质检：quality gate + 低置信 + 随机抽样")
    p.add_argument("--kg", default=None, help="kg_id（默认上次 build 的）")
    p.add_argument("--mode", default="quick", choices=["quick", "full"])
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--sample", type=int, default=30, help="随机抽样概念名个数（0 关闭）")
    p.set_defaults(func=cmd_review, default_log="WARNING")

    p = sub.add_parser("digest", help="生成复习产物")
    p.add_argument("--kg", default=None)
    p.add_argument("--formats", default="study_pack",
                   help="逗号分隔：study_pack,mindmap,notes,quiz,slides,…")
    p.set_defaults(func=cmd_digest, default_log="INFO")

    p = sub.add_parser("learn", help="开课/续学（自动复用未结束会话）")
    p.add_argument("--subject-id", default=None, help="科目 slug（默认上次 build 的）")
    p.add_argument("--user", default=None)
    p.add_argument("--goal", default="48h_sprint",
                   choices=["48h_sprint", "semester_study", "exam_review", "quick_overview"])
    p.set_defaults(func=cmd_learn, default_log="WARNING")

    for name, fun, hlp in [
        ("next", cmd_next, "查看当前教学动作"),
        ("advance", cmd_advance, "讲解类动作后推进"),
    ]:
        p = sub.add_parser(name, help=hlp)
        p.add_argument("--session", default=None)
        p.set_defaults(func=fun, default_log="WARNING")

    p = sub.add_parser("answer", help="回答当前提问/练习")
    p.add_argument("text", help="回答内容")
    p.add_argument("--session", default=None)
    p.set_defaults(func=cmd_answer, default_log="WARNING")

    p = sub.add_parser("ask", help="中途打断提问")
    p.add_argument("text", help="问题内容")
    p.add_argument("--session", default=None)
    p.set_defaults(func=cmd_ask, default_log="WARNING")

    p = sub.add_parser("progress", help="跨会话学习进度")
    p.add_argument("--subject-id", default=None)
    p.add_argument("--user", default=None)
    p.set_defaults(func=cmd_progress, default_log="WARNING")

    p = sub.add_parser("status", help="CLI 状态 + 科目列表")
    p.set_defaults(func=cmd_status, default_log="WARNING")

    args = parser.parse_args()
    configure_logging("INFO" if args.verbose else args.default_log)
    try:
        asyncio.run(args.func(args))
    except TutorError as e:
        # hint 里通常带外部 CLI 的 stderr 尾巴（如 mineru），吞掉会让诊断只剩盲猜
        msg = f"[错误] {e}"
        if e.hint:
            msg += f"\n[hint] {e.hint}"
        sys.exit(msg)


if __name__ == "__main__":
    main()
