"""M-003 客户端入口 - GUI 形态（V3.5 占位）

> 对应模块: M-003 / sm003-gui
> 关联接口: N/A（V3.5 决策，V3.1 阶段未实现）
> 关联选型: N/A（V3.5 决策，待选型：PySide6 / Tkinter / WebView）
> 设计模式: N/A（占位）
> 来源标注: [DD-001:MD-003 sm003-gui V3.5 占位] + [DD-M推断:仅做版本守卫]

[文件职责]  M-003 GUI 形态占位模块，V3.5 决策实现，V3.1 阶段仅做版本守卫。
[所属模块]  M-003（来自 DD-001）
[关联设计规范]  FS-003 / MD-003（来自 DD-001）

[功能描述]
  功能1: V3.1 阶段被 import 时抛出 NotImplementedError 提示 V3.5 决策
  功能2: 暴露 GUI_FORM 常量供 EntryDispatcher 占位引用

[输入输出]
  输入:  无
  输出:  N/A（占位）

[依赖关系]
  依赖文件:  无
  被依赖文件:  aitutor.clients.__init__（from aitutor.clients import gui 触发版本守卫）

[注意事项]
  注意1: V3.1 阶段禁止实现任何 GUI 业务逻辑（V3.5 决策）
  注意2: 任何 import 行为必须立即抛出明确的 NotImplementedError
  注意3: 不要在此文件中引入任何 GUI 框架依赖（避免污染 V3.1 依赖树）

[代码风格]  遵循 CS-AITutor-V3.1（来自 DD-001）
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-003 - 初始创建（V3.1 占位，无业务代码）
[作者]  DD-M-003-20260602
[来源标注]  [DD-001:MD-003 sm003-gui V3.5 占位] + [DD-M推断:仅做版本守卫]
"""

# 标准库
from typing import Final

# 第三方库
# （V3.1 阶段不引入任何 GUI 框架依赖）

# 本地模块
# （占位模块不引用任何业务模块）


# ============================================================
# 模块级常量
# ============================================================

# GUI 形态版本守卫
# [DD-M推断:V3.5 实现后删除此守卫并替换为真实 GUI 入口]
_GUI_VERSION_GATE: Final[str] = "3.5"

# 当前实现版本（V3.1 阶段不实现）
_CURRENT_VERSION: Final[str] = "3.1"

# GUI 形态标识符
# [DD-M推断:与 EntryDispatcher.SupportedForm 保持一致]
GUI_FORM: Final[str] = "gui"


# ============================================================
# 模块加载期版本守卫
# ============================================================

# [DD-M推断:任何 import 行为都触发 V3.5 决策提示]
# 注意: 此处仅在 import 时记录占位信息，不阻塞 aitutor.clients.__init__ 的 re-export
# 实际 GUI 启动时由 dispatcher 在 route() 中检测 GUI_FORM 时再抛 NotImplementedError
