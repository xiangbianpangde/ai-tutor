"""LRU L1 内存缓存契约测试。

CachedLLMProvider 包装任意 LLMProvider:
- 相同 (model, messages, temperature, max_tokens) → 命中缓存，不调底层 chat()
- 不同 messages → 调用底层 + 缓存
- 超过 max_size → LRU 淘汰最久未用
- stats() 返回 hits / misses 计数

后续切片: L2 SQLite 持久化 / L3 语义缓存（embedding 近邻匹配）。
"""
from __future__ import annotations

import pytest

from shared.llm_client import MockLLMProvider


def test_cache_hit_avoids_underlying_call() -> None:
    from shared.llm_cache import CachedLLMProvider

    inner = MockLLMProvider(canned_responses=["A", "B", "C"])
    cached = CachedLLMProvider(inner=inner, max_size=10)

    r1 = cached.chat(messages=[{"role": "user", "content": "hi"}])
    r2 = cached.chat(messages=[{"role": "user", "content": "hi"}])
    assert r1.content == "A"
    assert r2.content == "A"
    assert len(inner.calls) == 1  # 第二次没调底层
    stats = cached.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_different_messages_dont_collide() -> None:
    from shared.llm_cache import CachedLLMProvider

    inner = MockLLMProvider(canned_responses=["A", "B"])
    cached = CachedLLMProvider(inner=inner)
    a = cached.chat(messages=[{"role": "user", "content": "x"}])
    b = cached.chat(messages=[{"role": "user", "content": "y"}])
    assert a.content == "A"
    assert b.content == "B"
    assert len(inner.calls) == 2


def test_temperature_change_is_different_key() -> None:
    """temperature 不同应视为不同请求。"""
    from shared.llm_cache import CachedLLMProvider

    inner = MockLLMProvider(canned_responses=["A", "B"])
    cached = CachedLLMProvider(inner=inner)
    cached.chat(messages=[{"role": "user", "content": "hi"}], temperature=0.1)
    cached.chat(messages=[{"role": "user", "content": "hi"}], temperature=0.9)
    assert len(inner.calls) == 2


def test_lru_evicts_oldest() -> None:
    from shared.llm_cache import CachedLLMProvider

    inner = MockLLMProvider(canned_responses=["A", "B", "C", "A2"])
    cached = CachedLLMProvider(inner=inner, max_size=2)

    cached.chat(messages=[{"role": "user", "content": "k1"}])  # cache: k1
    cached.chat(messages=[{"role": "user", "content": "k2"}])  # cache: k1, k2
    cached.chat(messages=[{"role": "user", "content": "k3"}])  # cache: k2, k3 (k1 淘汰)
    # k1 已淘汰，再问会再调底层
    r = cached.chat(messages=[{"role": "user", "content": "k1"}])
    assert r.content == "A2"  # 第 4 个 canned response
    assert len(inner.calls) == 4


def test_cache_implements_llm_provider() -> None:
    from shared.llm_cache import CachedLLMProvider
    from shared.llm_client import LLMProvider

    inner = MockLLMProvider(canned_responses=["A"])
    cached = CachedLLMProvider(inner=inner)
    assert isinstance(cached, LLMProvider)


def test_cache_propagates_underlying_exception() -> None:
    """底层抛 TutorError → 不缓存，照样上抛。"""
    from shared.llm_cache import CachedLLMProvider
    from shared.llm_client import StubLLMProvider
    from shared.errors import TutorError

    cached = CachedLLMProvider(inner=StubLLMProvider())
    with pytest.raises(TutorError):
        cached.chat(messages=[{"role": "user", "content": "x"}])
    # 异常不应留下缓存条目，下次还会再尝试
    with pytest.raises(TutorError):
        cached.chat(messages=[{"role": "user", "content": "x"}])
    stats = cached.stats()
    assert stats["hits"] == 0


def test_health_reflects_inner() -> None:
    from shared.llm_cache import CachedLLMProvider
    from shared.llm_client import StubLLMProvider

    cached = CachedLLMProvider(inner=StubLLMProvider())
    assert cached.health().ok is False  # stub 不健康
