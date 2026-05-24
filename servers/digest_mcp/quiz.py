"""quiz generator — 从 KG 概念出题，输出 HTML + JSON 两个 artifact。

题型:
- fill_blank: 把 definition 里的 concept name 挖空让学生填
- multiple_choice: 用 4 个相邻 concept 的 name 作选项，1 正 + 3 干扰

后续切片可加:
- 难度分布（按 cognitive_load）
- 关系推理题（从 prereq edges 出题）
- LLM 生成场景题
"""
from __future__ import annotations

import html as html_lib
import json
import random
from pathlib import Path

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import ConceptRow, KnowledgeGraphRow
from shared.schemas import ArtifactURI
from shared.storage import RelationalStore

logger = get_logger("digest_mcp.quiz")

_TEMPLATE = (Path(__file__).resolve().parent / "assets" / "quiz-template.html").read_text(
    encoding="utf-8"
)


def _make_fill_blank(row: ConceptRow, qid: str) -> dict:
    """把 definition 里的 name_primary 挖掉。如果没出现 → 用题干"X 是什么？"。"""
    definition = row.definition or ""
    name = row.name_primary or ""
    if name and name in definition:
        prompt = definition.replace(name, "______", 1)
    else:
        prompt = f"以下概念的名称是什么？提示：{definition[:80]}"
    return {
        "id": qid,
        "type": "fill_blank",
        "prompt": prompt,
        "answer": name,
        "concept_id": row.id,
    }


def _make_multiple_choice(
    row: ConceptRow,
    distractor_rows: list[ConceptRow],
    qid: str,
    rng: random.Random,
) -> dict:
    """定义题：哪个 concept 名称匹配这段定义？"""
    candidates = [d.name_primary for d in distractor_rows if d.id != row.id][:3]
    while len(candidates) < 3:
        candidates.append(f"概念{rng.randint(1000,9999)}")
    options = [row.name_primary] + candidates
    rng.shuffle(options)
    return {
        "id": qid,
        "type": "multiple_choice",
        "prompt": f"以下定义对应哪个概念？\n\n{row.definition or '(无定义)'}",
        "options": options,
        "answer": row.name_primary,
        "concept_id": row.id,
    }


def _render_question_html(q: dict, idx: int) -> str:
    qtype = q["type"]
    prompt_esc = html_lib.escape(q["prompt"]).replace("\n", "<br>")
    if qtype == "fill_blank":
        body = f'<input type="text" placeholder="在此填写答案">'
    else:
        opts = "\n".join(
            f'<label><input type="radio" name="q{idx}" value="{html_lib.escape(o)}"> {html_lib.escape(o)}</label>'
            for o in q.get("options", [])
        )
        body = f'<div class="options">{opts}</div>'
    return (
        f'<div class="question" id="q{idx}">'
        f'<div class="q-type">{qtype}</div>'
        f'<div class="prompt">{prompt_esc}</div>'
        f'{body}'
        f'<div class="feedback"></div>'
        f'</div>'
    )


def generate_quiz(
    *,
    db: RelationalStore,
    kg_id: str,
    out_dir: Path,
    count: int = 10,
    seed: int | None = None,
) -> list[ArtifactURI]:
    """从 KG 生成 count 道题，写 quiz.html + quiz-data.json。"""
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)
        rows = (
            s.query(ConceptRow)
            .filter_by(kg_id=kg_id)
            .order_by(ConceptRow.id)
            .all()
        )

    rng = random.Random(seed if seed is not None else 0)
    pool = rows[:]
    rng.shuffle(pool)
    pool = pool[: min(count, len(pool))]

    questions: list[dict] = []
    for i, row in enumerate(pool):
        qid = f"q{i+1}"
        # 半数填空，半数选择
        if i % 2 == 0:
            q = _make_fill_blank(row, qid)
        else:
            # 干扰项：从其他 concept 随机取 3 个
            distractors = [r for r in rows if r.id != row.id]
            rng.shuffle(distractors)
            q = _make_multiple_choice(row, distractors[:6], qid, rng)
        questions.append(q)

    out_dir = Path(out_dir).resolve()  # 绝对路径保证 ArtifactURI 可被 sync-mcp 解析
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = out_dir / f"quiz-{kg_id}.json"
    json_path.write_text(
        json.dumps({"kg_id": kg_id, "questions": questions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # HTML
    questions_html = "\n".join(_render_question_html(q, i) for i, q in enumerate(questions))
    answers_min = json.dumps(
        [{"type": q["type"], "answer": q["answer"]} for q in questions],
        ensure_ascii=False,
    )
    html = (
        _TEMPLATE.replace("{{TITLE}}", f"测验 — {kg_id}")
        .replace("{{KG_ID}}", html_lib.escape(kg_id))
        .replace("{{COUNT}}", str(len(questions)))
        .replace("{{QUESTIONS_HTML}}", questions_html)
        .replace("{{ANSWERS_JSON}}", answers_min)
    )
    html_path = out_dir / f"quiz-{kg_id}.html"
    html_path.write_text(html, encoding="utf-8")

    logger.info("quiz.done", kg_id=kg_id, count=len(questions), out_dir=str(out_dir))
    return [
        ArtifactURI(
            uri=f"file:///{html_path.as_posix()}",
            mime_type="text/html",
            size_bytes=html_path.stat().st_size,
        ),
        ArtifactURI(
            uri=f"file:///{json_path.as_posix()}",
            mime_type="application/json",
            size_bytes=json_path.stat().st_size,
        ),
    ]
