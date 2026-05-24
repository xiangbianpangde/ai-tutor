"""DeepSeekProvider — 通过 OpenAI 兼容接口调 DeepSeek。

DeepSeek 完全兼容 OpenAI SDK，只需要把 base_url 改成 https://api.deepseek.com
即可。本 provider 实现 LLMProvider Protocol，可注册到 PluginRegistry。

后续切片可加: 流式输出、tool calling、JSON mode、上下文缓存。
"""
from __future__ import annotations

from typing import Any, ClassVar

from openai import OpenAI

from shared.config import get_deepseek_config
from shared.errors import TutorError
from shared.llm_client import ChatResponse
from shared.logging_config import get_logger
from shared.plugins import HealthStatus

logger = get_logger("shared.providers.deepseek")


class DeepSeekProvider:
    category: ClassVar[str] = "llm"
    name: ClassVar[str] = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        # 仅当 api_key 非空时构建客户端；空 key 留给 health() 报错
        self._client = (
            OpenAI(api_key=api_key, base_url=base_url) if api_key else None
        )

    @classmethod
    def from_env(cls) -> "DeepSeekProvider | None":
        cfg = get_deepseek_config()
        if cfg is None:
            return None
        return cls(api_key=cfg["api_key"], base_url=cfg["base_url"], model=cfg["model"])

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> ChatResponse:
        if self._client is None:
            raise TutorError(
                "PLUGIN_NOT_AVAILABLE",
                hint="DeepSeekProvider 未初始化（缺 api_key）",
            )
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001  捕获 openai SDK 任意异常
            logger.warning("deepseek.chat_failed", error=str(exc), model=self.model)
            raise TutorError(
                "PLUGIN_NOT_AVAILABLE",
                hint=f"DeepSeek 调用失败: {type(exc).__name__}: {exc}",
            ) from exc

        choice = resp.choices[0] if resp.choices else None
        content = (choice.message.content if choice else "") or ""
        usage = getattr(resp, "usage", None)
        return ChatResponse(
            content=content,
            model=getattr(resp, "model", self.model) or self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            finish_reason=getattr(choice, "finish_reason", "stop") or "stop",
        )

    def count_tokens(self, text: str) -> int:
        # 启发式：中文按字符算，英文按 4 字符/token
        return max(1, len(text) // 4)

    def health(self) -> HealthStatus:
        if not self.api_key:
            return HealthStatus(ok=False, reason="缺少 api_key")
        if self._client is None:
            return HealthStatus(ok=False, reason="客户端未初始化")
        return HealthStatus(
            ok=True, extra={"base_url": self.base_url, "model": self.model}
        )
