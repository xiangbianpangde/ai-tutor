"""multi_agent generator — 三角色教学对话脚本（JSON）。

每个 concept 生成一段对话，角色：
- teacher  讲解者：用定义 + 通俗解释开场
- student  学习者：提一个"为什么/怎么用"的真实疑问
- skeptic  抬杠者：抛一个常见误解逼 teacher 澄清
- teacher  收尾：回应误解 + 给一个例子

有 LLM → 让 LLM 生成自然对话；无 LLM → 规则模板（用 KG 已有字段填充）。
输出 dialogue-{kg_id}.json，可被前端逐句播放 / 配音。
"""
from __future__ import annotations

import json
from pathlib import Path

from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.schemas import ArtifactURI
from shared.storage import RelationalStore

from ._kg_read import load_sorted_concepts

logger = get_logger("digest_mcp.multi_agent")

_SYSTEM = (
    "你是教学对话编剧。给定一个概念，写一段 4-6 轮的三角色对话："
    "teacher（讲解）、student（提真实疑问）、skeptic（抛常见误解）。"
    "只输出 JSON 数组，每元素 {\"role\":..., \"content\":...}，role ∈ "
    "{teacher,student,skeptic}。中文，口语化，每句 ≤ 60 字。"
)


def _template_dialogue(card: dict) -> list[dict]:
    """无 LLM 时的规则模板对话。"""
    name = card["name"]
    turns = [
        {"role": "teacher", "content": f"我们来看「{name}」。{card['definition']}"},
    ]
    if card["informal"]:
        turns.append({"role": "teacher", "content": f"换句话说，{card['informal']}"})
    turns.append({"role": "student", "content": f"那「{name}」到底在什么场景下用得到？"})
    if card["examples"]:
        turns.append({"role": "teacher", "content": f"比如：{card['examples'][0]}"})
    else:
        turns.append({"role": "teacher", "content": "它是后续很多内容的基础，先把定义吃透。"})
    if card["misconceptions"]:
        turns.append({"role": "skeptic", "content": f"我一直以为：{card['misconceptions'][0]}，不对吗？"})
        turns.append({"role": "teacher", "content": "这是个常见误解——回到定义就能分辨，别被直觉带偏。"})
    else:
        turns.append({"role": "student", "content": "我大概懂了，让我自己复述一遍试试。"})
    return turns


def _llm_dialogue(llm: LLMProvider, card: dict) -> list[dict]:
    prompt = (
        f"概念名：{card['name']}\n定义：{card['definition']}\n"
        f"通俗解释：{card['informal']}\n"
        f"例子：{'; '.join(card['examples']) or '无'}\n"
        f"常见误解：{'; '.join(card['misconceptions']) or '无'}"
    )
    resp = llm.chat(messages=[
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": prompt},
    ])
    text = (resp.content or "").strip()
    if not text:
        return _template_dialogue(card)
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("["), text.rfind("]")
        if s >= 0 and e > s:
            try:
                parsed = json.loads(text[s:e + 1])
            except json.JSONDecodeError:
                return _template_dialogue(card)
        else:
            return _template_dialogue(card)
    # 校验结构
    if not isinstance(parsed, list) or not parsed:
        return _template_dialogue(card)
    valid = [
        {"role": t["role"], "content": str(t["content"])}
        for t in parsed
        if isinstance(t, dict) and t.get("role") in ("teacher", "student", "skeptic")
        and t.get("content")
    ]
    return valid or _template_dialogue(card)


def _card(r) -> dict:
    full = r.full_json or {}
    return {
        "id": r.id,
        "name": r.name_primary or r.id,
        "definition": r.definition or "（暂无定义）",
        "informal": r.informal_description or "",
        "examples": [e.get("text", "") for e in (full.get("examples") or []) if e.get("text")],
        "misconceptions": list(full.get("common_misconceptions") or []),
    }


def generate_multi_agent(
    *, db: RelationalStore, kg_id: str, out_dir: Path,
    llm: LLMProvider | None = None,
) -> ArtifactURI:
    """生成三角色对话脚本 JSON，返回 ArtifactURI。"""
    kg, rows = load_sorted_concepts(db, kg_id)

    scenes: list[dict] = []
    for r in rows:
        card = _card(r)
        turns = _llm_dialogue(llm, card) if llm is not None else _template_dialogue(card)
        scenes.append({"concept_id": card["id"], "concept_name": card["name"], "dialogue": turns})

    doc = {
        "subject": kg.subject_id,
        "kg_id": kg_id,
        "roles": {
            "teacher": "讲解者",
            "student": "学习者",
            "skeptic": "抬杠者（逼澄清误解）",
        },
        "generator": "llm" if llm is not None else "template",
        "scenes": scenes,
    }

    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / f"dialogue-{kg_id}.json"
    file_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("multi_agent.done", kg_id=kg_id, scenes=len(scenes),
                generator=doc["generator"], file=str(file_path))
    return ArtifactURI(
        uri=f"file:///{file_path.as_posix()}",
        mime_type="application/json",
        size_bytes=file_path.stat().st_size,
    )
