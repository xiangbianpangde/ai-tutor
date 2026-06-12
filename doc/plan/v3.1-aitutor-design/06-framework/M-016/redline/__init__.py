"""redline - M-016 红线编排（Chain + Observer）。

> 对应模块: M-016
> 关联接口: IC-006（红线检测 API-006 / IF-006）
> 关联选型: TS-013 Ruff / TS-014 Import Linter / TS-015 Redocly / TS-016 pre-commit / TS-017 pytest
> 关联设计规范: FS-016 / MD-016
> 来源标注: [DD-001:FS-016/MD-016/IC-006] + [DD-M推断:依据=Chain+Observer 模式 + pytest 工具补充]

[文件职责] ≤ 50字：M-016 红线编排包入口，导出公共 API
[所属模块] M-016
[关联设计规范] FS-016 / MD-016（来自 DD-001）
[功能描述]
  功能1: 导出 RedlineOrchestrator（Chain 模式主入口）
  功能2: 导出 ErrorHub（Observer 模式中心）
  功能3: 导出 RedlineReport（报告生成）
  功能4: 导出 5 个工具 Runner（Ruff / ImportLinter / Redocly / Precommit / Pytest）
[输入输出]
  输入: 无（模块初始化）
  输出: 公共符号表
[依赖关系]
  依赖文件: redline.orchestrator / redline.error_hub / redline.reports / redline.tools
  被依赖文件: aitutor.api.v1.health / aitutor.build.orchestrator（CI 阶段调用）
[注意事项]
  注意1: 仅 re-export 公共 API，私有符号以下划线前缀
  注意2: 不在此处执行业务逻辑
  注意3: 5 个工具 Runner 需通过 tools 子包导入，避免循环
[代码风格] 遵循 CS-AITutor（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-016 - 初始版本，含 5 工具 Runner 导出
[作者] DD-M-016-20260602
[来源标注] [DD-001:FS-016/MD-016]
"""
# ruff: noqa: F401  # re-export is intentional

# 注：本文件为框架注释版本，不含业务代码 import 逻辑
# 业务代码（DD-S 编写）应包含：
#   from aitutor.redline.orchestrator import RedlineOrchestrator
#   from aitutor.redline.error_hub import ErrorHub
#   from aitutor.redline.reports import RedlineReport
#   from aitutor.redline.tools import (
#       RuffRunner, ImportLinterRunner, RedoclyRunner, PrecommitRunner, PytestRunner,
#   )

__all__ = [
    "RedlineOrchestrator",
    "RedlineResult",
    "ToolResult",
    "ErrorHub",
    "RedlineObserver",
    "Report",
    "RedlineReport",
    "RuffRunner",
    "ImportLinterRunner",
    "RedoclyRunner",
    "PrecommitRunner",
    "PytestRunner",
]
