"""storage.sqlite_repo - M-017 SQLite 主存（SQLAlchemy 2.0 async）

> 对应模块: M-017 存储
> 关联接口: IC-002 / IC-004 / IC-007
> 关联选型: TS-003 SQLite / SQLAlchemy 2.0 async
> 关联设计: MD-AITutor-V3.1#m-017 类设计 SQLiteRepository
> 来源标注: [DD-001:MD-017] + [DD-M推断:依据=Repository 模式]
"""

# [文件职责] SQLite 主存仓储 + BaseRepository 抽象基类
# [所属模块] M-017
# [关联设计规范] MD-AITutor-V3.1#m-017 SQLiteRepository
# [功能描述]
#   功能1: BaseRepository 抽象基类，定义 query/insert/update/delete 通用接口
#   功能2: SQLiteRepository 通用仓储，提供 ORM CRUD
#   功能3: 写失败重试 1 次（E01703 锁等待 / E00403 DB 写失败）
# [输入输出]
#   输入: 实体（dict/dataclass）/ SQL 参数
#   输出: 实体列表 / 单实体 / 影响行数
# [依赖关系]
#   依赖文件: shared/exceptions.py / monitor/logger.py
#   被依赖文件: 全部 repository.py（M-004/008/013）
# [注意事项]
#   注意1: SQLite WAL 模式 + 异步引擎，并发读 OK / 写互斥
#   注意2: 大表查询必须使用索引（schema 在 migrations/v1_initial.py 定义）
#   注意3: 事务边界由 UnitOfWork 统一管理，禁止在此自行 commit
#   注意4: 重试仅对 OperationalError（瞬时锁等待）有效，不重试 IntegrityError
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [作者] DD-M-017-20260602
# [来源标注] [DD-001:MD-017]

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete, select, update as sa_update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from aitutor.shared.exceptions import StorageError


T = TypeVar("T")


# ============================================================
# 抽象基类：BaseRepository
# ============================================================


class BaseRepository(ABC, Generic[T]):
    """仓储抽象基类（泛型）。

    [类名] BaseRepository
    [职责] 定义 CRUD 标准接口，强制子类型实现
    [关联设计规范] MD-AITutor-V3.1#m-017 BaseRepository
    [类型变量]
      T: 仓储管理的实体类型
    [属性]
      属性1: session AsyncSession 必填 来自 UnitOfWork
      属性2: model Type[T] 必填 ORM 模型类（由子类指定）
      属性3: _retry_count int 内部 默认 1 写失败重试次数
    [方法列表]
      方法1: query(filters, limit, offset) -> List[T] - 查询
      方法2: insert(entity: T) -> T - 插入
      方法3: update(entity: T) -> None - 更新
      方法4: delete(id: Any) -> None - 删除
    [来源标注] [DD-001:MD-017] + [DD-M推断:依据=Repository 模式]
    """

    def __init__(self, session: AsyncSession, model: Type[T]) -> None:
        """初始化仓储。

        [函数名] __init__
        [职责] 注入 session 与模型类
        [参数说明]
          参数1: session AsyncSession 必填
          参数2: model Type[T] 必填 ORM 模型
        [来源标注] [DD-001:MD-017]
        """
        self.session = session
        self.model = model
        self._retry_count = 1

    @abstractmethod
    async def query(
        self,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[T]:
        """按条件查询。

        [函数名] query
        [职责] 子类必须实现；返回 List[T]
        [参数说明]
          参数1: filters Optional[dict] 可选 字段过滤条件
          参数2: limit int 可选 默认 100 规则 [1, 1000]
          参数3: offset int 可选 默认 0
        [返回值]
          类型: List[T]
        [来源标注] [DD-001:MD-017]
        """
        ...

    @abstractmethod
    async def insert(self, entity: T) -> T:
        """插入实体。

        [函数名] insert
        [职责] 子类必须实现
        [参数说明]
          参数1: entity T 必填
        [返回值]
          类型: T
        [来源标注] [DD-001:MD-017]
        """
        ...

    @abstractmethod
    async def update(self, entity: T) -> None:
        """更新实体。

        [函数名] update
        [职责] 子类必须实现
        [参数说明]
          参数1: entity T 必填
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...

    @abstractmethod
    async def delete(self, id: Any) -> None:
        """按 ID 删除。

        [函数名] delete
        [职责] 子类必须实现
        [参数说明]
          参数1: id Any 必填
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...


# ============================================================
# 通用实现：SQLiteRepository
# ============================================================


class SQLiteRepository(BaseRepository[T]):
    """SQLite 通用仓储（CRUD 默认实现）。

    [类名] SQLiteRepository
    [职责] 提供基于 SQLAlchemy 2.0 async 的标准 CRUD；子类可覆盖
    [关联设计规范] MD-AITutor-V3.1#m-017 SQLiteRepository
    [属性]
      属性1: session AsyncSession 必填
      属性2: model Type[T] 必填
      属性3: _retry_count int 内部 默认 1
      属性4: _retry_backoff_sec float 内部 默认 0.2
    [方法列表]
      方法1: query - 通用查询
      方法2: insert - 通用插入
      方法3: update - 通用更新
      方法4: delete - 通用删除
      方法5: _execute_with_retry - 重试包装
    [异常处理]
      异常1: StorageError - 写失败且重试 1 次仍失败（E00403/E01703）
    [并发安全] 是（SQLite WAL + 协程）
    [来源标注] [DD-001:MD-017]
    """

    async def query(
        self,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[T]:
        """按条件查询。

        [函数名] query
        [职责] 构造 SELECT 查询并返回结果列表
        [参数说明]
          参数1: filters Optional[dict] 可选 字段过滤（= 等值匹配）
          参数2: limit int 可选 默认 100 规则 [1, 1000]
          参数3: offset int 可选 默认 0
        [返回值]
          类型: List[T]
          描述: 实体列表
        [错误码]
          错误码1: E01703 含义: SQLite 锁等待 触发: OperationalError
        [并发安全] 是
        [幂等性] 是
        [性能约束] 单查 ≤50ms（P95，含索引）
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def insert(self, entity: T) -> T:
        """插入实体。

        [函数名] insert
        [职责] INSERT 一行；返回带主键的实体
        [参数说明]
          参数1: entity T 必填
        [返回值]
          类型: T
          描述: 插入后的实体（含主键）
        [错误码]
          错误码1: E01703 含义: 写失败 触发: 锁等待重试 1 次仍失败
        [并发安全] 是（主键唯一约束保护）
        [幂等性] 否（重复 insert 触发 IntegrityError）
        [性能约束] 单写 ≤50ms（P95）
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def update(self, entity: T) -> None:
        """更新实体（按主键）。

        [函数名] update
        [职责] UPDATE 一行
        [参数说明]
          参数1: entity T 必填 必须含主键
        [返回值]
          类型: None
        [错误码]
          错误码1: E01703 含义: 写失败 触发: 重试 1 次仍失败
        [并发安全] 是
        [幂等性] 是
        [性能约束] 单写 ≤50ms（P95）
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def delete(self, id: Any) -> None:
        """按主键删除。

        [函数名] delete
        [职责] DELETE 一行
        [参数说明]
          参数1: id Any 必填
        [返回值]
          类型: None
        [错误码]
          错误码1: E01703 含义: 写失败 触发: 重试 1 次仍失败
        [并发安全] 是
        [幂等性] 是
        [性能约束] 单写 ≤50ms（P95）
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def _execute_with_retry(
        self, operation_name: str, coro_factory
    ) -> Any:
        """执行写操作并在瞬时 OperationalError 时重试 1 次。

        [函数名] _execute_with_retry
        [职责] 包装写操作；捕获 OperationalError 退避重试 1 次
        [参数说明]
          参数1: operation_name str 必填 操作名（用于日志 trace）
          参数2: coro_factory Callable 必填 协程工厂
        [返回值]
          类型: Any
        [错误码]
          错误码1: E01703 含义: 写失败 触发: 2 次尝试均失败
        [来源标注] [DD-001:MD-017] + [DD-M推断:依据=EX-011 重试策略]
        """
        ...
