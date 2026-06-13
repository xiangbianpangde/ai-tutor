"""非评判防火墙（PGFGA 集成点 2）。

合同来源: ai-tutor-system-design/specs/pgfga-integration.md §三

机制:
- 所有 L6 生成的 TeachingAction.content 在返回前过这道关卡
- 命中六类禁止模式 → FirewallViolation + 建议替代措辞
- 当前切片: 关键词正则
- 后续切片: 语义级（用 LLM 二审）+ 上下文敏感（"不对"在反讽 vs 实质否定的区分）
"""
from __future__ import annotations

import re
from typing import Literal

from shared.schemas import FirewallViolation

# (category, pattern, suggested_fallback)
_RULES: list[tuple[str, str, str]] = [
    # 否定性判断
    ("negation", r"不对|你错了|这不合理|不是这样的", "改为承接思路：'你这里有一个有趣的尝试...我们一起看下细节'"),
    # 评判性语言
    ("judgment", r"想太多|没必要|太幼稚|不成熟|这很简单|你应该知道", "改为情境化：'这个对很多人都是难点，我们慢慢来'"),
    # 说教式口吻
    ("preachy", r"你应该|正确做法是|要知道|你必须|一定要|记住", "改为提问：'你觉得这里下一步可以怎么走？'"),
    # 话题终结
    ("topic_killer", r"^好的[，。\s]*$|^明白了[，。\s]*$|^了解了[，。\s]*$", "如果学生未自然收束，避免使用结束语；改为追问或留白"),
    # 外部空洞夸奖
    ("empty_praise", r"太棒了|你好聪明|你真厉害|你真优秀", "改为精准看见：'你刚才把 X 和 Y 联系起来了，这是 …'"),
    # 话题扭转
    ("topic_shift", r"我们回到|还是聊聊|先不说这个", "顺着学生当前思路走；如果必须切换，先解释为什么"),
]

_COMPILED: list[tuple[str, re.Pattern[str], str]] = [
    (cat, re.compile(p), fb) for cat, p, fb in _RULES
]


Category = Literal["negation", "judgment", "preachy", "topic_killer", "empty_praise", "topic_shift"]


class NonJudgmentFirewall:
    """对外只有 scan + scan_all 两个方法。无状态，可在 server.py 模块级单例。"""

    def scan(self, text: str) -> FirewallViolation | None:
        """命中第一个违规即返回；用于快速拒绝。"""
        if not text:
            return None
        for category, pattern, fallback in _COMPILED:
            m = pattern.search(text)
            if m:
                return FirewallViolation(
                    category=category,  # type: ignore[arg-type]
                    matched_pattern=m.group(0),
                    suggested_fallback=fallback,
                )
        return None

    def scan_all(self, text: str) -> list[FirewallViolation]:
        """全部违规列表；用于反馈给 prompt designer 的修正建议。"""
        out: list[FirewallViolation] = []
        if not text:
            return out
        for category, pattern, fallback in _COMPILED:
            for m in pattern.finditer(text):
                out.append(
                    FirewallViolation(
                        category=category,  # type: ignore[arg-type]
                        matched_pattern=m.group(0),
                        suggested_fallback=fallback,
                    )
                )
        return out
