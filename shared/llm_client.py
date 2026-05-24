"""LLM 客户端抽象（L1）。

合同来源: ai-tutor-system-design/specs/llm-cost-control.md

本切片只实现：
- LLMProvider Protocol（chat + count_tokens + health）
- ChatResponse 数据类
- StubLLMProvider — 默认占位；调用即抛 PLUGIN_NOT_AVAILABLE。用于"未配置 API key 时
  系统能启动 + 报清晰错误"
- MockLLMProvider — 测试用，按预设序列返回，记录所有调用

后续切片实现:
- DeepSeekProvider / OpenAIProvider 真实调用
- ThreeTierCache（L1 内存 / L2 SQLite / L3 语义）
- BudgetController（每任务上限 + 全局上限 + 熔断）
- TaskRouter（按 task tier 分级到不同模型）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Protocol, runtime_checkable

from .errors import TutorError
from .plugins import HealthStatus


@dataclass
class ChatResponse:
    content: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"
    raw: dict[str, Any] | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """所有 LLM 后端共同接口。注册进 PluginRegistry 时 category='llm'。"""

    category: ClassVar[str]
    name: ClassVar[str]

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> ChatResponse: ...

    def count_tokens(self, text: str) -> int: ...

    def health(self) -> HealthStatus: ...


# --------------------------------------------------------------------------- #
# Stub: 未配置 provider 时的默认值
# --------------------------------------------------------------------------- #


class StubLLMProvider:
    """没装 / 没配 LLM 时的占位 provider。

    任何 chat 调用都抛 PLUGIN_NOT_AVAILABLE，让上层知道"该走 LLM 但还没接好"。
    """

    category: ClassVar[str] = "llm"
    name: ClassVar[str] = "stub"

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> ChatResponse:
        raise TutorError(
            "PLUGIN_NOT_AVAILABLE",
            hint="LLMProvider 未配置。在 .env 设置 DEEPSEEK_API_KEY 或注册自定义 provider",
        )

    def count_tokens(self, text: str) -> int:
        # 启发式：1 token ≈ 4 字符（英文偏快，中文偏慢）
        return max(1, len(text) // 4)

    def health(self) -> HealthStatus:
        return HealthStatus(ok=False, reason="stub — 未配置真实 provider")


# --------------------------------------------------------------------------- #
# Mock: 测试用
# --------------------------------------------------------------------------- #


@dataclass
class MockLLMProvider:
    """按预设序列返回；记录全部 chat() 调用，便于断言。"""

    canned_responses: list[str] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    _cursor: int = field(default=0, init=False)

    category: ClassVar[str] = "llm"
    name: ClassVar[str] = "mock"

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> ChatResponse:
        self.calls.append({
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        })
        if self._cursor >= len(self.canned_responses):
            raise TutorError(
                "PLUGIN_NOT_AVAILABLE",
                hint=f"MockLLMProvider 已用尽 {len(self.canned_responses)} 个 canned response",
            )
        text = self.canned_responses[self._cursor]
        self._cursor += 1
        return ChatResponse(
            content=text,
            model="mock",
            prompt_tokens=sum(len(m["content"]) // 4 for m in messages),
            completion_tokens=len(text) // 4,
        )

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def health(self) -> HealthStatus:
        remaining = len(self.canned_responses) - self._cursor
        return HealthStatus(ok=remaining > 0, reason=f"剩余 {remaining} 个 canned response")
