"""storage.unit_of_work - M-017 UnitOfWork 事务管理

> 对应模块: M-017 存储
> 关联接口: IC-001（服务启动 init_storage）/ IC-002（学习回合事务边界）/ IC-004（数据入库事务）
> 关联选型: TS-003 SQLite / TS-004 ChromaDB
> 关联设计: MD-AITutor-V3.1#m-017-存储 类设计 UnitOfWork
> 来源标注: [DD-001:MD-017] + [DD-M推断:依据=UnitOfWork 模式]
"""

# [文件职责] UnitOfWork 事务一致性管理 + 存储初始化入口
# [所属模块] M-017
# [关联设计规范] MD-AITutor-V3.1#m-017 UnitOfWork 类设计
# [功能描述]
#   功能1: 统一管理 SQLite Session / ChromaDB Collection / FileStore 三后端生命周期
#   功能2: 提供上下文管理器（__enter__/__exit__）自动 commit/rollback
#   功能3: init_storage() 启动期初始化引擎 + 注入依赖
# [输入输出]
#   输入: StorageConfig（路径/连接串/池大小）
#   输出: UnitOfWork 实例（context manager）
# [依赖关系]
#   依赖文件: sqlite_repo.py / chroma_repo.py / file_store.py / shared/exceptions.py
#   被依赖文件: 业务 service 层（M-004/008/013/014）通过 DI 注入
# [注意事项]
#   注意1: UoW 仅在同一 asyncio.Task 内有效（asyncio ContextVar 绑定）
#   注意2: 三后端必须全部 commit 成功才视为事务成功；任一失败触发全部回滚
#   注意3: ChromaDB 无传统事务语义，"回滚"通过 delete 补偿实现
#   注意4: 长事务（>5s）需主动分解为多个 UoW，避免锁等待 E01703
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-017 - 初始创建文件框架
# [作者] DD-M-017-20260602
# [来源标注] [DD-001:MD-017]

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from aitutor.storage.chroma_repo import ChromaRepository
from aitutor.storage.file_store import FileStore
from aitutor.storage.sqlite_repo import SQLiteRepository


# ============================================================
# 配置数据类：StorageConfig
# ============================================================


@dataclass
class StorageConfig:
    """存储配置。

    [类名] StorageConfig
    [职责] 集中描述三后端初始化所需参数
    [关联设计规范] MD-AITutor-V3.1#m-017 StorageConfig
    [属性]
      属性1: sqlite_path Path 必填 SQLite 数据库文件路径
      属性2: chroma_path Path 必填 ChromaDB 持久化目录
      属性3: file_base_path Path 必填 文件存储根目录（~/.<app>/）
      属性4: pool_size int 可选 默认 5 异步连接池大小
      属性5: echo_sql bool 可选 默认 False 是否打印 SQL
    [来源标注] [DD-001:MD-017]
    """

    sqlite_path: Path
    chroma_path: Path
    file_base_path: Path
    pool_size: int = 5
    echo_sql: bool = False


# ============================================================
# 类：UnitOfWork
# ============================================================


class UnitOfWork:
    """工作单元（事务边界管理器）。

    [类名] UnitOfWork
    [职责] 统一管理 SQLite / ChromaDB / FileStore 三后端的事务边界
    [关联设计规范] MD-AITutor-V3.1#m-017 UnitOfWork 类设计
    [属性]
      属性1: engine AsyncEngine 必填 SQLAlchemy 异步引擎
      属性2: session AsyncSession 可选 上下文管理器进入时创建
      属性3: chroma ChromaRepository 必填 ChromaDB 仓储
      属性4: file_store FileStore 必填 文件仓储
      属性5: sqlite SQLiteRepository 必填 SQLite 仓储（基于 session）
      属性6: _committed bool 内部 默认 False 是否已 commit
      属性7: _in_context ContextVar[bool] 内部 上下文标记
    [方法列表]
      方法1: __enter__() -> UnitOfWork - 进入上下文，创建 session
      方法2: __exit__(exc_type, exc_val, exc_tb) -> None - 退出上下文，异常则 rollback
      方法3: commit() -> None - 显式提交（同时 flush Chroma + close File handle）
      方法4: rollback() -> None - 显式回滚（SQLite 事务回滚 + Chroma delete 补偿）
      方法5: begin() -> None - 显式开启事务（可选）
    [异常处理]
      异常1: StorageError - 初始化失败（E01702 ChromaDB 损坏 / E01701 磁盘满）
      异常2: TransactionError - commit 失败（包含 trace_id 上下文）
    [并发安全] 是（asyncio 协程内使用，跨协程需新建 UoW）
    [幂等性] commit 幂等，rollback 幂等
    [性能约束] 短事务 <5s（P95）
    [来源标注] [DD-001:MD-017]
    """

    def __init__(
        self,
        engine: AsyncEngine,
        chroma: ChromaRepository,
        file_store: FileStore,
    ) -> None:
        """初始化 UnitOfWork。

        [函数名] __init__
        [职责] 注入三后端依赖
        [参数说明]
          参数1: engine AsyncEngine 必填 SQLAlchemy 异步引擎（来自 init_storage）
          参数2: chroma ChromaRepository 必填 ChromaDB 仓储
          参数3: file_store FileStore 必填 文件仓储
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def __aenter__(self) -> "UnitOfWork":
        """异步进入上下文管理器，创建 session。

        [函数名] __aenter__
        [职责] 创建 AsyncSession + 标记 in_context=True
        [参数说明]
          参数: 无
        [返回值]
          类型: UnitOfWork
        [错误码]
          错误码1: E01702 含义: ChromaDB 损坏 触发: 初始化时无法连接
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """异步退出上下文管理器，根据异常决定 commit/rollback。

        [函数名] __aexit__
        [职责] 异常触发 rollback；正常触发 commit
        [参数说明]
          参数1: exc_type Optional[type[BaseException]] 异常类型
          参数2: exc_val Optional[BaseException] 异常值
          参数3: exc_tb Optional[TracebackType] traceback
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def commit(self) -> None:
        """显式提交事务。

        [函数名] commit
        [职责] 提交 SQLite 事务 + flush Chroma + 关闭 file handle
        [参数说明]
          参数: 无
        [返回值]
          类型: None
        [错误码]
          错误码1: E01703 含义: SQLite 锁等待 触发: OperationalError 重试 1 次仍失败
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def rollback(self) -> None:
        """显式回滚事务。

        [函数名] rollback
        [职责] SQLite 事务回滚 + Chroma delete 补偿 + File 句柄关闭
        [参数说明]
          参数: 无
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...


# ============================================================
# 模块级函数
# ============================================================


# 进程级单例：当前 UoW（由 DI 容器注入）
_current_uow: ContextVar[Optional[UnitOfWork]] = ContextVar(
    "current_uow", default=None
)


async def init_storage(config: StorageConfig) -> UnitOfWork:
    """初始化存储（启动期入口）。

    [函数名] init_storage
    [职责] 创建引擎 + ChromaDB 客户端 + FileStore 目录 + 装配 UnitOfWork
    [关联接口契约] IC-001（服务启动期装配）
    [参数说明]
      参数1: config StorageConfig 必填 存储配置
    [返回值]
      类型: UnitOfWork
      描述: 已初始化的 UnitOfWork 实例（caller 负责 with 上下文）
    [错误码]
      错误码1: E01701 含义: 磁盘满 触发: 创建目录失败
      错误码2: E01702 含义: ChromaDB 损坏 触发: 启动期连接失败
      错误码3: E01704 含义: 迁移失败 触发: schema 版本不匹配
    [前置条件] config.sqlite_path 父目录可写
    [后置条件] 数据库文件存在、chroma 集合已创建、file 根目录可写
    [并发安全] 是（启动期单次调用）
    [幂等性] 是（重复调用会幂等创建）
    [性能约束] 启动 ≤3s（含迁移）
    [示例]
      ```
      uow = await init_storage(config)
      async with uow:
          await uow.sqlite.query(...)
      ```
    [来源标注] [DD-001:MD-017] + [IC-001]
    """
    ...


def get_session() -> AsyncSession:
    """获取当前 UoW 内的 AsyncSession。

    [函数名] get_session
    [职责] 从 ContextVar 取出当前 UoW 的 session，供各 Repository 使用
    [关联接口契约] 内部 API
    [参数说明]
      参数: 无
    [返回值]
      类型: AsyncSession
      描述: 处于活跃事务中的 session
    [错误码]
      错误码1: RuntimeError 含义: 未在 UoW 上下文中 触发: 直接调用本函数
    [来源标注] [DD-001:MD-017]
    """
    ...
