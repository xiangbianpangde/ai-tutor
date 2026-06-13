"""RelationExtractor — 从已富化的概念集合中抽取「非结构类」语义关系。

背景:
  结构类关系已由 _build_toc 从章节层级/顺序产出：
    - part_of            ← 章节嵌套
    - prerequisite_strong ← 同级前后顺序
  其余 10 种 SemanticRelation 需要看「概念对」的语义才能判定，单概念富化
  (ConceptEnricher) 看不到概念对，故单列一个抽取器，用一次 LLM 调用基于
  全体概念的定义推断关系。

调用契约:
  extractor = RelationExtractor(llm=llm_provider)
  new_edges, warnings = extractor.extract(concepts=enriched, existing_edges=structural)

LLM 期望返回 JSON:
  {"relations": [
     {"from": "<concept_id>", "to": "<concept_id>", "type": "is_a",
      "weight": 0.0-1.0, "explanation": "一句话依据", "confidence": 0.0-1.0}
  ]}

容错（全程不抛错，关系是「增强」而非「必需」——结构边已保证连通性）:
- LLM 不可用 / 任意异常       → 返回 ([], [warning])，构建继续用结构边
- 非 JSON / 解析失败          → ([], [warning])
- 非法 type / from-to 无法解析 / 自环 / 与已有边重复 → 跳过该条 + warning
- 概念数 > _MAX_CONCEPTS      → 跳过抽取 + warning（v1 面向 15-30 概念的教材规模；
                                大图需窗口化分批，留后续切片）
"""
from __future__ import annotations

import json
from typing import Any, get_args

from pydantic import ValidationError

from shared.errors import TutorError
from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.schemas import Concept, Relation, SemanticRelation

logger = get_logger("knowledge_mcp.relation_extractor")

# 全部 12 种关系；其中两种由结构生成，抽取时不强求（出现也会被去重）。
_VALID_RELATIONS: set[str] = set(get_args(SemanticRelation))
_STRUCTURAL: set[str] = {"part_of", "prerequisite_strong"}

# v1 规模上限：超过则跳过（避免 O(n) 概念塞进一个 prompt 失控）。
_MAX_CONCEPTS: int = 80
_DEF_PREVIEW: int = 120  # 每个概念喂给 prompt 的定义截断长度

_SYSTEM = (
    "你是知识工程专家。基于概念的定义，判定概念之间的语义关系。"
    "只在有明确文本依据时建立关系，宁缺毋滥，不臆造。"
    "所有输出为严格合法 JSON。"
)

# 给 LLM 的关系类型说明（侧重非结构关系）。
_RELATION_GUIDE = """\
- is_a: A 是 B 的一种（分类从属）
- prerequisite_weak: 懂 A 有助于但非必须先于 B
- analogous_to: A 与 B 结构类比
- contradicts: A 与 B 互斥/对立
- generalizes: A 是 B 的推广
- instantiates: A 是 B 的具体实例
- proves: A 用于证明 B
- computed_from: A 由 B 计算得到
- common_pitfall: 学 B 时常在 A 上犯错
- historical_origin: A 是 B 的历史来源"""


def _build_prompt(concepts: list[Concept]) -> str:
    lines = []
    for c in concepts:
        definition = (c.definition or "").replace("\n", " ").strip()
        if len(definition) > _DEF_PREVIEW:
            definition = definition[:_DEF_PREVIEW] + "…"
        lines.append(f"- {c.id}: {c.names[0]} — {definition}")
    concept_block = "\n".join(lines)
    return f"""请标注下列概念之间的语义关系。只输出 JSON，不要解释。

层级关系(part_of)与教材顺序(prerequisite_strong)已自动生成，**无需重复**，
请专注下列其余关系类型：
{_RELATION_GUIDE}

概念列表（用 id 引用）:
{concept_block}

输出格式:
{{"relations": [
  {{"from": "<id>", "to": "<id>", "type": "<上面的关系类型>", "weight": 0.0~1.0, "explanation": "一句话依据", "confidence": 0.0~1.0}}
]}}

要求: from/to 必须是上面列出的 id；没有把握的关系不要输出；可以返回空列表 {{"relations": []}}。
"""


def _parse_json(text: str) -> dict[str, Any] | None:
    """宽容 JSON 解析：剥 markdown 围栏 / 取首个 {…} 块。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            out = json.loads(text[start : end + 1])
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


class RelationExtractor:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def extract(
        self, *, concepts: list[Concept], existing_edges: list[Relation]
    ) -> tuple[list[Relation], list[str]]:
        """返回 (new_relations, warnings)。绝不抛错——失败即降级为无新关系。"""
        if len(concepts) < 2:
            return [], []
        if len(concepts) > _MAX_CONCEPTS:
            msg = f"概念数 {len(concepts)} > {_MAX_CONCEPTS}，v1 跳过关系抽取（结构边保留）"
            logger.info("relation_extract.skip_large", n=len(concepts))
            return [], [msg]

        prompt = _build_prompt(concepts)
        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
        except TutorError as exc:
            # 关系是增强项：即便 LLM 此刻不可用也不让整个 build 失败（富化阶段已证明
            # LLM 可用；这里多半是瞬时/额度问题）。降级为只有结构边。
            logger.warning("relation_extract.llm_unavailable", code=exc.code)
            return [], [f"关系抽取跳过（LLM: {exc.code}）"]
        except Exception as exc:  # noqa: BLE001  捕获 LLM SDK 任意异常
            logger.warning("relation_extract.llm_exception", error=str(exc))
            return [], [f"关系抽取跳过（LLM 异常: {exc}）"]

        data = _parse_json(resp.content)
        if data is None or not isinstance(data.get("relations"), list):
            return [], [f"关系抽取返回无法解析（前 80 字: {resp.content[:80]!r}）"]

        return self._build_relations(data["relations"], concepts, existing_edges)

    def _build_relations(
        self,
        raw: list[Any],
        concepts: list[Concept],
        existing_edges: list[Relation],
    ) -> tuple[list[Relation], list[str]]:
        id_set = {c.id for c in concepts}
        # 名称 → id（用于 LLM 偶尔返回 name 而非 id 的兜底）
        name_to_id: dict[str, str] = {}
        for c in concepts:
            for nm in c.names:
                name_to_id.setdefault(nm.strip(), c.id)

        # 去重键：(from, to, type)，含结构边与本批已加入的
        seen: set[tuple[str, str, str]] = {
            (e.from_id, e.to_id, e.type) for e in existing_edges
        }

        out: list[Relation] = []
        warnings: list[str] = []

        def _resolve(ref: Any) -> str | None:
            if not isinstance(ref, str):
                return None
            ref = ref.strip()
            if ref in id_set:
                return ref
            return name_to_id.get(ref)

        for item in raw:
            if not isinstance(item, dict):
                continue
            rtype = item.get("type")
            if rtype not in _VALID_RELATIONS:
                warnings.append(f"丢弃非法关系类型 {rtype!r}")
                continue
            from_id = _resolve(item.get("from"))
            to_id = _resolve(item.get("to"))
            if from_id is None or to_id is None:
                warnings.append(
                    f"丢弃无法解析端点的关系 {item.get('from')!r}->{item.get('to')!r}"
                )
                continue
            if from_id == to_id:
                continue  # 自环，静默跳过（Relation 也会拒绝）
            key = (from_id, to_id, rtype)
            if key in seen:
                continue  # 与结构边或本批已有重复
            weight = item.get("weight", 0.6)
            conf = item.get("confidence", 0.6)
            explanation = item.get("explanation")
            if not isinstance(explanation, str) or not explanation.strip():
                explanation = f"LLM 推断的 {rtype} 关系"
            try:
                rel = Relation(
                    from_id=from_id,
                    to_id=to_id,
                    type=rtype,  # type: ignore[arg-type]  已对照 _VALID_RELATIONS
                    weight=_clamp(float(weight)) if isinstance(weight, int | float) else 0.6,
                    explanation=explanation.strip(),
                    confidence=_clamp(float(conf)) if isinstance(conf, int | float) else 0.6,
                )
            except (ValidationError, ValueError, TypeError) as exc:
                warnings.append(f"丢弃非法关系 {from_id}->{to_id} ({rtype}): {exc}")
                continue
            out.append(rel)
            seen.add(key)

        logger.info(
            "relation_extract.done",
            extracted=len(out),
            warnings=len(warnings),
        )
        return out, warnings
