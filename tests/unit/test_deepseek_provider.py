"""DeepSeekProvider 契约测试。

DeepSeek 提供 OpenAI 兼容接口，所以用 openai SDK 即可。
为避免真实 API 调用，全部 mock openai.OpenAI 客户端。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.errors import TutorError


def _make_mock_openai_response(content: str, ptokens: int = 5, ctokens: int = 7) -> MagicMock:
    """模拟 openai SDK 的 chat.completions.create 返回值。"""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "stop"
    usage = MagicMock()
    usage.prompt_tokens = ptokens
    usage.completion_tokens = ctokens
    resp = MagicMock()
    resp.choices = [choice]
    resp.model = "deepseek-chat"
    resp.usage = usage
    return resp


def test_provider_implements_llm_provider() -> None:
    from shared.llm_client import LLMProvider
    from shared.providers.deepseek import DeepSeekProvider

    p = DeepSeekProvider(api_key="sk-x", base_url="https://x", model="deepseek-chat")
    assert isinstance(p, LLMProvider)
    assert p.category == "llm"
    assert p.name == "deepseek"


def test_chat_calls_openai_with_correct_params() -> None:
    from shared.providers.deepseek import DeepSeekProvider

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _make_mock_openai_response("hi")

    with patch("shared.providers.deepseek.OpenAI", return_value=fake_client):
        p = DeepSeekProvider(api_key="sk-x", base_url="https://api.deepseek.com", model="deepseek-chat")
        resp = p.chat(
            messages=[{"role": "user", "content": "你好"}],
            temperature=0.2,
            max_tokens=512,
        )

    assert resp.content == "hi"
    assert resp.model == "deepseek-chat"
    assert resp.prompt_tokens == 5
    assert resp.completion_tokens == 7

    call = fake_client.chat.completions.create.call_args
    assert call.kwargs["model"] == "deepseek-chat"
    assert call.kwargs["temperature"] == 0.2
    assert call.kwargs["max_tokens"] == 512
    assert call.kwargs["messages"] == [{"role": "user", "content": "你好"}]


def test_chat_wraps_openai_errors_in_tutor_error() -> None:
    """openai SDK 抛任意异常 → 包装为 PLUGIN_NOT_AVAILABLE TutorError。"""
    from shared.providers.deepseek import DeepSeekProvider

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("network down")

    with patch("shared.providers.deepseek.OpenAI", return_value=fake_client):
        p = DeepSeekProvider(api_key="sk-x", base_url="https://x", model="deepseek-chat")
        with pytest.raises(TutorError) as exc:
            p.chat(messages=[{"role": "user", "content": "x"}])
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"
    assert "deepseek" in (exc.value.hint or "").lower() or "network" in (exc.value.hint or "").lower()


def test_health_returns_ok_when_constructed() -> None:
    from shared.providers.deepseek import DeepSeekProvider

    p = DeepSeekProvider(api_key="sk-x", base_url="https://x", model="deepseek-chat")
    # 不实际调网络；提供 api_key + base_url 就算"可达"
    assert p.health().ok is True


def test_health_unhealthy_when_no_key() -> None:
    from shared.providers.deepseek import DeepSeekProvider

    p = DeepSeekProvider(api_key="", base_url="https://x", model="deepseek-chat")
    h = p.health()
    assert h.ok is False
    assert "api_key" in (h.reason or "").lower() or "key" in (h.reason or "").lower()


def test_count_tokens_estimates() -> None:
    from shared.providers.deepseek import DeepSeekProvider

    p = DeepSeekProvider(api_key="sk-x", base_url="https://x", model="deepseek-chat")
    n = p.count_tokens("hello 你好 world")
    assert 1 <= n <= 20


def test_from_env_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """DeepSeekProvider.from_env() 从环境装配；没 key 时返回 None。"""
    from shared.providers.deepseek import DeepSeekProvider

    # 没 key
    for k in ("DEEPSEEK_API_KEY", "Deepseek_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert DeepSeekProvider.from_env() is None

    # 有 key
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-y")
    p = DeepSeekProvider.from_env()
    assert p is not None
    assert p.name == "deepseek"
