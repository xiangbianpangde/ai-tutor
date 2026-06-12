"""M-003 客户端入口（Facade + Strategy）— 模块初始化

> 对应模块: M-003
> 关联接口: IC-001（服务启动，作为入参）
> 关联选型: TS-001 Python / TS-002 FastAPI
> 设计模式: Facade + Strategy
> 来源标注: [DD-001:MD-003/FS-003] + [DD-M推断:Facade+Strategy 模式组织 4 形态入口]

[文件职责]  M-003 客户端入口模块初始化，导出 4 种形态入口（CLI/Web/GUI/Lib）的公共 API。
[所属模块]  M-003（来自 DD-001）
[关联设计规范]  FS-003 / MD-003（来自 DD-001）

[功能描述]
  功能1: 集中 re-export 4 形态入口的公共类与函数，供外部 `import aitutor.clients` 时按名引用
  功能2: 暴露 `EntryDispatcher` 作为统一调度入口（Strategy 模式）
  功能3: 通过 `__all__` 显式控制公共 API 表面，避免内部实现外泄

[输入输出]
  输入: 无（模块加载即触发）
  输出: 名称空间暴露 CLIEntry / WebEntry / LibraryEntry / EntryDispatcher / cli_main / web_serve / library_chat

[依赖关系]
  依赖文件:  本模块下属 cli.py / web.py / lib.py / dispatcher.py / gui/
  被依赖文件:  aitutor.main（M-001 服务入口的 pyproject scripts 间接引用 cli_main / web_serve）

[注意事项]
  注意1: 本模块禁止引入任何业务模块（session / cache / rag 等），仅做形态分发，避免反向依赖
  注意2: __all__ 必须与下方 re-export 保持一致，Ruff F401 仅 __init__ 允许 re-export
  注意3: GUI 形态仅占位（V3.5 决策），V3.1 阶段勿实现任何 GUI 业务逻辑

[代码风格]  遵循 CS-AITutor-V3.1（来自 DD-001）
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-003 - 初始创建（仅注释骨架，无业务代码）
[作者]  DD-M-003-20260602
[来源标注]  [DD-001:FS-003] + [DD-M推断:Facade+Strategy 模式统一 4 形态入口]
"""

# 标准库
# （无标准库导入，本模块仅做 re-export）

# 第三方库
# （无第三方库导入）

# 本地模块 —— 4 形态入口
from aitutor.clients.cli import CLIEntry, cli_main
from aitutor.clients.dispatcher import EntryDispatcher
from aitutor.clients.lib import AITutorClient, LibraryEntry, library_chat
from aitutor.clients.web import WebEntry, web_serve

# 本地模块 —— GUI 占位（V3.5 决策）
# 注意: V3.1 阶段 GUI 不导出公共 API，仅占位以避免 RUF022
from aitutor.clients import gui  # noqa: F401  # [DD-M推断:保留以触发 gui/__init__.py 的版本守卫]

# 公共 API 表面
__all__: list[str] = [
    # CLI 形态
    "CLIEntry",
    "cli_main",
    # Web 形态
    "WebEntry",
    "web_serve",
    # GUI 形态（V3.5 占位）
    "gui",
    # Library 形态
    "AITutorClient",
    "LibraryEntry",
    "library_chat",
    # Strategy 调度
    "EntryDispatcher",
]
