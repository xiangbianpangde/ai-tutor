"""ConceptEnricher — 把 toc 模式的骨架 Concept 用 LLM 富化为带定义/例子/置信度的真实概念。

调用契约:
  enricher = ConceptEnricher(llm=llm_provider)
  enriched, warning = enricher.enrich(concept=toc_concept, body_text="...章节正文...")

LLM 期望返回 JSON:
  {
    "definition": "...",                  # 真实定义
    "informal_description": "...",        # 口语化描述
    "examples": [{"text": "...", "type": "computation|proof|..."}],
    "common_misconceptions": ["...", "..."],
    "bloom_level": "remember|understand|apply|analyze|evaluate|create",
    "confidence": 0.0-1.0,                # LLM 自评
  }

容错:
- 非 JSON / 解析失败       → 返回原 concept + warning
- 缺字段                  → 已提供字段更新，缺字段保留
- bloom_level 非法         → 忽略此字段 + warning，其他照常
- confidence 越界          → clamp [0,1]
- LLMProvider PLUGIN_NOT_AVAILABLE → 上抛（让调用方决定降级）
"""
from __future__ import annotations

import json
from typing import Any

from shared.errors import TutorError
from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.schemas import Concept, Example

logger = get_logger("knowledge_mcp.concept_enricher")


_BLOOM_VALID = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
_EXAMPLE_VALID = {
    "proof", "computation", "application", "counterexample", "pathological",
}


_SYSTEM = (
    "你是知识工程专家。基于学生的学习笔记片段，把章节标题填充为"
    "结构化的概念定义。只依据文本本身，不臆造，不评判。"
    "所有输出为严格合法 JSON。"
)


def _build_prompt(concept: Concept, body_text: str) -> str:
    name = concept.names[0]
    return f"""请把下面这个概念整理为 JSON。只输出 JSON，不要解释。

概念名: {name}
当前抽象层级: {concept.classification.abstract_level}
当前学科域: {concept.classification.domain}

正文（学生笔记原文）:
---
{body_text}
---

请输出（所有字段均可选；不确定就省略）:
{{
  "definition": "概念的精确定义（基于正文，1-3 句）",
  "informal_description": "口语化解释（让初学者懂）",
  "examples": [
    {{"text": "例子描述", "type": "computation|proof|application|counterexample|pathological"}}
  ],
  "common_misconceptions": ["误解1", "误解2"],
  "bloom_level": "remember|understand|apply|analyze|evaluate|create",
  "confidence": 0.0~1.0
}}
"""


def _parse_json(text: str) -> dict[str, Any] | None:
    """宽容 JSON 解析：剥 markdown ``` 围栏 / 找首个 { 到末尾 }。"""
    text = text.strip()
    # 剥 ```json ... ``` 围栏
    if text.startswith("```"):
        lines = text.splitlines()
        # 去掉首尾围栏行
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # 尝试直接解析
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        pass
    # 找首个 { ... } 块
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            out = json.loads(text[start : end + 1])
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class ConceptEnricher:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def enrich(self, *, concept: Concept, body_text: str) -> tuple[Concept, str | None]:
        """返回 (enriched_concept, warning_or_none)。

        warning != None 表示 LLM 调用成功但解析有问题，concept 部分更新（或完全未变）。
        """
        prompt = _build_prompt(concept, body_text)
        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
        except TutorError:
            # PLUGIN_NOT_AVAILABLE 等 — 上抛让调用方决定降级
            raise
        except Exception as exc:  # noqa: BLE001  捕获 LLM SDK 任意异常
            logger.warning("enricher.llm_exception", concept_id=concept.id, error=str(exc))
            return concept, f"LLM 调用异常: {exc}"

        data = _parse_json(resp.content)
        if data is None:
            return concept, f"LLM 返回无法解析为 JSON（前 100 字: {resp.content[:100]!r}）"

        return self._apply(concept, data)

    def _apply(self, concept: Concept, data: dict[str, Any]) -> tuple[Concept, str | None]:
        """把 LLM 数据落到 Concept 字段；返回（新 concept, warning）。"""
        warnings: list[str] = []
        updates: dict[str, Any] = {}

        if "definition" in data and isinstance(data["definition"], str) and data["definition"].strip():
            updates["definition"] = data["definition"].strip()

        if "informal_description" in data and isinstance(data["informal_description"], str):
            updates["informal_description"] = data["informal_description"].strip()

        if "examples" in data and isinstance(data["examples"], list):
            new_examples: list[Example] = []
            for item in data["examples"]:
                if not isinstance(item, dict):
                    continue
                text = item.get("text", "")
                etype = item.get("type", "computation")
                if etype not in _EXAMPLE_VALID:
                    etype = "computation"
                if isinstance(text, str) and text.strip():
                    new_examples.append(Example(text=text.strip(), type=etype))
            if new_examples:
                updates["examples"] = new_examples

        if "common_misconceptions" in data and isinstance(data["common_misconceptions"], list):
            misc = [m.strip() for m in data["common_misconceptions"] if isinstance(m, str) and m.strip()]
            if misc:
                updates["common_misconceptions"] = misc

        if "bloom_level" in data:
            bl = data["bloom_level"]
            if isinstance(bl, str) and bl in _BLOOM_VALID:
                new_class = concept.classification.model_copy(update={"bloom_level": bl})
                updates["classification"] = new_class
            else:
                warnings.append(f"bloom_level={bl!r} 不在合法枚举内，已忽略")

        if "confidence" in data:
            conf = data["confidence"]
            if isinstance(conf, (int, float)):
                updates["confidence"] = _clamp(float(conf))

        enriched = concept.model_copy(update=updates) if updates else concept
        warning = "; ".join(warnings) if warnings else None
        logger.info(
            "enricher.apply",
            concept_id=concept.id,
            applied_fields=list(updates.keys()),
            warnings=warnings,
        )
        return enriched, warning
