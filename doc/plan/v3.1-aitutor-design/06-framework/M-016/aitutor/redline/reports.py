"""reports - 报告数据模型（Pydantic BaseModel）。

> 对应模块: M-016
> 关联接口: IC-006（红线检测 出参）
> 关联选型: TS-013~017 + Pydantic v2
> 设计模式: Data Transfer Object
> 来源标注: [DD-001:MD-M-016/FS-M-016/IC-006] + [DD-M推断:依据=Pydantic v2 DTO 最佳实践]

[文件职责]
  本文件定义 M-016 红线检测的核心数据模型：ToolResult（单工具结果）、Report（兼容旧名
  别，指向 ToolResult）、RedlineReport（聚合报告，对应 IC-006 出参）。所有字段带类型
  注解，pydantic 校验在构造期完成。

[所属模块]
  M-016（红线编排 / Chain + Observer）

[关联设计规范]
  FS-M-016 / MD-M-016 / CS-M-016

[功能描述]
  功能1: 单工具结果模型 ToolResult
  功能2: 聚合报告模型 RedlineReport（IC-006 出参）
  功能3: JSON 序列化支持（用于 DE-046 持久化）
  功能4: 错误码映射（exit_code → E0160X 错误码字符串）

[输入输出]
  输入: 来自 Runner / ErrorHub 的字段值
  输出: 序列化后的 dict / JSON 字符串

[依赖关系]
  依赖文件:
    - aitutor.shared.types.RedlineToolName
  被依赖文件:
    - aitutor.redline.orchestrator
    - aitutor.redline.error_hub
    - aitutor.redline.tools.*（间接）

[注意事项]
  注意1: RedlineReport.exit_code 必须 ∈ {0, 1}，CI 通过 0 失败 1
  注意2: RedlineReport.fix_url 非空（Pydantic Field min_length 校验）
  注意3: raw_output 必须含所有 tool 键（dict[str, str]）
  注意4: duration_ms 必填，单位毫秒
  注意5: Pydantic ConfigDict 必须 frozen=False 允许后续追加字段（如 fix_url 二次更新）

[代码风格]
  遵循 CS-M-016

[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-016 - 初始版本（仅注释，无业务代码）
[作者] DD-M-016-20260602
[来源标注] [DD-001:MD-M-016] + [DD-M推断:依据=IC-006 出参字段映射]
"""

from __future__ import annotations

# ============================================================
# 标准库
# ============================================================
# from typing import Any

# ============================================================
# 第三方
# ============================================================
# from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# 本地
# ============================================================
# from aitutor.shared.types import RedlineToolName


# ============================================================
# 模型定义
# ============================================================

# class ToolResult(BaseModel):
#     """单工具红线执行结果。
#
#     [类名] ToolResult
#     [职责] 描述单工具（ruff/import_linter/redocly/pre_commit/pytest）的执行结果。
#     [关联设计规范] MD-M-016
#     [属性]
#       属性1: tool RedlineToolName 工具名
#       属性2: exit_code int 退出码 [0, 1]
#       属性3: violation_count int 违规计数
#       属性4: raw_output str 原始输出（stdout + stderr）
#       属性5: duration_ms int 耗时（毫秒）
#     [方法列表]
#       方法1: is_passed() -> bool - 判断是否通过（exit_code == 0）
#       方法2: to_dict() -> dict[str, Any] - 转为可序列化字典
#     [状态机] N/A
#     [异常处理]
#       异常1: ValueError - Pydantic 校验失败（exit_code 越界等）
#     [来源标注] [DD-001:MD-M-016 ToolResult 推断] + [DD-M推断:依据=单工具结果 DTO]
#     """
#     model_config = ConfigDict(frozen=False, extra="forbid")
#
#     tool: RedlineToolName = Field(..., description="工具名")
#     exit_code: int = Field(..., ge=0, le=1, description="退出码")
#     violation_count: int = Field(..., ge=0, description="违规计数")
#     raw_output: str = Field(default="", description="原始输出")
#     duration_ms: int = Field(..., ge=0, description="耗时（毫秒）")
#
#     def is_passed(self) -> bool:
#         """判断工具是否通过。
#
#         [函数职责] 读取 exit_code 并返回布尔。
#         [关联接口契约] 无
#         [参数说明] 无
#         [返回值]
#           类型: bool
#           描述: exit_code == 0
#         [错误码] 无
#         [前置条件] 无
#         [后置条件] 无
#         [并发安全] 是
#         [幂等性] 是
#         [性能约束] O(1)
#         [示例]
#           >>> ToolResult(tool="ruff", exit_code=0, ...).is_passed()
#           True
#         [来源标注] [DD-M推断:依据=便捷查询方法]
#         """
#         pass
#
#     def to_dict(self) -> dict[str, Any]:
#         """转为可序列化字典。
#
#         [函数职责] 序列化为 dict，用于 JSON 写入。
#         [关联接口契约] 无
#         [参数说明] 无
#         [返回值]
#           类型: dict[str, Any]
#         [错误码] 无
#         [前置条件] 无
#         [后置条件] 无
#         [并发安全] 是
#         [幂等性] 是
#         [性能约束] O(1)
#         [示例]
#           >>> ToolResult(...).to_dict()
#           {'tool': 'ruff', 'exit_code': 0, ...}
#         [来源标注] [DD-M推断:依据=DTO 序列化]
#         """
#         pass


# Report 作为 ToolResult 的别名（MD-M-016 类设计中的 Report 与 ToolResult 同义）
# Report = ToolResult  # [DD-M推断:依据=MD-M-016 同时提到 Report 与 ToolResult]


# class RedlineReport(BaseModel):
#     """红线检测聚合报告（IC-006 出参主对象）。
#
#     [类名] RedlineReport
#     [职责] 封装 IC-006 出参字段：exit_code、violation_count、raw_output、fix_url、duration_ms。
#     [关联设计规范] MD-M-016 / IC-006
#     [属性]
#       属性1: exit_code int [0, 1] 整体退出码
#       属性2: violation_count int 违规总数
#       属性3: raw_output dict[str, str] 各工具原始输出
#       属性4: fix_url str 修复手册链接
#       属性5: duration_ms int 总耗时（毫秒）
#       属性6: tool_results list[ToolResult] 各工具详细结果
#       属性7: passed_tools list[RedlineToolName] 通过的工具
#       属性8: failed_tools list[RedlineToolName] 失败的工具
#     [方法列表]
#       方法1: is_passed() -> bool - 整体通过？
#       方法2: to_json() -> str - 序列化为 JSON
#       方法3: get_failed_tool_messages() -> dict[str, str] - 失败工具的 raw_output
#     [状态机] N/A
#     [异常处理]
#       异常1: ValueError - 字段校验失败
#     [来源标注] [DD-001:MD-M-016 RedlineReport + IC-006 出参] + [DD-M推断:依据=IC-006 字段映射]
#     """
#     model_config = ConfigDict(frozen=False, extra="forbid")
#
#     exit_code: int = Field(..., ge=0, le=1, description="整体退出码")
#     violation_count: int = Field(..., ge=0, description="违规总数")
#     raw_output: dict[str, str] = Field(default_factory=dict, description="各工具原始输出")
#     fix_url: str = Field(..., min_length=1, description="修复手册链接")
#     duration_ms: int = Field(..., ge=0, description="总耗时（毫秒）")
#     tool_results: list[ToolResult] = Field(default_factory=list, description="各工具详细结果")
#     passed_tools: list[RedlineToolName] = Field(default_factory=list, description="通过工具")
#     failed_tools: list[RedlineToolName] = Field(default_factory=list, description="失败工具")
#
#     def is_passed(self) -> bool:
#         """判断整体是否通过。
#
#         [函数职责] exit_code == 0 判断。
#         [关联接口契约] IC-006
#         [参数说明] 无
#         [返回值]
#           类型: bool
#         [错误码] 无
#         [前置条件] 无
#         [后置条件] 无
#         [并发安全] 是
#         [幂等性] 是
#         [性能约束] O(1)
#         [示例]
#           >>> r = RedlineReport(exit_code=0, ...)
#           >>> r.is_passed()
#           True
#         [来源标注] [DD-M推断:依据=DTO 便捷方法]
#         """
#         pass
#
#     def to_json(self) -> str:
#         """序列化为 JSON 字符串。
#
#         [函数职责] model_dump_json 封装。
#         [关联接口契约] IC-006（fix_url 等字段用于 DE-046 持久化）
#         [参数说明] 无
#         [返回值]
#           类型: str
#         [错误码]
#           错误码1: TypeError 字段不可序列化
#         [前置条件] 无
#         [后置条件] 无
#         [并发安全] 是
#         [幂等性] 是
#         [性能约束] O(N) N=字段数
#         [示例]
#           >>> r.to_json()
#         [来源标注] [DD-M推断:依据=序列化]
#         """
#         pass
#
#     def get_failed_tool_messages(self) -> dict[str, str]:
#         """获取失败工具的 raw_output 字典。
#
#         [函数职责] 从 tool_results 过滤 exit_code≠0 的项，映射 tool→raw_output。
#         [关联接口契约] 无
#         [参数说明] 无
#         [返回值]
#           类型: dict[str, str]
#         [错误码] 无
#         [前置条件] 无
#         [后置条件] 无
#         [并发安全] 是
#         [幂等性] 是
#         [性能约束] O(N)
#         [示例]
#           >>> r.get_failed_tool_messages()
#           {'ruff': '...violation...', 'pytest': '...coverage...'}
#         [来源标注] [DD-M推断:依据=CI 阻断信息提取]
#         """
#         pass
