"""L1 内存缓存（LRU）— 透明地装饰任意 LLMProvider。

合同来源: ai-tutor-system-design/specs/llm-cost-control.md 的三级缓存设计。
当前切片只实现 L1（内存）。L2（SQLite）和 L3（语义近邻）留下切片。

用法:
    inner = DeepSeekProvider.from_env()
    llm = CachedLLMProvider(inner=inner, max_size=256)
    llm.chat(messages=[...])  # 第一次调底层，之后同 messages 命中缓存

为什么不直接给所有 provider 加 cache：保持 SRP，让 cache 可独立选用/关闭/换层级。
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from typing import Any, ClassVar

from .llm_client import ChatResponse, LLMProvider
from .plugins import HealthStatus


def _make_key(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> str:
    """稳定的缓存键。用 sha1(json) 避免长键。"""
    payload = json.dumps(
        {"m": model, "msgs": messages, "t": temperature, "n": max_tokens},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class CachedLLMProvider:
    """LRU 装饰器；实现 LLMProvider Protocol。"""

    category: ClassVar[str] = "llm"
    name: ClassVar[str] = "cached"

    def __init__(self, *, inner: LLMProvider, max_size: int = 256) -> None:
        self.inner = inner
        self.max_size = max_size
        self._cache: OrderedDict[str, ChatResponse] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @property
    def supports_generation(self) -> bool:
        """缓存层的生成能力 = 被包装 provider 的能力。"""
        return bool(getattr(self.inner, "supports_generation", False))

    def _model_name(self) -> str:
        return getattr(self.inner, "model", "") or getattr(self.inner, "name", "unknown")

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> ChatResponse:
        key = _make_key(self._model_name(), messages, temperature, max_tokens)

        if key in self._cache:
            self._cache.move_to_end(key)  # LRU touch
            self._hits += 1
            return self._cache[key]

        # miss: 调底层（异常透传，不缓存）
        resp = self.inner.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self._misses += 1
        self._cache[key] = resp
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)  # 淘汰最旧
        return resp

    def count_tokens(self, text: str) -> int:
        return self.inner.count_tokens(text)

    def health(self) -> HealthStatus:
        return self.inner.health()

    def stats(self) -> dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "max_size": self.max_size,
        }

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0
