"""PluginRegistry 契约测试。

合同来源: ai-tutor-system-design/specs/plugin-registry.md

设计目标:
- 注册插件实例（PDF 解析、转写、LLM、Embedding…）
- 按 category 取活跃 provider（不可用就走降级链）
- 健康检查统一返回 dict[category, {provider, status}]
"""
from __future__ import annotations

import pytest

from shared.errors import TutorError


def test_register_and_get_single_provider() -> None:
    from shared.plugins import HealthStatus, Plugin, PluginRegistry

    class FakePdfPlugin(Plugin):
        category = "pdf_parse"
        name = "fake"

        def health(self) -> HealthStatus:
            return HealthStatus(ok=True)

    reg = PluginRegistry()
    reg.register(FakePdfPlugin())
    p = reg.get("pdf_parse")
    assert p.name == "fake"


def test_get_with_fallback_chain() -> None:
    """主 provider 不健康 → 降级到下一个。"""
    from shared.plugins import HealthStatus, Plugin, PluginRegistry

    class BrokenPlugin(Plugin):
        category = "pdf_parse"
        name = "broken"

        def health(self) -> HealthStatus:
            return HealthStatus(ok=False, reason="模型未加载")

    class GoodPlugin(Plugin):
        category = "pdf_parse"
        name = "good"

        def health(self) -> HealthStatus:
            return HealthStatus(ok=True)

    reg = PluginRegistry()
    reg.register(BrokenPlugin(), priority=10)
    reg.register(GoodPlugin(), priority=5)
    p = reg.get("pdf_parse")
    assert p.name == "good"  # broken 高优先但 health=False，降级到 good


def test_get_missing_category_raises() -> None:
    from shared.plugins import PluginRegistry

    reg = PluginRegistry()
    with pytest.raises(TutorError) as exc:
        reg.get("nonexistent")
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"


def test_health_check_aggregates_all_categories() -> None:
    from shared.plugins import HealthStatus, Plugin, PluginRegistry

    class A(Plugin):
        category = "pdf_parse"
        name = "a"
        def health(self) -> HealthStatus:
            return HealthStatus(ok=True)

    class B(Plugin):
        category = "llm"
        name = "b"
        def health(self) -> HealthStatus:
            return HealthStatus(ok=False, reason="rate limit")

    reg = PluginRegistry()
    reg.register(A())
    reg.register(B())
    report = reg.health_check()
    assert report["pdf_parse"]["status"] == "healthy"
    assert report["pdf_parse"]["provider"] == "a"
    assert report["llm"]["status"] == "unhealthy"
    assert "rate limit" in report["llm"]["reason"]


def test_all_categories_unhealthy_falls_back_to_first() -> None:
    """所有 provider 都坏：依然返回最高优先的，让调用方拿到清晰错误。"""
    from shared.plugins import HealthStatus, Plugin, PluginRegistry

    class Bad1(Plugin):
        category = "pdf_parse"
        name = "bad1"
        def health(self) -> HealthStatus:
            return HealthStatus(ok=False)

    class Bad2(Plugin):
        category = "pdf_parse"
        name = "bad2"
        def health(self) -> HealthStatus:
            return HealthStatus(ok=False)

    reg = PluginRegistry()
    reg.register(Bad1(), priority=10)
    reg.register(Bad2(), priority=5)
    # 两个都坏 → 抛 PLUGIN_NOT_AVAILABLE
    with pytest.raises(TutorError) as exc:
        reg.get("pdf_parse")
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"
    assert "bad1" in (exc.value.hint or "") or "bad2" in (exc.value.hint or "")
