"""backend.teaching.local_judge —— 无真 LLM 时的本地确定性判分 provider。

为什么需要：全流程测"完全学完一个科目"时发现——没配 API key 时教学循环卡死在
CHECK：FIX-L 让**回退启发式永不授 correct**（防含名废话冒充掌握），但这也意味着无 key
时**任何概念都过不了 CHECK→无限 EXPLAIN→CHECK 循环，科目永远学不完**。

本 provider 作为"基础模式"判分器：以 LLMProvider 形式注入教学引擎，只接管**判分**
（识别判分 prompt → 按答案对概念定义的 2-gram 覆盖度确定性打分，substantive 答案可达
correct），其余调用（内容生成/诊断…）抛 PLUGIN_NOT_AVAILABLE 让上层走各自模板回退，
与 StubLLM 一致。真实部署配了 DeepSeek 则不用它。

相对 FIX-L 启发式：它是**注入的 provider 主路径**（非 fallback），可授 correct；但保持
克制——correct 需实打实的定义覆盖 + 足够长度，避免 fluff 冒充掌握。
"""
from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from shared.errors import TutorError
from shared.llm_client import ChatResponse, HealthStatus

# correct 门槛：定义 2-gram 命中数 + 答案最小实义长度（克制，防 fluff）
_CORRECT_HITS = 4
_CORRECT_MIN_LEN = 12
_PARTIAL_HITS = 2


def _ngrams(text: str, n: int = 2) -> set[str]:
    t = (text or "").strip()
    return {t[i : i + n] for i in range(len(t) - n + 1)} if len(t) >= n else ({t} if t else set())


def _extract(prompt: str, label: str) -> str:
    """从判分 prompt 抠出某字段（"官方定义: …" / "学生答案: …"）到行尾。"""
    m = re.search(rf"{re.escape(label)}\s*[:：]\s*(.*)", prompt)
    return m.group(1).strip() if m else ""


class LocalJudgeProvider:
    """本地确定性判分 provider（基础模式）。只判分，其余委派 Stub 行为。"""

    category: ClassVar[str] = "llm"
    name: ClassVar[str] = "local-judge"
    supports_generation: ClassVar[bool] = False  # 内容生成仍走模板，不用本判分器

    def chat(
        self, *, messages: list[dict[str, str]], temperature: float = 0.3,
        max_tokens: int = 1024, **kwargs: Any,
    ) -> ChatResponse:
        content = messages[-1]["content"] if messages else ""
        # 仅接管判分 prompt（_build_prompt 含"判断学生答案"+要求 correctness）
        if "判断学生答案" in content and "correctness" in content:
            return self._judge(content)
        # 其余（内容生成/诊断/意图）→ 与 Stub 一致抛出，让上层走模板回退
        raise TutorError("PLUGIN_NOT_AVAILABLE", hint="local-judge 只判分")

    def _judge(self, prompt: str) -> ChatResponse:
        definition = _extract(prompt, "官方定义")
        informal = _extract(prompt, "通俗解释")
        answer = _extract(prompt, "学生答案")
        question = _extract(prompt, "题目")

        if not answer or answer in ("(无)", "（无）"):
            return self._resp("incorrect", 0.0, "空答案或未作答")

        a_grams = _ngrams(answer)
        content_grams = _ngrams(definition) | _ngrams(informal)
        hits = len(a_grams & content_grams)
        substantive = len(answer.strip()) >= _CORRECT_MIN_LEN

        # 答非所问保护（与 LLM 主路径同精神）：有题目但答案与题目几乎无关 → 压 partial
        if question and question not in ("(无)", "（无）"):
            q_overlap = len(a_grams & _ngrams(question))
            if q_overlap == 0 and hits < _CORRECT_HITS:
                return self._resp("partial", 0.55, "答案与题目关联弱，未正面回应")

        if hits >= _CORRECT_HITS and substantive:
            return self._resp("correct", 0.85, f"覆盖定义核心要点（命中 {hits} 处）")
        if hits >= _PARTIAL_HITS:
            return self._resp("partial", 0.6, f"部分要点对，覆盖 {hits} 处但不充分")
        return self._resp("incorrect", 0.3, "未命中概念定义要点")

    @staticmethod
    def _resp(correctness: str, score: float, evidence: str) -> ChatResponse:
        body = json.dumps(
            {
                "correctness": correctness,
                "raw_score": score,
                "evidence": evidence,
                "suggested_remediation": "" if correctness == "correct" else "再回顾定义的关键点",
            },
            ensure_ascii=False,
        )
        return ChatResponse(content=body, prompt_tokens=0, completion_tokens=0)

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def health(self) -> HealthStatus:
        return HealthStatus(ok=True, reason="local-judge（基础模式确定性判分）")
