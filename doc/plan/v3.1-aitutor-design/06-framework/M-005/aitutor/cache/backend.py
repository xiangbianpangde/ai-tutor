"""backend - 缓存双后端适配（SQLite 默认 / Redis 可选）

[文件路径] src/aitutor/cache/backend.py
[文件职责] 缓存存储后端抽象与双实现（SQLite/Redis），统一 get/set/ttl 接口
[所属模块] M-005（来自 DD-001）
[关联设计规范] FS-005 / MD-005（来自 DD-001）
[功能描述]
  功能1: 定义后端抽象接口（BaseCacheBackend）
  功能2: 实现 SQLiteCacheBackend（默认 / 单进程）
  功能3: 实现 RedisCacheBackend（可选 / 分布式）
  功能4: Redis 不可用时降级 SQLite（E00501）
[输入输出]
  输入: 缓存键（query_hash）/ 缓存值（response 文本）/ TTL 秒数
  输出: 缓存命中结果（None 表示未命中）/ 写入成功状态 / 剩余 TTL
[依赖关系]
  依赖文件: aitutor.shared.exceptions（CacheBackendError）
  被依赖文件: aitutor.cache.proxy（CacheProxy 持有 backend 引用）
[注意事项]
  注意1: SQLite 后端仅适用于单进程（V3.1 默认）；多进程需切 Redis
  注意2: Redis 后端必须处理连接池耗尽（E00501 降级）
  注意3: 后端实现必须线程安全（asyncio Lock 保护连接）
  注意4: TTL 到期自动清理（SQLite 触发器 / Redis EXPIRE）
[代码风格] 遵循 CS-AITutor-V3.1（DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-005 - 初始框架（仅注释，无业务代码）
[作者] DD-M-005-20260602
[来源标注] [DD-001:FS-005] + [DD-001:MD-005]
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, Optional

# 类型检查阶段导入（运行期延迟导入，遵循 Import Linter contract 5）
if TYPE_CHECKING:
    from aitutor.shared.exceptions import CacheBackendError


# =============================================================================
# 常量定义
# =============================================================================
# [DD-M推断:依据=MD-005 阈值范围 + CS 常量命名规范 UPPER_SNAKE_CASE]
DEFAULT_TTL_SECONDS: int = 3600           # 默认 TTL 1h（与 IC-003 NLI 缓存一致）
SQLITE_DB_PATH: str = "~/.aitutor/cache/cache.sqlite"  # SQLite 默认路径
REDIS_DEFAULT_URL: str = "redis://127.0.0.1:6379/0"    # Redis 默认 URL

# 后端类型字面量（用于 select_backend 工厂）
BackendKind = Literal["sqlite", "redis"]


# =============================================================================
# 抽象基类
# =============================================================================

class BaseCacheBackend(ABC):
    """[类名] BaseCacheBackend

    [职责] 缓存后端抽象接口（Strategy 模式），统一 get/set/ttl 语义
    [关联设计规范] MD-005（来自 DD-001 模块细化方案）
    [属性]
      属性1: kind BackendKind 后端类型
      属性2: is_available bool 后端是否可用（用于降级判定）
    [方法列表]
      方法1: get(key: str) → Optional[str] - 读取缓存值
      方法2: set(key: str, value: str, ttl: int) → bool - 写入缓存
      方法3: ttl(key: str) → int - 查询剩余 TTL（秒）
      方法4: healthcheck() → bool - 健康检查（E00501 降级判定）
    [状态机] N/A
    [异常处理]
      异常1: CacheBackendError - 后端不可用 / 序列化失败
    [来源标注] [DD-001:MD-005]
    """

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """[函数名] get

        [职责] 读取缓存值
        [参数说明]
          参数1: key str 必填 缓存键（query_hash）校验规则 长度 [16, 64]
        [返回值]
          类型: Optional[str]
          描述: 缓存值（None 表示未命中或已过期）
          特殊值: None 表示 miss
        [错误码] E00502 缓存反序列化失败
        [前置条件] 后端连接就绪
        [后置条件] 不修改后端状态
        [并发安全] 是（asyncio Lock）
        [幂等性] 是 / 多次读取返回一致结果
        [性能约束] 单次读取 ≤5ms
        [来源标注] [DD-001:MD-005]
        """
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: str, ttl: int) -> bool:
        """[函数名] set

        [职责] 写入缓存值（含 TTL）
        [参数说明]
          参数1: key str 必填 缓存键 校验规则 长度 [16, 64]
          参数2: value str 必填 缓存值 校验规则 长度 [1, 100000]
          参数3: ttl int 必填 过期时间（秒） 校验规则 [1, 86400]
        [返回值]
          类型: bool
          描述: True=写入成功 False=写入失败
        [错误码] E00502 序列化失败
        [前置条件] TTL > 0
        [后置条件] 缓存项可在 ttl 秒内读取
        [并发安全] 是（同 key 写互斥）
        [幂等性] 是 / 同 key 重复 set 覆盖
        [性能约束] 单次写入 ≤10ms
        [来源标注] [DD-001:MD-005]
        """
        raise NotImplementedError

    @abstractmethod
    def ttl(self, key: str) -> int:
        """[函数名] ttl

        [职责] 查询剩余 TTL（秒）
        [参数说明]
          参数1: key str 必填 缓存键
        [返回值]
          类型: int
          描述: 剩余秒数（-1 表示无 TTL，-2 表示 key 不存在）
        [前置条件] key 已存在
        [后置条件] 不修改后端状态
        [并发安全] 是
        [幂等性] 是
        [性能约束] ≤3ms
        [来源标注] [DD-001:MD-005]
        """
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> bool:
        """[函数名] healthcheck

        [职责] 后端健康检查（用于 E00501 降级判定）
        [参数说明] 无
        [返回值]
          类型: bool
          描述: True=后端可用 False=不可用
        [并发安全] 是
        [幂等性] 是
        [性能约束] ≤50ms
        [来源标注] [DD-M推断:依据=E00501 异常处理要求]
        """
        raise NotImplementedError


# =============================================================================
# SQLite 后端实现
# =============================================================================

class SQLiteCacheBackend(BaseCacheBackend):
    """[类名] SQLiteCacheBackend

    [职责] SQLite 后端实现（V3.1 默认后端，单进程适用）
    [关联设计规范] MD-005（来自 DD-001）
    [属性]
      属性1: kind Literal["sqlite"] 后端类型
      属性2: db_path str SQLite 文件路径
      属性3: engine AsyncEngine SQLAlchemy 异步引擎
    [方法列表]
      方法1: get(key) → Optional[str] - 读取（覆盖抽象方法）
      方法2: set(key, value, ttl) → bool - 写入（覆盖抽象方法）
      方法3: ttl(key) → int - 查询 TTL（覆盖抽象方法）
      方法4: healthcheck() → bool - SQLite 文件可写检查
    [状态机] N/A
    [异常处理]
      异常1: CacheBackendError - SQLite 锁等待 / 磁盘满
    [来源标注] [DD-001:MD-005] + [DD-001:FS-005]
    """

    def __init__(self, db_path: str = SQLITE_DB_PATH) -> None:
        """[函数名] __init__

        [职责] 初始化 SQLite 后端（建立连接池）
        [参数说明]
          参数1: db_path str 可选 默认 SQLITE_DB_PATH SQLite 文件路径
        [错误码] E00501 文件不可写
        [并发安全] N/A（构造期）
        [来源标注] [DD-001:MD-005]
        """
        raise NotImplementedError

    # get / set / ttl / healthcheck 继承自 BaseCacheBackend，全部为 NotImplementedError
    # 由 DD-S/DEV 在 src/aitutor/cache/backend.py 中实现


# =============================================================================
# Redis 后端实现
# =============================================================================

class RedisCacheBackend(BaseCacheBackend):
    """[类名] RedisCacheBackend

    [职责] Redis 后端实现（可选，分布式场景使用，Redis 不可用时降级 SQLite）
    [关联设计规范] MD-005（来自 DD-001）
    [属性]
      属性1: kind Literal["redis"] 后端类型
      属性2: url str Redis 连接 URL
      属性3: client Redis asyncio 客户端
    [方法列表]
      方法1: get(key) → Optional[str] - 读取（覆盖抽象方法）
      方法2: set(key, value, ttl) → bool - 写入（覆盖抽象方法，含 EX）
      方法3: ttl(key) → int - 查询 TTL（调用 TTL 命令）
      方法4: healthcheck() → bool - Redis PING 健康检查
    [状态机] N/A
    [异常处理]
      异常1: CacheBackendError - E00501 Redis 不可用时降级 SQLite
    [来源标注] [DD-001:MD-005] + [DD-001:FS-005]
    """

    def __init__(self, url: str = REDIS_DEFAULT_URL) -> None:
        """[函数名] __init__

        [职责] 初始化 Redis 后端（异步连接池）
        [参数说明]
          参数1: url str 可选 默认 REDIS_DEFAULT_URL Redis URL
        [错误码] E00501 连接失败
        [并发安全] N/A（构造期）
        [来源标注] [DD-001:MD-005]
        """
        raise NotImplementedError

    # get / set / ttl / healthcheck 继承自 BaseCacheBackend，全部为 NotImplementedError
    # 由 DD-S/DEV 在 src/aitutor/cache/backend.py 中实现


# =============================================================================
# 模块级函数
# =============================================================================

def select_backend(env: str) -> BaseCacheBackend:
    """[函数名] select_backend

    [职责] 按环境变量选择后端实现（sqlite 默认 / redis 可选）
    [关联接口契约] IC-002（cache hit 写入路径）
    [参数说明]
      参数1: env str 必填 运行环境标识 校验规则 范围 {"dev","test","prod"}
    [返回值]
      类型: BaseCacheBackend
      描述: 后端实例（SQLiteCacheBackend 或 RedisCacheBackend）
    [错误码]
      错误码1: E00501 含义 后端不可用 触发 Redis 不可达 处理 降级 SQLite + WARN
    [前置条件] env 合法
    [后置条件] 后端连接就绪
    [并发安全] 是（连接池）
    [幂等性] 是 / 同 env 多次调用返回同类型后端
    [性能约束] ≤50ms
    [来源标注] [DD-001:MD-005]
    """
    raise NotImplementedError
