"""M-003 客户端入口 - Strategy 模式调度器（统一入口分发）

> 对应模块: M-003 / sm003-cli + sm003-web + sm003-lib（横切）
> 关联接口: IC-001（服务启动） / IC-002（学习回合）
> 关联选型: TS-001 Python
> 设计模式: Strategy（EntryDispatcher 持有 3 个形态的 strategy 可调用对象）
> 来源标注: [DD-001:MD-003 Facade+Strategy] + [DD-M推断:Strategy 字典持有 form -> handler]

[文件职责]  M-003 Strategy 模式调度器，按 form 参数选择对应形态入口的处理函数。
[所属模块]  M-003（来自 DD-001）
[关联设计规范]  FS-003 / MD-003（来自 DD-001）

[功能描述]
  功能1: 提供 `EntryDispatcher` 类，按 form 字符串路由到 cli/web/lib 形态
  功能2: 集中维护 form -> handler 映射表（Strategy 字典）
  功能3: 统一处理 E00301 形态不支持异常

[输入输出]
  输入:  form: str（"cli" | "web" | "lib"）+ 调用参数
  输出:  对应形态处理函数的返回值

[依赖关系]
  依赖文件:  aitutor.clients.cli / aitutor.clients.web / aitutor.clients.lib
  被依赖文件:  aitutor.clients.__init__（re-export EntryDispatcher）

[注意事项]
  注意1: form 字符串与 pyproject [project.scripts] 入口名保持一致
  注意2: GUI 形态 V3.5 才实现，V3.1 阶段 dispatcher 不注册 gui 策略
  注意3: dispatcher 自身不持有任何状态，可被多次复用

[代码风格]  遵循 CS-AITutor-V3.1（来自 DD-001）
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-003 - 初始创建（仅注释骨架，无业务代码）
[作者]  DD-M-003-20260602
[来源标注]  [DD-001:MD-003 Facade+Strategy] + [DD-M推断:Strategy 字典模式]
"""

# 标准库
from typing import Any, Callable, Final, Literal

# 第三方库
# （无第三方库依赖）

# 本地模块
from aitutor.clients.cli import cli_main
from aitutor.clients.lib import library_chat
from aitutor.clients.web import web_serve


# ============================================================
# 模块级常量
# ============================================================

# 支持的形态字面量
# [DD-M推断:与 pyproject [project.scripts] 入口名 + MD-003 4 形态对齐]
SupportedForm = Literal["cli", "web", "gui", "lib"]

# 形态 -> 处理函数 映射表（Strategy 字典）
# [DD-M推断:gui 形态 V3.5 占位，V3.1 阶段不注册；注册后 E00301 触发]
_STRATEGY_MAP: Final[dict[str, Callable[..., Any]]] = {
    "cli": cli_main,
    "web": web_serve,
    "lib": library_chat,
    # "gui": _gui_entry,  # V3.5 占位
}

# V3.1 阶段已实现形态集合
_IMPLEMENTED_FORMS: Final[frozenset[str]] = frozenset({"cli", "web", "lib"})


# ============================================================
# 异常类
# ============================================================


class UnsupportedFormError(ValueError):
    """[类名] UnsupportedFormError
    [职责]  形态不支持异常，对应错误码 E00301。
    [关联设计规范] MD-003 E00301（来自 DD-001）

    [异常处理]
      异常1: UnsupportedFormError  - 触发 E00301 形态不支持

    [示例]
      >>> raise UnsupportedFormError("gui")
      Traceback (most recent call last):
          ...
      UnsupportedFormError: 形态不支持: gui（已实现: cli/web/lib）
    """
    # [DD-M推断:继承 ValueError 而非 Exception，捕获粒度更精准]
    pass


# ============================================================
# 类定义
# ============================================================


class EntryDispatcher:
    """[类名] EntryDispatcher
    [职责]  Strategy 模式调度器，按 form 参数路由到对应形态入口。
    [关联设计规范] MD-003 Facade+Strategy EntryDispatcher（来自 DD-001）

    [属性]
      属性1: form: str                当前形态标识
      属性2: strategies: dict         Strategy 映射表（form -> handler）

    [方法列表]
      方法1: __init__(form) -> None   - 初始化形态标识
      方法2: route(*args, **kwargs)   - 分派到对应 strategy handler
      方法3: list_supported() -> list[str] - 列出已支持的形态

    [状态机]  N/A（无状态分发）

    [异常处理]
      异常1: UnsupportedFormError     - form 不在 _STRATEGY_MAP 中（E00301）
    """

    # --------------------------------------------------------
    # 构造与初始化
    # --------------------------------------------------------

    def __init__(self, form: str) -> None:
        """[函数名] __init__
        [职责]  初始化调度器形态标识。
        [关联接口契约]  IC-001（服务启动，web/cli 形态的根入口）
        [参数说明]
          参数1: form str 必填 规则 ∈ {cli, web, gui, lib}  形态标识
        [返回值]  None
        [错误码]
          错误码1: E00301  UnsupportedFormError  form 不在已实现集合
        [前置条件]  无
        [后置条件]  self.form / self.strategies 已设置
        [并发安全]  N/A
        [幂等性]  是
        [性能约束]  <1ms
        [示例]
          >>> d = EntryDispatcher("cli")
          >>> d.form
          'cli'
        [来源标注]  [DD-001:MD-003 EntryDispatcher]
        """
        # [DD-M推断:form 不在 _IMPLEMENTED_FORMS 时立即抛 UnsupportedFormError]
        self.form: str = form
        self.strategies: dict[str, Callable[..., Any]] = dict(_STRATEGY_MAP)
        raise NotImplementedError  # 业务代码由 DD-S 实现

    # --------------------------------------------------------
    # 分派
    # --------------------------------------------------------

    def route(self, *args: Any, **kwargs: Any) -> Any:
        """[函数名] route
        [职责]  按 self.form 分派到对应 strategy handler。
        [关联接口契约]  IC-001（web/cli） / IC-002（lib）
        [参数说明]
          参数1: *args  可变位置参数  透传给 handler
          参数2: **kwargs 可变关键字参数 透传给 handler
        [返回值]
          类型: Any
          描述: handler 的返回值（cli_main -> int / web_serve -> None / library_chat -> str）
        [错误码]
          错误码1: E00301  UnsupportedFormError  form 未实现
        [前置条件]  self.form 在 _IMPLEMENTED_FORMS 中
        [后置条件]  对应 handler 已被调用一次
        [并发安全]  否（依赖具体 handler 的并发模型）
        [幂等性]  否（依赖具体 handler）
        [性能约束]  <1ms（不含 handler 执行时间）
        [示例]
          >>> d = EntryDispatcher("cli")
          >>> # rc = d.route(["start", "--port", "8000"])
          >>> # rc  # 0=成功
        [来源标注]  [DD-001:MD-003 EntryDispatcher.route]
        """
        # [DD-M推断:从 self.strategies 取出 handler 并透传 *args, **kwargs]
        raise NotImplementedError  # 业务代码由 DD-S 实现

    # --------------------------------------------------------
    # 查询
    # --------------------------------------------------------

    @staticmethod
    def list_supported() -> list[str]:
        """[函数名] list_supported
        [职责]  列出当前已支持的形态清单。
        [关联接口契约]  N/A
        [参数说明]  无
        [返回值]
          类型: list[str]
          描述: 已实现形态列表（V3.1: [cli, web, lib]）
        [并发安全]  N/A
        [幂等性]  是
        [来源标注]  [DD-M推断:静态方法，便于外部查询]
        """
        # [DD-M推断:返回 _IMPLEMENTED_FORMS 的排序列表]
        raise NotImplementedError  # 业务代码由 DD-S 实现
