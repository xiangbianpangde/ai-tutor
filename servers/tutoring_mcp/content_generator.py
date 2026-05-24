"""教学内容生成 (P0 #1) — 用 LLM 把"模板填空"的教学动作改写成真实讲解内容。

问题（SYSTEM-AUDIT #1）：策略状态机产出的 TeachingAction.content 是模板填空
（`f"{name} 的核心定义：{t.definition}"`），举不出例子、做不出类比、没有逐步推导。

做法：引擎拿到策略产出的 action 后，调 ContentGenerator.enrich() 用 LLM 按
action.type 重写 content（讲解配直觉+例子；练习给真题；提示给针对性引导……）。
- 仅当 provider.supports_generation 为 True（真实 LLM）时才调用；否则原样返回
  （模板兜底）——这让 Stub/Mock 驱动的测试完全不受影响。
- 任何失败（不可用 / 异常 / 空返回）都回退到原模板 content，绝不让教学中断。

定位：本模块独立于具体策略，按 action.type 工作，所以 6 种策略的讲解类动作都受益。
反馈分级（respond 的 feedback）是另一件事（P1 #7），不在此处。
"""
from __future__ import annotations

from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.schemas import Concept, TeachingAction

logger = get_logger("tutoring_mcp.content_generator")

# 这些动作类型值得用 LLM 生成真实内容；元动作（休息/反思/检查点/复习提示）保持模板
_ENRICHABLE = frozenset({
    "explain", "show_example", "give_exercise",
    "provide_hint", "ask_question", "reveal_answer",
})

_SYSTEM = (
    "你是一位优秀的学科老师，讲解清晰、具体、善用例子和直觉。"
    "直接输出教学内容本身，不要寒暄、不要复述指令、不要用 markdown 标题。"
)

# action.type → 任务说明
_TASK: dict[str, str] = {
    "explain": "讲解这个概念：先给一句话直觉，再用一个具体例子点明它解决什么问题。",
    "show_example": "给出一个具体的、可跟着算/跟着想的例子来阐明这个概念。",
    "give_exercise": "出一道检验该概念理解的练习题（只出题，不给答案）。",
    "provide_hint": "针对这个概念给一条不直接给答案的引导性提示。",
    "ask_question": "提出一个能检验学生是否真正理解该概念的问题（只问，不答）。",
    "reveal_answer": "清楚地讲清该概念的标准答案/定义，并点出最关键的一点。",
}


def _scaffold_hint(level: int) -> str:
    if level >= 3:
        return "学生需要最多支撑：多给铺垫、把步骤拆细、配前置回顾。"
    if level >= 1:
        return "给适度引导，保留一点让学生自己思考的空间。"
    return "学生能力强：简洁直接，可适当延伸挑战，少铺垫。"


class ContentGenerator:
    """把模板动作改写成 LLM 生成的真实教学内容。"""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def _build_prompt(self, action: TeachingAction, concept: Concept, scaffold_level: int) -> str:
        name = concept.names[0]
        task = _TASK.get(action.type, "讲解这个概念。")
        misconceptions = "；".join(concept.common_misconceptions[:3]) or "（无）"
        return (
            f"概念：{name}\n"
            f"定义：{concept.definition}\n"
            f"通俗解释：{concept.informal_description or '（无）'}\n"
            f"常见误解：{misconceptions}\n"
            f"教学指令：{task}\n"
            f"分寸：{_scaffold_hint(scaffold_level)}\n"
            f"控制在 4 句话以内，用中文。"
        )

    def enrich(
        self,
        *,
        action: TeachingAction,
        concept: Concept,
        scaffold_level: int = 1,
    ) -> TeachingAction:
        """返回内容被 LLM 改写后的新 action；不可用/失败时原样返回。"""
        if not getattr(self.llm, "supports_generation", False):
            return action
        if action.type not in _ENRICHABLE or concept is None or not concept.names:
            return action

        prompt = self._build_prompt(action, concept, scaffold_level)
        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=400,
            )
        except Exception as exc:  # noqa: BLE001 — 生成失败绝不中断教学
            logger.info("content_gen.fallback", reason=str(exc), action_type=action.type)
            return action

        content = (resp.content or "").strip()
        if not content:
            return action

        return action.model_copy(
            update={
                "content": content,
                "metadata": {**action.metadata, "generated": True},
            }
        )
