# 文件框架结构 — M-017 存储

> 角色：DD-M-017 详细设计师（模块）
> 负责模块：M-017（存储，Repository + UnitOfWork）
> 上游：DD-001 详细设计文档（DDI=0.96）
> 下游：DD-S 结构设计师
> 来源标注：[DD-001:FS-017/MD-017/IC-001~008/EX-011/024]

---

## [模块编号] M-017
## [模块名称] 存储（Storage）
## [设计模式] Repository + UnitOfWork

## [文件框架]

```
src/aitutor/storage/
  __init__.py              ← [职责：模块初始化，导出公共接口（UoW / Repository / FileStore / Migration）]
    - 模块 docstring
    - 公共 API re-export
  unit_of_work.py           ← [职责：事务管理（SQLite + Chroma + File）]
    - [类 UnitOfWork 注释：事务边界管理]
    - [类 StorageConfig 注释：存储配置]
    - [类 StorageError 注释：存储域异常]
  sqlite_repo.py            ← [职责：SQLite 关系数据访问（SQLAlchemy 2.0 async）]
    - [类 SQLiteRepository 注释：通用 Repository]
    - [类 SessionRepository 注释：会话表]
    - [类 MemoryRepository 注释：记忆表]
    - [类 DocumentRepository 注释：文档元数据表]
    - [类 AuditLogRepository 注释：审计日志]
  chroma_repo.py            ← [职责：ChromaDB 向量库访问]
    - [类 ChromaRepository 注释：向量集合管理]
    - [类 EmbeddingAdapter 注释：嵌入生成适配器]
  file_store.py             ← [职责：文件存储（PDF/chunks/configs）]
    - [类 FileStore 注释：文件系统包装]
    - [类 PathGuard 注释：路径白名单]
  migrations/
    __init__.py             ← [职责：迁移包入口]
      - [函数 discover_migrations 注释]
    v1_initial.py           ← [职责：v1 初始 schema（documents / sessions / memories / audit_logs）]
      - [类 V1InitialMigration 注释：创建初始表]
      - [类 Migration 基类注释：迁移抽象]

tests/unit/test_storage/
  __init__.py               ← 测试包
  conftest.py               ← 共享 fixture（临时 SQLite / 临时目录 / mock chroma）
  test_unit_of_work.py      ← [测试场景: 正常提交/异常回滚/上下文管理]
  test_sqlite_repo.py       ← [测试场景: 增删改查/并发/事务]
  test_chroma_repo.py       ← [测试场景: 增删向量/查询/重建]
  test_file_store.py        ← [测试场景: 读写/路径越界/不存在]
  test_migrations.py        ← [测试场景: 初始迁移/回滚/版本检测]
```

## [文件间依赖关系]

```
unit_of_work.py
    ↓
sqlite_repo.py + chroma_repo.py + file_store.py
    ↓
migrations/v1_initial.py
    ↓
shared/exceptions.py + shared/types.py
```

## [依赖规则]（Import Linter contract:3 强制）

- `storage/*` 允许依赖：`shared/*` + `migrations/*`
- `storage/*` 禁止依赖：`api/*` + `session/*` + `memory/*` + `cache/*` + `pipeline/*` + `rag/*` + `teaching/*` + `redline/*`
- 防止反向依赖（Repository 不得被 Service / API 直接访问，必须经 UoW）

## [文件结构 5 项合规检查]

| 检查项 | 标准 | 通过情况 |
|--------|------|---------|
| 目录层级 | ≥2 层（storage/ + migrations/） | ✅ 3 层 |
| 文件命名 | snake_case（unit_of_work/sqlite_repo/chroma_repo/file_store） | ✅ |
| 文件职责 | 单一职责（UoW / Repo / File / Migration） | ✅ |
| 依赖关系 | 无循环依赖（UoW → Repo → Migration） | ✅ |
| 最佳实践 | src layout + migrations/ 版本化 + tests/ 独立 | ✅ |

## [来源标注]

[DD-001:FS-017] 文件结构规范 M-017
[DD-001:MD-017] 模块细化方案 M-017（5 类 + 5 函数 + 4 异常）
[DD-001:IC-001~008] 接口契约（含 IC-001 启动期 DB 初始化、IC-004 入库、IC-007 长期记忆）
[DD-001:EX-011/024] DB 写失败 / 并发写入冲突
[DD-001:TS-003/004] SQLite（SQLAlchemy 2.0 async）/ ChromaDB
[DD-M推断:依据=UnitOfWork 模式经典实现需 __enter__/__exit__ 上下文管理]
