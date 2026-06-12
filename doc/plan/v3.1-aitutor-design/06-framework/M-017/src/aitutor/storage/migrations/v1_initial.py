"""v1_initial - 初始 schema 迁移

> 对应模块: M-017
> 关联接口: IC-001（启动期 E00103 旧库不兼容）
> 关联选型: TS-003 SQLite
> 来源标注: [DD-001:MD-017/FS-017] + [DD-001:DS-001~005]
"""
# [文件职责] 创建初始 4 张表（sessions / memories / documents / audit_logs）+ schema_version 表
# [所属模块] M-017
# [关联设计规范] FS-017 / MD-017 / DS-001~005
# [功能描述]
#   功能1: 建表 sessions（id, user_id, state, created_at, last_active）
#   功能2: 建表 memories（id, user_id, content, importance, last_access, hash）
#   功能3: 建表 documents（id, user_id, path, chunk_count, status, created_at）
#   功能4: 建表 audit_logs（id, trace_id, event_type, payload, ts）
#   功能5: 建表 schema_version（version INTEGER, applied_at INTEGER）
# [输入输出]
#   输入: AsyncEngine
#   输出: None
# [依赖关系]
#   依赖文件: shared/exceptions.py
#   被依赖文件: unit_of_work.py:migrate()
# [注意事项]
#   注意1: 所有表必须含 created_at / updated_at 时间戳
#   注意2: 索引：user_id / trace_id / status
#   注意3: UNIQUE 约束：memories.hash（防重复 save，IC-007）
#   注意4: 回滚必须 DROP 全部 5 张表
# [代码风格] 遵循 CS-001
# [创建日期] 2026-06-02
# [作者] DD-M-017-20260602
# [来源标注] [DD-001:DS-001~005] + [DD-M推断:依据=SQLite schema 标准设计]

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from aitutor.shared.exceptions import MigrationError

# === 类注释 ===

# [类名] Migration
# [职责] 迁移抽象基类
# [关联设计规范] MD-017
# [属性]
#   属性1: version int 版本号（v1=1, v2=2, ...）
#   属性2: description str 描述
# [方法列表]
#   方法1: up(engine) -> None - 应用迁移
#   方法2: down(engine) -> None - 回滚迁移
# [异常处理]
#   异常1: MigrationError - 迁移失败（EX-011/01704）
# [来源标注] [DD-001:MD-017] + [DD-M推断:依据=alembic Migration 基类模式]
class Migration:
    """迁移基类。"""


# [类名] V1InitialMigration
# [职责] v1 初始 schema 迁移
# [关联设计规范] MD-017 / DS-001~005
# [属性]
#   属性1: version = 1
#   属性2: description = "Create initial 4 tables + schema_version"
# [方法列表]
#   方法1: up(engine) - 建 5 张表
#   方法2: down(engine) - 删 5 张表
# [异常处理]
#   异常1: MigrationError - DDL 失败
# [来源标注] [DD-001:DS-001~005]
class V1InitialMigration(Migration):
    """v1 初始迁移。"""
