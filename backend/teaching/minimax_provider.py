"""backend.teaching.minimax_provider —— MiniMax-M3 真实 LLM provider（OpenAI 兼容）。

把用户部署的 MiniMax API 接成 AI-Tutor 的 LLMProvider：判分 + 内容生成 + 诊断都走真 LLM，
让科目能被**真实**学到完成（而非本地判分器的近似）。

- 端点 OpenAI 兼容：POST {base}/chat/completions，Bearer {MINIMAX_API_KEY}，model=MiniMax-M3。
- MiniMax-M3 是推理模型，回复含 `<think>…</think>`——返回前剥掉，只留正文（判分 JSON）。
- 死系统代理绕法：请求显式 no_proxy（urllib 用空 ProxyHandler）。
- supports_generation=True：真 LLM，ContentGenerator 会用它生成讲解/例子/练习。
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any, ClassVar

from shared.errors import TutorError
from shared.llm_client import ChatResponse, HealthStatus

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
# 直连 opener（空代理）——绕死系统代理（见持久记忆 dead-system-proxy-workaround）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class MiniMaxProvider:
    """MiniMax-M3 LLM provider（真实 LLM）。"""

    category: ClassVar[str] = "llm"
    name: ClassVar[str] = "minimax"
    # 默认 False：内容讲解走模板（快、不卡），把 MiniMax 留给高价值的**判分**（scorer 直接
    # 调 chat，不看此开关）。要 LLM 生成讲解可显式开（慢，~5-55s/步）。
    supports_generation: ClassVar[bool] = False

    def __init__(
        self, *, api_key: str | None = None, base_url: str | None = None,
        model: str = "MiniMax-M3", timeout: float = 90.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.base_url = (base_url or os.environ.get("MINIMAX_BASE_URL")
                         or "https://api.minimaxi.com/v1").rstrip("/")
        self.model = os.environ.get("MINIMAX_MODEL", model)
        self.timeout = timeout
        if not self.api_key:
            raise TutorError("PLUGIN_NOT_AVAILABLE", hint="MINIMAX_API_KEY 未设置")

    @staticmethod
    def available() -> bool:
        return bool(os.environ.get("MINIMAX_API_KEY"))

    def chat(
        self, *, messages: list[dict[str, str]], temperature: float = 0.3,
        max_tokens: int = 1024, **kwargs: Any,
    ) -> ChatResponse:
        # 判分 prompt：要 JSON-only + 低温，最大化可解析性
        msgs = list(messages)
        last = msgs[-1]["content"] if msgs else ""
        is_scoring = isinstance(last, str) and '"correctness"' in last
        if is_scoring:
            msgs = [{"role": "system",
                     "content": "你是判分器。只输出一个 JSON 对象，不要任何解释、不要 markdown 代码块、不要 <think>。"}] + msgs
            temperature = 0.1
        body = json.dumps({
            "model": self.model, "messages": msgs,
            "temperature": temperature, "max_tokens": max(max_tokens, 2048),
        }).encode()
        last_exc: Exception | None = None
        for _attempt in range(2):  # 单次重试：MiniMax 偶发超时
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions", data=body,
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
            )
            try:
                with _OPENER.open(req, timeout=self.timeout) as resp:
                    data = json.load(resp)
                    break
            except Exception as exc:  # 网络/超时/HTTP 错误
                last_exc = exc
        else:
            raise TutorError("LLM_REQUEST_FAILED", hint=str(last_exc)[:200]) from last_exc

        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content") or ""
        content = _THINK.sub("", content).strip()  # 剥推理块
        fence = _FENCE.search(content)  # 剥 ```json ... ``` 代码围栏
        if fence:
            content = fence.group(1).strip()
        usage = data.get("usage") or {}
        return ChatResponse(
            content=content,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
        )

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 3)

    def health(self) -> HealthStatus:
        return HealthStatus(ok=True, reason=f"minimax {self.model}")
