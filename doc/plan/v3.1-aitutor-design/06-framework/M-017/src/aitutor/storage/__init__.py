"""storage - M-017 存储（Repository + UnitOfWork）

> 对应模块: M-017 存储
> 关联接口: IC-001（服务启动）/ IC-002（学习回合）/ IC-004（数据入库）/ IC-007（长期记忆）
> 关联选型: TS-003 SQLite / TS-004 ChromaDB
> 关联设计: MD-AITutor-V3.1#m-017-存储repository--unitofwork
> 关联设计模式: Repository + UnitOfWork
> 来源标注: [DD-001:FS-017/MD-017] + [DD-M推断:依据=Repository+UoW 经典分层]
"""

# [文件职责] 存储模块初始化；统一导出 UnitOfWork + 3 个 Repository（SQLite/ChromaDB/File）
# [所属模块] M-017
# [关联设计规范] MD-AITutor-V3.1#m-017 / FS-AITutor-V3.1#m-017
# [设计模式] Repository（每后端一个仓储）+ UnitOfWork（事务一致性）
# [导出策略]
#   公共 API: UnitOfWork / StorageConfig / SQLiteRepository / ChromaRepository / FileStore / MigrationRunner
#   内部 API: BaseRepository / BaseMigration
# [依赖关系]
#   被依赖文件: 全部 repository.py（M-004/008/013）+ ingest/ingester.py（M-014）+ build/verifier.py（M-015）
#   依赖文件: shared/exceptions.py / shared/types.py / monitor/logger.py
# [注意事项]
#   注意1: 存储模块不直接对外暴露 Connection / Engine，强制经 UnitOfWork 申请（防止裸连接）
#   注意2: 跨模块调用者仅允许通过 UnitOfWork 或各 Repository 公开方法访问
#   注意3: migrations 子模块由 MigrationRunner 调度，禁止外部直接执行
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [作者] DD-M-017-20260602
# [来源标注] [DD-001:FS-017/MD-017]

from aitutor.storage.unit_of_work import (
    StorageConfig,
    UnitOfWork,
)
from aitutor.storage.sqlite_repo import (
    BaseRepository,
    SQLiteRepository,
)
from aitutor.storage.chroma_repo import (
    ChromaRepository,
)
from aitutor.storage.file_store import (
    FileStore,
)
from aitutor.storage.migrations import (
    Migration,
    MigrationRunner,
    V1InitialMigration,
)

__all__ = [
    "StorageConfig",
    "UnitOfWork",
    "BaseRepository",
    "SQLiteRepository",
    "ChromaRepository",
    "FileStore",
    "Migration",
    "MigrationRunner",
    "V1InitialMigration",
]

__version__ = "3.1.0"
__module_id__ = "M-017"
