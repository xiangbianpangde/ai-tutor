"""aitutor.cache - 缓存中间件模块入口

> 对应模块: M-005
> 关联接口: IC-002（学习回合 — cache hit 写入）
> 关联选型: TS-003 SQLite / TS-005 Redis / TS-006 httpx
> 设计模式: Proxy + Flyweight
> 来源标注: [DD-001:FS-005] + [DD-001:MD-005]
"""
# [来源标注] [DD-001:FS-005]
# 本文件为 M-005 缓存中间件包的入口，仅导出公共接口，不实现业务逻辑
# 私有成员实现分散到 backend.py / lru.py / semantic.py / proxy.py

# 延迟导入，避免循环依赖（proxy 依赖 backend/lru/semantic）
# [DD-M推断:依据=Python src layout 最佳实践 + Import Linter contract 1/2]
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 类型检查阶段导入，运行期不导入（避免循环）
    from aitutor.cache.backend import CacheBackend
    from aitutor.cache.lru import LRUEvictionPolicy
    from aitutor.cache.proxy import CacheProxy
    from aitutor.cache.semantic import CacheEntry, SemanticCache


# 公共导出清单
# [DD-M推断:依据=DD-001 FS-005 文件结构与 MD-005 类设计]
__all__: list[str] = [
    "CacheBackend",
    "CacheEntry",
    "CacheProxy",
    "LRUEvictionPolicy",
    "SemanticCache",
    "build_cache_proxy",  # 工厂函数（DD-M推断：封装依赖装配）
    "select_backend",     # 工厂函数（DD-001 MD-005 函数签名）
]


def build_cache_proxy(env: str = "dev") -> "CacheProxy":  # noqa: ARG001
    """构造 CacheProxy 工厂（DD-M推断：封装依赖装配）。

    [DD-M推断:依据=MD-005 select_backend + MD-005 CacheProxy 属性]
    [来源标注] [DD-001:MD-005] + [DD-M推断:DI 注入]
    """
    raise NotImplementedError  # 由 DD-S/DEV 实现


def select_backend(env: str) -> "CacheBackend":
    """按 env 选择后端实现（sqlite 默认 / redis 可选）。

    [DD-001:MD-005] select_backend(env: str) → CacheBackend
    [来源标注] [DD-001:MD-005]
    """
    raise NotImplementedError  # 由 DD-S/DEV 实现
