"""教学反馈分级 (P1 #7) — 反馈三级管道的 L3：LLM 润色。

问题（SYSTEM-AUDIT #8）：respond 的反馈只有 3 个模板（correct/partial/incorrect），
粗粒度、不针对学生的具体答案。

三级管道（在 engine.respond 里组合）：
  L1 — 按 correctness 的基础模板（engine._build_raw_feedback）
  L2 — 叠加错误诊断的 remediation（针对性下一步，仍是模板，已在 _build_raw_feedback）
  L3 — 本模块：把 L1+L2 的产物 + 学生答案 + 判分证据，用 LLM 润色成温暖、具体、
       非评判的反馈。失败/不可用 → 原样返回传入的 L1+L2 模板（fallback）。

与 ContentGenerator 同构：仅当 provider.supports_generation 为真才调 LLM，使 Mock/Stub
驱动的既有 respond 测试完全不受影响。润色结果仍由 engine 过非评判防火墙（最后兜底）。
"""
from __future__ import annotations

from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.schemas import Concept

logger = get_logger("tutoring_mcp.feedback_generator")

_SYSTEM = (
    "你是一位温暖、敏锐的学科老师，给学生即时反馈。"
    "原则：先精准看见学生答案里对的部分，再点出关键；语气平等、具体，不评判人格。"
    "禁止：'不对/你错了'、'你应该/记住/正确做法是'、'太棒了/你真聪明' 这类否定、说教或空洞夸奖。"
    "直接输出反馈本身，1-3 句，中文，不要寒暄、不要复述指令。"
)

# correctness → 反馈任务说明
_TASK = {
    "correct": "学生答对了。精准指出 ta 抓住的关键点，并自然地推进到下一步。",
    "partial": "学生答了一部分。先承接 ta 对的地方，再温和地补上缺的关键，给一个具体的下一步。",
    "incorrect": "学生这次没答对。先承认 ta 的思考/尝试，不否定，再换个角度引导，给一个具体可走的下一步。",
}


class FeedbackGenerator:
    """反馈 L3：LLM 润色。无真实 LLM 时返回传入的模板 fallback。"""

    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def _build_prompt(
        self, *, correctness: str, concept: Concept,
        student_answer: str, evidence: str, remediation: str,
    ) -> str:
        task = _TASK.get(correctness, _TASK["partial"])
        return (
            f"概念：{concept.names[0]}\n"
            f"定义：{concept.definition}\n"
            f"学生的答案：{student_answer or '（空）'}\n"
            f"判分证据：{evidence or '（无）'}\n"
            f"建议的下一步：{remediation or '（无）'}\n"
            f"反馈任务：{task}"
        )

    def generate(
        self,
        *,
        correctness: str,
        concept: Concept,
        student_answer: str,
        evidence: str = "",
        remediation: str = "",
        fallback: str,
    ) -> str:
        """返回 LLM 润色后的反馈；不可用/失败/空 → 返回 fallback（L1+L2 模板）。"""
        if not getattr(self.llm, "supports_generation", False) or concept is None or not concept.names:
            return fallback

        prompt = self._build_prompt(
            correctness=correctness, concept=concept,
            student_answer=student_answer, evidence=evidence, remediation=remediation,
        )
        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=300,
            )
        except Exception as exc:  # noqa: BLE001 — 反馈生成失败绝不中断教学
            logger.info("feedback_gen.fallback", reason=str(exc), correctness=correctness)
            return fallback

        content = (resp.content or "").strip()
        return content or fallback
