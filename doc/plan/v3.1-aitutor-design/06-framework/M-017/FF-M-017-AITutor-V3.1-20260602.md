# 文件框架结构 — M-017 存储 — AITutor V3.1

> 负责模块：M-017 存储（Repository + UnitOfWork）
> 关联设计规范：MD-M-017 / FS-M-017 / IC-M-017 / CS-NNN
> 来源标注：[DD-001:FS-NNN/MD-NNN/IC-NNN] + [DD-M推断:依据]
> 文件框架轮次：1/4

---

## [模块编号] M-017
## [模块名称] 存储（Storage）
## [设计模式] Repository + UnitOfWork
## [关联技术选型] TS-003 SQLite / TS-004 ChromaDB

## 文件框架

```
M-017/
└── aitutor/
    └── storage/
        ├── __init__.py                ← 模块入口，导出公共接口（UnitOfWork / SQLiteRepository / ChromaRepository / FileStore / MigrationRunner）
        ├── unit_of_work.py            ← UnitOfWork 实现（事务边界：__enter__/__exit__/commit/rollback）
        │   - [UnitOfWork 类注释]
        │   - [函数: __enter__/__exit__/commit/rollback/get_session/query_chroma/read_file/write_file/migrate/init_storage]
        ├── sqlite_repo.py             ← SQLite 主存 Repository（SQLAlchemy 2.0 async）
        │   - [SQLiteRepository 类注释]
        │   - [BaseRepository 抽象基类]
        │   - [函数: query/insert/update/delete/execute/executemany/begin/commit/rollback]
        ├── chroma_repo.py             ← ChromaDB 向量库 Repository
        │   - [ChromaRepository 类注释]
        │   - [函数: query/add/delete/update/count/peek/reset]
        ├── file_store.py              ← 文件存储（基于 ~/.<app>/ 路径）
        │   - [FileStore 类注释]
        │   - [函数: read/write/delete/exists/list/resolve_path/ensure_dir]
        └── migrations/                ← 数据库迁移（版本化）
            ├── __init__.py
            └── v1_initial.py          ← v1 初始 Schema（DDL + 索引）

└── tests/
    └── unit/
        └── test_storage/
            ├── __init__.py
            ├── test_unit_of_work.py   ← UoW 事务流转测试
            │   - [测试场景1: 正常提交] [断言: 三后端一致] [Mock: 三后端]
            │   - [测试场景2: 异常回滚] [断言: 全部回滚] [Mock: 三后端]
            │   - [测试场景3: 嵌套使用] [断言: 上下文正常] [Mock: 无]
            ├── test_sqlite_repo.py    ← SQLite 异步仓储测试
            │   - [测试场景1: 增删改查] [断言: 行为正确] [Mock: AsyncEngine]
            │   - [测试场景2: 事务隔离] [断言: 并发安全] [Mock: AsyncSession]
            │   - [测试场景3: 锁等待重试] [断言: 重试后成功] [Mock: 锁异常]
            ├── test_chroma_repo.py    ← ChromaDB Repository 测试
            │   - [测试场景1: 向量查询] [断言: 返回chunk列表] [Mock: Client]
            │   - [测试场景2: 增/删/改] [断言: 集合更新] [Mock: Client]
            │   - [测试场景3: ChromaDB 损坏] [断言: 重建恢复] [Mock: 损坏client]
            ├── test_file_store.py     ← 文件存储测试
            │   - [测试场景1: 读写删除] [断言: 行为正确] [Mock: 临时目录]
            │   - [测试场景2: 路径越界防护] [断言: 抛出SecurityError] [Mock: 越界路径]
            │   - [测试场景3: 磁盘满] [断言: 抛StorageError] [Mock: 满盘]
            └── test_migrations.py     ← 迁移测试
                - [测试场景1: v1 升级] [断言: DDL 执行] [Mock: 引擎]
                - [测试场景2: 回滚 v1] [断言: 状态还原] [Mock: 引擎]
                - [测试场景3: 迁移失败回滚] [断言: 自动回滚] [Mock: 失败迁移]
```

## 文件间依赖关系

```
api/v1/* (M-002)
    ↓ Depends
service/* (M-004/M-008/M-013/M-014)
    ↓
repository/* (M-004/M-013)
    ↓
storage/
    ├── unit_of_work.py  ──→  sqlite_repo.py  ──→  shared/exceptions
    │                   ──→  chroma_repo.py  ──→  shared/exceptions
    │                   ──→  file_store.py   ──→  shared/exceptions
    │                   ──→  migrations/
    │                          └── v1_initial.py
    └── migrations/v1_initial.py  ──→  sqlite_repo.py
```

**无循环依赖**，依赖方向：service → repository → storage → shared

## 子模块拆分

| 子模块 | 职责 | 对应文件 |
|--------|------|----------|
| sm017-sqlite | SQLite 主存（SQLAlchemy 2.0 async） | sqlite_repo.py |
| sm017-chroma | ChromaDB 向量库 | chroma_repo.py |
| sm017-files | 文件存储 | file_store.py |
| sm017-uow | 事务管理（跨三后端） | unit_of_work.py |
| sm017-migrate | Schema 迁移 | migrations/ |

## 类设计

| 类 | 职责 | 关键方法 |
|----|------|----------|
| `UnitOfWork` | 事务边界管理（3 后端协同） | `__enter__/__exit__/commit/rollback` |
| `SQLiteRepository` | SQLite 异步仓储 | `query/insert/update/delete` |
| `BaseRepository` | 仓储抽象基类（ABC） | 抽象方法：query/insert/update/delete |
| `ChromaRepository` | ChromaDB 向量仓储 | `query/add/delete` |
| `FileStore` | 文件存储（沙箱路径） | `read/write/delete/exists` |
| `MigrationRunner` | 迁移执行器 | `run/rollback` |
| `StorageConfig` | 存储配置（Pydantic） | - |

## 函数签名（来自 MD-M-017）

```python
def init_storage(config: StorageConfig) -> None
def get_session() -> AsyncSession
def query_chroma(collection: str, embedding: List[float]) -> List[Chunk]
def read_file(path: str) -> bytes
def write_file(path: str, data: bytes) -> None
def migrate(version: int) -> bool
```

## 文件结构 5 项合规检查（4.7）

| 检查项 | 检查标准 | 通过 | 证据 |
|--------|---------|------|------|
| 目录层级 | 目录层级≥2层 | ✅ | src/aitutor/storage/ + migrations/，3 层 |
| 文件命名 | snake_case | ✅ | unit_of_work/sqlite_repo/chroma_repo/file_store/migrations |
| 文件职责 | 每个文件单一职责 | ✅ | UoW/3 后端/迁移 各自分离 |
| 依赖关系 | 无循环依赖 | ✅ | UoW → 3 后端 + migrations，方向单向 |
| 最佳实践 | src layout + Repository/UoW | ✅ | 符合 DD-001:FS-M-017 规范 |

**合规度 = 高（5/5 通过）**

## 来源标注
[DD-001:FS-NNN/MD-NNN/IC-NNN] + [DD-M推断:依据=Python src layout + Repository/UoW 模式最佳实践]
