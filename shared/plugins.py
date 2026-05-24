"""插件注册中心（L1）。

合同来源: ai-tutor-system-design/specs/plugin-registry.md

设计原则:
- Plugin 是一个 Protocol，要求 category + name + health()
- PluginRegistry 按 priority 排序，get() 自动跳过不健康的，全坏才抛错
- 健康检查不应该有副作用，调用方按 TTL 自己缓存

本切片：只实现注册 / 取活跃 / 健康聚合。
后续切片补：进程外健康探测、自动重试、provider 切换 webhook。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, runtime_checkable

from .errors import TutorError


@dataclass
class HealthStatus:
    ok: bool
    reason: str | None = None
    extra: dict[str, Any] | None = None


@runtime_checkable
class Plugin(Protocol):
    """所有插件必须暴露 category 和 name + health()。

    具体行为方法（如 LLM.chat、PdfParser.parse）由 category 自己的子 Protocol 定义。
    """

    category: ClassVar[str]
    name: ClassVar[str]

    def health(self) -> HealthStatus: ...


class PluginRegistry:
    """按 category 管理插件，按 priority 降序优先。"""

    def __init__(self) -> None:
        # category -> list[(priority, plugin)]，按 priority 降序
        self._by_category: dict[str, list[tuple[int, Plugin]]] = {}

    def register(self, plugin: Plugin, *, priority: int = 0) -> None:
        bucket = self._by_category.setdefault(plugin.category, [])
        bucket.append((priority, plugin))
        bucket.sort(key=lambda x: x[0], reverse=True)

    def get(self, category: str) -> Plugin:
        """返回第一个健康的 plugin；全坏则抛 PLUGIN_NOT_AVAILABLE。"""
        bucket = self._by_category.get(category)
        if not bucket:
            raise TutorError(
                "PLUGIN_NOT_AVAILABLE",
                hint=f"category={category} 未注册任何 provider",
            )
        broken: list[str] = []
        for _prio, plugin in bucket:
            status = plugin.health()
            if status.ok:
                return plugin
            broken.append(f"{plugin.name}({status.reason or 'unknown'})")
        raise TutorError(
            "PLUGIN_NOT_AVAILABLE",
            hint=f"category={category} 全部 provider 不健康: {', '.join(broken)}",
        )

    def health_check(self) -> dict[str, dict[str, Any]]:
        """每个 category 取第一个 plugin 的健康状态。"""
        out: dict[str, dict[str, Any]] = {}
        for category, bucket in self._by_category.items():
            if not bucket:
                continue
            _prio, plugin = bucket[0]
            status = plugin.health()
            out[category] = {
                "provider": plugin.name,
                "status": "healthy" if status.ok else "unhealthy",
                "reason": status.reason,
            }
        return out
