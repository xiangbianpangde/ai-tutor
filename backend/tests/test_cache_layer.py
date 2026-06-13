"""backend.middleware.CacheLayer 测试 —— 覆盖 spec 03 功能3（命中/过期/统计）+ 跨重启存活。"""
from __future__ import annotations

import pytest

from backend.middleware import CacheLayer

PROVIDER, MODEL, TEMP = "deepseek", "deepseek-chat", 0.0
MSGS = [{"role": "user", "content": "解释导数定义"}]


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'cache.db').as_posix()}"


def test_miss_then_hit_saves_tokens(db_url):
    """spec 03 场景1：相同输入第二次命中，不调 LLM。"""
    cache = CacheLayer(db_url)
    assert cache.get(PROVIDER, MODEL, MSGS, TEMP) is None  # miss
    cache.set(PROVIDER, MODEL, MSGS, TEMP, "导数是变化率", tokens=500)
    assert cache.get(PROVIDER, MODEL, MSGS, TEMP) == "导数是变化率"  # hit
    s = cache.stats()
    assert s["hits"] == 1 and s["misses"] == 1
    assert s["saved_tokens"] == 500


def test_key_distinguishes_inputs(db_url):
    cache = CacheLayer(db_url)
    cache.set(PROVIDER, MODEL, MSGS, 0.0, "A")
    # 不同 temperature → 不同键 → miss
    assert cache.get(PROVIDER, MODEL, MSGS, 0.7) is None
    # 不同 messages → 不同键 → miss
    assert cache.get(PROVIDER, MODEL, [{"role": "user", "content": "别的"}], 0.0) is None


def test_ttl_expiry(db_url):
    """spec 03 场景2：过期后视为未命中，需重新请求。"""
    cache = CacheLayer(db_url)
    cache.set(PROVIDER, MODEL, MSGS, TEMP, "缓存值", ttl_s=10, now=1000.0)
    assert cache.get(PROVIDER, MODEL, MSGS, TEMP, now=1005.0) == "缓存值"  # 未过期
    assert cache.get(PROVIDER, MODEL, MSGS, TEMP, now=1020.0) is None  # 已过期


def test_hit_rate_stats(db_url):
    """spec 03 场景3：10 次请求 7 命中 → hit_rate 0.7。"""
    cache = CacheLayer(db_url)
    cache.set(PROVIDER, MODEL, MSGS, TEMP, "X", tokens=100)
    for _ in range(7):
        cache.get(PROVIDER, MODEL, MSGS, TEMP)  # 7 hit
    for i in range(3):
        cache.get(PROVIDER, MODEL, [{"role": "user", "content": f"q{i}"}], TEMP)  # 3 miss
    s = cache.stats()
    assert s["hits"] == 7 and s["misses"] == 3
    assert s["hit_rate"] == 0.7
    assert s["saved_tokens"] == 700


def test_persistence_across_restart(db_url):
    """v2 第一波过堂（缓存侧）：新实例（模拟进程重启）仍命中同库已存条目。"""
    first = CacheLayer(db_url)
    first.set(PROVIDER, MODEL, MSGS, TEMP, "落库的回答", tokens=42)
    # 模拟重启：全新实例，运行期计数归零，但条目已落 SQLite
    reborn = CacheLayer(db_url)
    assert reborn.stats()["hits"] == 0  # 计数确实是新进程
    assert reborn.get(PROVIDER, MODEL, MSGS, TEMP) == "落库的回答"  # 条目存活 → 命中
    assert reborn.stats()["saved_tokens"] == 42


def test_clear(db_url):
    cache = CacheLayer(db_url)
    cache.set(PROVIDER, MODEL, MSGS, TEMP, "x")
    cache.clear()
    assert cache.stats()["entries"] == 0
    assert cache.get(PROVIDER, MODEL, MSGS, TEMP) is None
