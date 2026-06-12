"""aitutor.storage - 存储模块（Repository + UnitOfWork）。

> 对应模块: M-017
> 关联接口: IC-M-017（来自 DD-001 详细设计）
> 关联选型: TS-003 SQLite / TS-004 ChromaDB
> 来源标注: [DD-001:FS-NNN/MD-NNN] + [DD-M推断:依据=Python src layout + Repository/UoW 最佳实践]

[文件路径] src/aitutor/storage/__init__.py
[文件职责] 存储模块入口，导出公共 API（UnitOfWork / SQLiteRepository / ChromaRepository / FileStore / MigrationRunner）
[所属模块] M-017（来自 DD-001）
[关联设计规范] FS-M-017 / MD-M-017（来自 DD-001）
[功能描述]
  功能1: 导出 M-017 模块的所有公共接口（UoW / Repository / FileStore / Migration）
  功能2: 集中管理模块版本号与对外契约
  功能3: 简化外部导入路径（`from aitutor.storage import UnitOfWork`）
[输入输出]
  输入: 无（仅作为包初始化）
  输出: 对外暴露的类/函数符号
[依赖关系]
  依赖文件:
    - aitutor.storage.unit_of_work（UnitOfWork 类）
    - aitutor.storage.sqlite_repo（SQLiteRepository / BaseRepository 类）
    - aitutor.storage.chroma_repo（ChromaRepository 类）
    - aitutor.storage.file_store（FileStore 类）
    - aitutor.storage.migrations（MigrationRunner / v1_initial 迁移）
  被依赖文件:
    - 任何需要 M-017 能力的上游模块（M-004/M-008/M-013/M-014 的 repository/service 层）
[注意事项]
  注意1: 仅 re-export 公共 API，私有符号以下划线开头（如 _internal_helper）
  注意2: 模块版本号必须与 pyproject.toml 保持一致（3.1.0）
  注意3: 不要在此文件执行副作用（避免 import 时副作用）
[代码风格] 遵循 CS-NNN：4 空格缩进、Google 风格 Docstring、snake_case
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-017 - 初始版本，导出 UnitOfWork / 3 Repository / FileStore / MigrationRunner
[作者] DD-M-017-2026-06-02
[来源标注] [DD-001:FS-NNN/MD-NNN] + [DD-M推断:依据=DD-001 FS-M-017 目录结构]
"""
