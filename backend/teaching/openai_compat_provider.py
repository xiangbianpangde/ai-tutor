"""backend.teaching.openai_compat_provider —— 通用 OpenAI 兼容 LLM provider。

让用户在设置页填任意 OpenAI 兼容端点（DeepSeek / OpenAI / 智谱 / 本地
Ollama·vLLM…）即可热接入教学管线：``POST {base_url}/chat/completions``，
Bearer 鉴权，解析 choices[0].message.content，剥 ``<think>`` 推理块与
```` ```json ```` 围栏（与 MiniMaxProvider 同一套清洗）。

- urllib 直连（空代理 opener，与 MiniMaxProvider 同一绕法），无 SDK 依赖。
- API key 只存本对象内存；``describe()`` 返回打码形态供设置页回显，
  任何日志/错误路径都不得输出完整 key。
- base_url 由用户显式配置；scheme 限定 http/https（本地 Ollama/vLLM 的
  http://localhost 是合法场景，属用户自配端点的有意豁免）。
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Any, ClassVar
from urllib.parse import urlsplit

from shared.errors import TutorError
from shared.llm_client import ChatResponse, HealthStatus

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _validate_base_url(base_url: str) -> str:
    """只接受 http/https 绝对地址；返回去尾斜杠的规范形态。"""
    trimmed = (base_url or "").strip().rstrip("/")
    parts = urlsplit(trimmed)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise TutorError(
            "LLM_CONFIG_INVALID",
            hint=f"base_url 必须是 http/https 绝对地址，收到：{base_url!r}",
        )
    return trimmed


def mask_key(api_key: str) -> str:
    """打码 API key：只留前 3 与后 4 位。"""
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:3]}***{api_key[-4:]}"


class OpenAICompatProvider:
    """用户自配的 OpenAI 兼容 LLM provider（运行时热替换）。"""

    category: ClassVar[str] = "llm"
    name: ClassVar[str] = "openai_compat"
    supports_generation: ClassVar[bool] = True

    def __init__(
        self, *, api_key: str, base_url: str, model: str,
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise TutorError("LLM_CONFIG_INVALID", hint="API key 不能为空")
        if not model:
            raise TutorError("LLM_CONFIG_INVALID", hint="model 不能为空")
        self.api_key = api_key
        self.base_url = _validate_base_url(base_url)
        self.model = model
        self.timeout = timeout

    def describe(self) -> dict[str, str]:
        """脱敏描述（设置页回读用）；永不含完整 key。"""
        return {
            "provider": self.name,
            "base_url": self.base_url,
            "model": self.model,
            "api_key_masked": mask_key(self.api_key),
        }

    def chat(
        self, *, messages: list[dict[str, str]], temperature: float = 0.3,
        max_tokens: int = 1024, **kwargs: Any,
    ) -> ChatResponse:
        body = json.dumps({
            "model": self.model, "messages": list(messages),
            "temperature": temperature, "max_tokens": max(max_tokens, 1024),
        }).encode()
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )
        try:
            with _OPENER.open(request, timeout=self.timeout) as resp:
                data = json.load(resp)
        except Exception as exc:
            # hint 只带异常类型与首行，绝不含请求头（防 key 外泄）
            raise TutorError(
                "LLM_REQUEST_FAILED",
                hint=f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}",
            ) from exc
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        content = _THINK.sub("", content).strip()
        fence = _FENCE.search(content)
        if fence:
            content = fence.group(1).strip()
        usage = data.get("usage") or {}
        return ChatResponse(
            content=content,
            model=str(data.get("model") or self.model),
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
        )

    def ping(self) -> dict[str, Any]:
        """最小连通性探测：一条 1-token 消息，返回模型与延迟毫秒。"""
        started = time.perf_counter()
        response = self.chat(
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.0, max_tokens=1,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return {"ok": True, "model": response.model or self.model,
                "latency_ms": elapsed_ms}

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 3)

    def health(self) -> HealthStatus:
        return HealthStatus(ok=True, reason=f"openai_compat {self.model}")
