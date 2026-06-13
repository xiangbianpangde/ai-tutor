"""LLMProvider Protocol + 默认 stub 的契约测试。

合同来源:
  ai-tutor-system-design/specs/llm-cost-control.md (分级 / 缓存 / 熔断 / 预算)
  本切片只实现：
    - LLMProvider Protocol（chat、count_tokens）
    - StubLLMProvider（无 API key 时的默认；调用即抛 PLUGIN_NOT_AVAILABLE）
    - MockLLMProvider（测试用：返回预设回复）
  后续切片实现：DeepSeekProvider 真实调用 + 三级缓存 + 预算
"""
from __future__ import annotations

import pytest

from shared.errors import TutorError


def test_stub_provider_chat_raises() -> None:
    from shared.llm_client import StubLLMProvider

    provider = StubLLMProvider()
    with pytest.raises(TutorError) as exc:
        provider.chat(messages=[{"role": "user", "content": "x"}])
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"
    assert "未配置" in (exc.value.hint or "") or "未配置" in exc.value.message


def test_mock_provider_returns_canned() -> None:
    from shared.llm_client import MockLLMProvider

    provider = MockLLMProvider(canned_responses=["A", "B"])
    r1 = provider.chat(messages=[{"role": "user", "content": "q1"}])
    r2 = provider.chat(messages=[{"role": "user", "content": "q2"}])
    assert r1.content == "A"
    assert r2.content == "B"


def test_mock_provider_records_calls() -> None:
    """Mock 必须记录调用历史，便于测试断言。"""
    from shared.llm_client import MockLLMProvider

    provider = MockLLMProvider(canned_responses=["x"])
    provider.chat(messages=[{"role": "user", "content": "hello"}])
    assert len(provider.calls) == 1
    assert provider.calls[0]["messages"][0]["content"] == "hello"


def test_count_tokens_rough_estimate() -> None:
    """count_tokens 用最简启发式（字符数 / 4），具体 tokenizer 后续切片接入。"""
    from shared.llm_client import StubLLMProvider

    provider = StubLLMProvider()
    n = provider.count_tokens("hello world")
    assert 1 <= n <= 11  # 粗略估计区间


def test_provider_health_status() -> None:
    from shared.llm_client import MockLLMProvider, StubLLMProvider

    assert StubLLMProvider().health().ok is False
    assert MockLLMProvider(canned_responses=["x"]).health().ok is True


def test_provider_implements_plugin_protocol() -> None:
    """LLMProvider 必须能注册进 PluginRegistry。"""
    from shared.llm_client import MockLLMProvider
    from shared.plugins import Plugin, PluginRegistry

    p = MockLLMProvider(canned_responses=["x"])
    assert isinstance(p, Plugin)

    reg = PluginRegistry()
    reg.register(p)
    out = reg.get("llm")
    assert out.name == "mock"
