# 框架决策记录 FDR — M-017 存储

> 角色：DD-M-017
> 来源标注：[DD-M推断:依据=UnitOfWork 模式 + DD-001 规范]

---

## FDR-001 单元文件命名采用类型前缀

- **决策状态**：已接受
- **决策内容**：`sqlite_repo.py` / `chroma_repo.py` / `file_store.py` 替代通用 `repository.py`
- **决策理由**：M-017 包含 3 个异构后端（SQL 关系 / 向量 / 文件），用类型前缀避免多 Repository 命名冲突，也便于 Import Linter 精确控制依赖边界
- **拒绝的替代方案**：单 `repository.py` 文件——3 后端职责混杂，单文件函数数将超过 20 上限（违反 4.2）
- **影响范围**：M-017 所有 Repository 实现
- **来源标注**：[DD-001:FS-017] + [DD-M推断:依据=同模块异构后端需要明确前缀]

## FDR-002 migrations/ 子目录版本化

- **决策状态**：已接受
- **决策内容**：迁移按 `v{N}_{name}.py` 版本化，便于未来扩展（v2/v3）
- **决策理由**：当前仅 v1，但 schema 演进是必然（FS-017 规范预留 migrations/ 子目录）；版本化让 `discover_migrations` 自动发现
- **拒绝的替代方案**：单 `migration.py` 文件——无法支持多版本
- **影响范围**：迁移调度、启动期 init_storage
- **来源标注**：[DD-001:FS-017]

## FDR-003 UnitOfWork 上下文管理（async with）

- **决策状态**：已接受
- **决策内容**：`UnitOfWork` 实现 `__aenter__` / `__aexit__`，自动 commit/rollback
- **决策理由**：DD-001 MD-017 明确要求 UnitOfWork 模式 + `__enter__/__exit__`；async 化匹配 SQLAlchemy 2.0 async session
- **拒绝的替代方案**：显式 begin/commit/rollback——容易遗漏异常路径的事务关闭
- **影响范围**：所有调用 UoW 的 service 层
- **来源标注**：[DD-001:MD-017] + [DD-M推断:依据=UnitOfWork 经典实现]

## FDR-004 PathGuard 独立类

- **决策状态**：已接受
- **决策内容**：`PathGuard` 独立成类，与 `FileStore` 分离
- **决策理由**：EX-014 路径越界是安全异常，需独立单元测试；分离让 `FileStore` 专注读写，Guard 专注白名单
- **拒绝的替代方案**：把校验逻辑内联到 `FileStore` 各方法——违反单一职责，测试覆盖率下降
- **影响范围**：所有 FileStore 读写入口
- **来源标注**：[DD-001:EX-014] + [DD-M推断:依据=Guard 模式]

## FDR-005 Chroma 损坏自动重建（EX-012 策略前置）

- **决策状态**：已接受
- **决策内容**：`ChromaRepository.rebuild_from_sqlite()` 显式提供重建方法
- **决策理由**：EX-012 触发后必须能从 SQLite documents 表恢复向量；方法签名独立便于单测
- **拒绝的替代方案**：损坏即抛错，让上层处理——可用性差，需在每个调用方重复重建逻辑
- **影响范围**：启动期 init_storage / 运行时 query 失败重试
- **来源标注**：[DD-001:EX-012]

## FDR-006 启用 SQLite WAL 模式

- **决策状态**：已接受
- **决策内容**：engine 层 `connect_args={"check_same_thread": False}` + `PRAGMA journal_mode=WAL` + `busy_timeout=5000`
- **决策理由**：EX-024 并发写冲突，WAL 是 SQLite 官方推荐并发模式
- **拒绝的替代方案**：默认 DELETE 日志模式——单写者，吞吐极低
- **影响范围**：所有 SQLite 写操作
- **来源标注**：[DD-001:EX-024] + [DD-M推断:依据=SQLite WAL 最佳实践]

## 来源标注汇总

[DD-001:FS-017/MD-017] 文件结构 + 模块细化
[DD-001:EX-011/012/014/024] DB 迁移 / Chroma 损坏 / 路径越界 / 并发冲突
[DD-M推断:依据=UnitOfWork / Repository / Guard / Adapter 等经典模式应用]
