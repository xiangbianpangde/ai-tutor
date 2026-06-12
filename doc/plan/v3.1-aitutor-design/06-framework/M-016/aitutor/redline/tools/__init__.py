"""tools - 红线工具 Runner 集合（Chain 各节点）。

> 对应模块: M-016
> 关联接口: IC-006
> 关联选型: TS-013 Ruff / TS-014 Import Linter / TS-015 Redocly / TS-016 pre-commit
> 设计模式: Chain of Responsibility（节点实现同一 Runner 协议）
> 来源标注: [DD-001:MD-M-016/FS-M-016/IC-006] + [DD-M推断:依据=Chain 节点 + 协议对象]

[文件职责]
  本文件为 tools 子包入口，集中暴露 4 个 Runner（RuffRunner / ImportLinterRunner /
  RedoclyRunner / PrecommitRunner）。注意：Pytest Runner 因与 pre-commit 冲突，单独由
  Orchestrator 调用，不在 tools 子包内。Chain 中各 Runner 实现同一协议（run 方法），
  允许 Orchestrator 统一调度。

[所属模块]
  M-016（红线编排 / Chain + Observer）

[关联设计规范]
  FS-M-016 / MD-M-016 / CS-M-016

[功能描述]
  功能1: 4 Runner re-export
  功能2: Runner 协议定义（抽象基类 Runner）
  功能3: Runner 注册表（用于 Orchestrator 自动发现）

[输入输出]
  输入: 外部调用方 ``from aitutor.redline.tools import RuffRunner``
  输出: 4 个 Runner 类 + Runner 协议

[依赖关系]
  依赖文件:
    - aitutor.redline.tools.ruff.RuffRunner
    - aitutor.redline.tools.import_linter.ImportLinterRunner
    - aitutor.redline.tools.redocly.RedoclyRunner
    - aitutor.redline.tools.precommit.PrecommitRunner
  被依赖文件:
    - aitutor.redline.orchestrator
    - tests/unit/test_redline/test_tools/*

[注意事项]
  注意1: 严禁在 __init__ 中实例化 Runner（保持类型 re-export，不含实例）
  注意2: 4 个 Runner 命名必须严格一致，否则 Orchestrator 注册失败
  注意3: 新增 Runner 须同步在 __init__ 暴露 + Orchestrator.register_tool 支持

[代码风格]
  遵循 CS-M-016

[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-016 - 初始版本（仅注释，无业务代码）
[作者] DD-M-016-20260602
[来源标注] [DD-001:FS-M-016 子包] + [DD-M推断:依据=子包 re-export 惯例]
"""

# ============================================================
# 4 个 Runner re-export
# ============================================================
# from aitutor.redline.tools.ruff import RuffRunner                    # [DD-001:MD-M-016 sm016-ruff]
# from aitutor.redline.tools.import_linter import ImportLinterRunner  # [DD-001:MD-M-016 sm016-importlinter]
# from aitutor.redline.tools.redocly import RedoclyRunner              # [DD-001:MD-M-016 sm016-redocly]
# from aitutor.redline.tools.precommit import PrecommitRunner          # [DD-001:MD-M-016 sm016-precommit]

# ============================================================
# Runner 协议（抽象基类）
# ============================================================
# from abc import ABC, abstractmethod

# class Runner(ABC):
#     """Chain 节点抽象协议。
#
#     [类名] Runner
#     [职责] 定义 4 个 Runner 的统一接口。
#     [关联设计规范] MD-M-016 Chain 模式
#     [属性] N/A
#     [方法列表]
#       方法1: run(changed_files) -> ToolResult - 执行工具并返回结果
#       方法2: name() -> str - 工具名（用于 RedlineReport.raw_output 键）
#     [状态机] N/A
#     [异常处理] 子类各自实现
#     [来源标注] [DD-M推断:依据=Chain 节点协议 + 抽象基类惯例]
#     """
#
#     @abstractmethod
#     def run(self, changed_files: list[str] | None = None) -> "ToolResult":
#         """执行工具。
#
#         [函数职责] 子类必须实现。
#         [关联接口契约] IC-006
#         [参数说明]
#           参数1: changed_files list[str] | None 可选 增量文件列表
#         [返回值]
#           类型: ToolResult
#         [错误码]
#           错误码1: E01601 退出码非 0
#         [前置条件] 工具配置存在（.ruff.toml 等）
#         [后置条件] ToolResult 字段填齐
#         [并发安全] 否（Orchestrator 调度）
#         [幂等性] 是
#         [性能约束] 单工具 ≤ 5min
#         [示例] 不直接调用
#         [来源标注] [DD-M推断:依据=Chain 节点协议]
#         """
#         pass
#
#     @abstractmethod
#     def name(self) -> str:
#         """返回工具名。
#
#         [函数职责] 标识当前 Runner 在 RedlineReport.raw_output 中的键。
#         [关联接口契约] IC-006 raw_output dict 键
#         [参数说明] 无
#         [返回值]
#           类型: str
#           描述: "ruff" | "import_linter" | "redocly" | "pre_commit"
#         [错误码] 无
#         [前置条件] 无
#         [后置条件] 无
#         [并发安全] 是
#         [幂等性] 是
#         [性能约束] O(1)
#         [示例]
#           >>> RuffRunner().name()
#           'ruff'
#         [来源标注] [DD-001:MD-M-016 工具名常量]
#         """
#         pass


# ============================================================
# Runner 注册表（Orchestrator 自动发现）
# ============================================================
# RUNNER_REGISTRY: dict[str, type[Runner]] = {
#     "ruff": RuffRunner,
#     "import_linter": ImportLinterRunner,
#     "redocly": RedoclyRunner,
#     "pre_commit": PrecommitRunner,
# }
# """[DD-M推断:依据=注册表模式 + 自动发现]"""
