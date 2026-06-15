"""scripts/learn_to_completion.py —— 用 MiniMax 真 LLM 把一个科目**学到完成**。

验证 "完全学完一个科目"：导入资料 → 建图 → 教学循环（MiniMax 判分）驱动到 session
status=completed。MiniMax 同时充当**判分器**（注入引擎）和**优等生**（按题目生成好答案），
模拟一个认真学习并答对的学生，从而走完所有概念。

用法：NO_PROXY='*' .venv/Scripts/python.exe scripts/learn_to_completion.py "科目名" path/to/material.md
不传参 → 用内置 3 概念样例。打印每步轨迹 + 最终是否 COMPLETED。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.teaching.minimax_provider import MiniMaxProvider  # noqa: E402
from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire  # noqa: E402
from servers.knowledge_mcp.kg_enrich_adapter import build_kg_toc  # noqa: E402
from servers.tutoring_mcp.engine import TeachingEngine  # noqa: E402
from servers.tutoring_mcp.session import SessionStore  # noqa: E402
from shared.models import ConceptRow, User  # noqa: E402
from shared.storage import FileStore, RelationalStore  # noqa: E402

# 按 action.type 分支（策略无关）：这些类型需要学生作答，其余是展示态→继续。
QUESTION_TYPES = {"ask_question", "give_exercise", "probe", "elicit"}
_SAMPLE = """# 极限
当自变量趋近某个值时，函数值无限接近的那个确定的数。
# 连续
函数在某点的极限值等于它在该点的取值，图像不间断。
# 导数
函数在某点的瞬时变化率，是切线的斜率，由极限定义。
"""


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else "数学分析样例"
    md_text = Path(sys.argv[2]).read_text(encoding="utf-8") if len(sys.argv) > 2 else _SAMPLE

    d = Path(tempfile.mkdtemp())
    store = RelationalStore(f"sqlite:///{d / 't.db'}")
    store.init_schema()
    with store.session() as s:
        s.add(User(id="learner", display_name="学习者"))
        s.commit()
    md = d / "m.md"
    md.write_text(md_text, encoding="utf-8")
    manifest, cid = acquire(
        subject=name, version="v1",
        sources=[AcquireSource(type="file", uri=str(md))],
        user_id="learner", file_store=FileStore(str(d / "f")), db=store,
    )
    kg_id, concepts, *_ = build_kg_toc(
        corpus_id=cid, subject_slug="subj",
        markdown_path=Path(manifest.file_paths["markdown"]), db=store,
    )
    print(f"科目「{name}」: {len(concepts)} 概念 {[c.names[0] for c in concepts]}")

    judge = MiniMaxProvider()
    student = MiniMaxProvider()  # 同一 API，充当优等生答题
    eng = TeachingEngine(db=store, sessions=SessionStore(store), llm=judge)
    ss = SessionStore(store)
    ctx = ss.create(user_id="learner", subject_id=name)
    order = eng._topo_order(kg_id)
    ctx.current_concept_id = order[0]
    ctx.position_in_plan = 0
    ctx.status = "active"
    ctx.teaching_plan_id = kg_id
    ss.save(ctx)

    def concept_def(cid_: str) -> tuple[str, str]:
        with store.session() as s:
            r = s.get(ConceptRow, cid_)
            return (r.name_primary, r.definition) if r else ("", "")

    def answer_question(cname: str, defn: str, question: str) -> str:
        prompt = (
            f"你是学懂了的优等生。概念「{cname}」的定义是：{defn}\n"
            f"老师的提问/练习是：{question}\n"
            "请直接用自己的话，准确、完整地讲清这个概念的核心（2-3 句）。"
            "即使题目不具体或像练习题，也要用该概念的定义正面作答，"
            "**绝对不要**说'没有给出例子/题目不具体'之类的话。只输出答案本身。"
        )
        try:
            ans = student.chat(messages=[{"role": "user", "content": prompt}],
                               temperature=0.3, max_tokens=400).content.strip()
            # 防御：模型仍在抱怨没题目 → 退回用定义自述
            if not ans or "没有" in ans[:12] or "请" in ans[:6]:
                return f"{cname}指的是：{defn}"
            return ans
        except Exception:
            return f"{cname}指的是：{defn}"

    mastered_path: list[str] = []
    for step in range(60):
        ctx = ss.load(ctx.session_id)
        if ctx.status == "completed":
            print(f"[{step}] ✅ 科目已学完 COMPLETED  pos={ctx.position_in_plan}/{len(order)}")
            break
        action = eng.next_action(ctx.session_id)
        ctx = ss.load(ctx.session_id)
        if ctx.status == "completed":
            print(f"[{step}] ✅ 科目已学完 COMPLETED（动作后）")
            break
        st = ctx.current_strategy_state or ""
        cname, defn = concept_def(ctx.current_concept_id)
        print(f"[{step}] {action.type:14} state={st:6} 概念={cname} pos={ctx.position_in_plan}")
        try:
            if action.type in QUESTION_TYPES:
                ans = answer_question(cname, defn, action.content or "")
                res = eng.respond(ctx.session_id, ans)
                print(f"      学生答：{ans[:46]}… → 判 {res.correctness}")
                if ctx.current_concept_id not in mastered_path and res.correctness == "correct":
                    mastered_path.append(ctx.current_concept_id)
            else:  # 展示态 / break → 继续
                before = ss.load(ctx.session_id).current_strategy_state
                eng.advance(ctx.session_id)
                # advance 没推动（非展示态卡住）→ 兜底用 respond 当作答
                if ss.load(ctx.session_id).current_strategy_state == before:
                    ans = answer_question(cname, defn, action.content or "")
                    eng.respond(ctx.session_id, ans)
        except Exception as e:  # noqa: BLE001
            print(f"      ERR {type(e).__name__}: {str(e)[:80]}")
    else:
        print("⚠️ 60 步内未学完")

    final = ss.load(ctx.session_id)
    print(f"\n最终：status={final.status}  位置={final.position_in_plan}/{len(order)}  "
          f"答对概念={len(mastered_path)}")
    return 0 if final.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
