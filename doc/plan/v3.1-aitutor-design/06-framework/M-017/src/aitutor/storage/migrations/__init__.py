"""storage.migrations - M-017 数据库迁移框架

> 对应模块: M-017 存储
> 关联接口: IC-001（服务启动 init_storage 触发迁移）
> 关联选型: TS-003 SQLite / TS-001 Python
> 关联设计: MD-AITutor-V3.1#m-017 类设计 MigrationRunner
> 来源标注: [DD-001:MD-017] + [DD-M推断:依据=Chain 模式（迁移链）]
"""

# [文件职责] 数据库迁移框架（Migration 基类 + MigrationRunner 调度 + v1 初始迁移）
# [所属模块] M-017
# [关联设计规范] MD-AITutor-V3.1#m-017 MigrationRunner
# [功能描述]
#   功能1: Migration 抽象基类定义 up/down 接口
#   功能2: MigrationRunner 按 version 顺序执行 + 自动回滚
#   功能3: V1InitialMigration 初始 schema（users/sessions/memories/documents 等）
# [输入输出]
#   输入: 目标 version
#   输出: bool 迁移是否成功
# [依赖关系]
#   依赖文件: sqlite_repo.py / unit_of_work.py
#   被依赖文件: unit_of_work.py init_storage()
# [注意事项]
#   注意1: 迁移失败必须自动回滚 + 备份（E01704）
#   注意2: 迁移链单向（只允许 up）；down 仅 DEBUG 模式
#   注意3: 迁移前必须先备份数据库文件
#   注意4: 新增迁移必须 append 列表，禁止修改历史迁移
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [作者] DD-M-017-20260602
# [来源标注] [DD-001:MD-017]

from __future__ import annotations

import abc
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from aitutor.shared.exceptions import StorageError


# ============================================================
# 抽象基类：Migration
# ============================================================


class Migration(abc.ABC):
    """迁移基类（链式）。

    [类名] Migration
    [职责] 定义 up/down 接口；记录 version
    [关联设计规范] MD-AITutor-V3.1#m-017 Migration
    [属性]
      属性1: version int 必填 迁移版本号（单调递增）
      属性2: description str 必填 描述
    [方法列表]
      方法1: up(session) - 正向迁移
      方法2: down(session) - 反向迁移（仅 DEBUG）
    [来源标注] [DD-001:MD-017] + [DD-M推断:依据=Chain 模式]
    """

    version: int
    description: str

    @abc.abstractmethod
    async def up(self, session: AsyncSession) -> None:
        """执行迁移。

        [函数名] up
        [职责] 子类必须实现；执行 DDL
        [参数说明]
          参数1: session AsyncSession 必填
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...

    @abc.abstractmethod
    async def down(self, session: AsyncSession) -> None:
        """回滚迁移（仅 DEBUG）。

        [函数名] down
        [职责] 子类必须实现
        [参数说明]
          参数1: session AsyncSession 必填
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...


# ============================================================
# 类：MigrationRunner
# ============================================================


@dataclass
class _MigrationRecord:
    """迁移记录（持久化在 _migrations 表）。"""
    version: int
    applied_at: str  # ISO8601
    description: str


class MigrationRunner:
    """迁移调度器。

    [类名] MigrationRunner
    [职责] 按 version 顺序执行迁移；失败回滚 + 备份恢复
    [关联设计规范] MD-AITutor-V3.1#m-017 MigrationRunner
    [属性]
      属性1: db_path Path 必填 SQLite 文件路径
      属性2: migrations List[Migration] 必填 已注册迁移列表
      属性3: backup_dir Path 必填 备份目录
    [方法列表]
      方法1: run(target_version) - 跑到目标版本
      方法2: rollback(target_version) - 回滚到目标版本
      方法3: status() - 查询当前版本
    [异常处理]
      异常1: StorageError - 迁移失败（E01704）
    [并发安全] 否（启动期单次）
    [幂等性] 是（重复执行已应用迁移不报错）
    [性能约束] 启动迁移 ≤3s
    [来源标注] [DD-001:MD-017]
    """

    def __init__(
        self,
        db_path: Path,
        migrations: List[Migration],
        backup_dir: Path,
    ) -> None:
        """初始化 MigrationRunner。

        [函数名] __init__
        [职责] 注入路径 + 迁移列表（按 version 升序）
        [参数说明]
          参数1: db_path Path 必填
          参数2: migrations List[Migration] 必填
          参数3: backup_dir Path 必填
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def run(self, target_version: int = -1) -> bool:
        """执行迁移到目标版本。

        [函数名] run
        [职责] 备份 → 逐个 up → 写入 _migrations 表
        [关联接口契约] IC-001（启动期装配）
        [参数说明]
          参数1: target_version int 可选 默认 -1（最新） 目标版本
        [返回值]
          类型: bool
          描述: 成功 True / 失败 False（已自动回滚）
        [错误码]
          错误码1: E01704 含义: 迁移失败 触发: DDL 异常 / 备份失败
        [并发安全] 否
        [幂等性] 是
        [性能约束] ≤3s
        [来源标注] [DD-001:MD-017] + [IC-001]
        """
        ...

    async def rollback(self, target_version: int) -> bool:
        """回滚到目标版本（仅 DEBUG）。

        [函数名] rollback
        [职责] 备份 → 反向 down
        [参数说明]
          参数1: target_version int 必填
        [返回值]
          类型: bool
        [错误码]
          错误码1: E01704 含义: 回滚失败 触发: DDL 异常
        [注意事项] 注意1: 生产环境禁用
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def status(self) -> int:
        """查询当前版本。

        [函数名] status
        [职责] 从 _migrations 表读取最新 version
        [参数说明]
          参数: 无
        [返回值]
          类型: int
          描述: 当前已应用的最大 version；0 表示未迁移
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def _backup(self) -> Path:
        """备份数据库（内部）。

        [函数名] _backup
        [职责] 复制 db_path 到 backup_dir
        [参数说明]
          参数: 无
        [返回值]
          类型: Path
          描述: 备份文件路径
        [错误码]
          错误码1: E01704 含义: 备份失败 触发: 磁盘满
        [来源标注] [DD-001:MD-017]
        """
        ...


# ============================================================
# 迁移：V1InitialMigration
# ============================================================


class V1InitialMigration(Migration):
    """v1 初始迁移（建立核心 schema）。

    [类名] V1InitialMigration
    [职责] 创建 users / sessions / messages / memories / documents / fsrs_cards / _migrations 表
    [关联设计规范] MD-AITutor-V3.1#m-017 V1InitialMigration
    [属性]
      属性1: version int 固定 1
      属性2: description str 固定 "initial schema"
    [DDL 列表]
      - users(id, name, created_at, ...)
      - sessions(id, user_id, state, created_at, last_active, ...)
      - messages(id, session_id, role, content, ts, ...)
      - memories(id, user_id, content, last_access, importance, ...)
      - documents(id, user_id, file_path, status, ...)
      - chunks(id, doc_id, content, embedding_ref, ...)
      - fsrs_cards(id, user_id, state, due, stability, ...)
      - _migrations(version, applied_at, description)
    [来源标注] [DD-001:MD-017] + [DD-M推断:依据=核心实体表设计]
    """

    version: int = 1
    description: str = "initial schema (users/sessions/messages/memories/documents/chunks/fsrs_cards)"

    async def up(self, session: AsyncSession) -> None:
        """执行 v1 迁移。

        [函数名] up
        [职责] 创建 8 张核心表 + 索引
        [参数说明]
          参数1: session AsyncSession 必填
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def down(self, session: AsyncSession) -> None:
        """回滚 v1 迁移。

        [函数名] down
        [职责] DROP 全部表
        [参数说明]
          参数1: session AsyncSession 必填
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-017]
        """
        ...


# 注册迁移（按 version 升序）
REGISTERED_MIGRATIONS: List[Migration] = [
    V1InitialMigration(),
]
