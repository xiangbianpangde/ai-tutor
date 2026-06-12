"""dispatcher - 教学动作分发器（Mediator）

[文件路径] src/aitutor/teaching/dispatcher.py
[文件职责] 教学侧 Mediator 实现：动作到具体 handler 的解耦分发
[所属模块] M-009 教学编排（来自 DD-001）
[关联设计规范] MD-009 / FS-009（来自 DD-001）
[功能描述]
  功能1: 注册教学动作 handler（如 feynman/fsrs/stage_change/idle）
  功能2: 按 action 名分派到对应 handler
  功能3: 构造并校验 TeachingContext
[输入输出]
  输入: action（str）、TeachingContext
  输出: ActionResult（含 success/payload/next_state）
[依赖关系]
  依赖文件: feynman/scorer.py（M-010）、fsrs/scheduler.py（M-011）、stage/evaluator.py（M-012）、shared/types.py
  被依赖文件: orchestrator.py（M-009）
[注意事项]
  注意1: handlers 注册表需在启动期装配，运行期只读
  注意2: Mediator 屏蔽 handler 内部实现差异，对外只暴露统一签名
  注意3: 未注册 action 走 LLM 兜底并记 audit_log
[代码风格] 遵循 CS-AITutor-V3.1（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-009 - 初版文件头注释
[作者] DD-M-M-009-20260602
[来源标注] [DD-001:MD-009] + [DD-M推断:依据=Mediator 模式在教学域的映射]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass
class TeachingContext:
    """[类名] TeachingContext
    [职责] 教学上下文数据载体
    [关联设计规范] MD-009（来自 DD-001）
    [属性]
      属性1: user_id str 用户 ID，32hex
      属性2: session_id str 会话 ID，UUIDv4
      属性3: action str 教学动作名
      属性4: context_ids List[str] 关联上下文（如 FSRS 卡片 ID）
      属性5: trace_id str 32hex trace 标识
      属性6: extras Dict[str, Any] 扩展字段
    [方法列表]
      方法1: build() -> "TeachingContext" 工厂方法（数据校验）
    [来源标注] [DD-001:MD-009] + [DD-M推断:依据=DDT 上下文传递最佳实践]
    """

    user_id: str
    session_id: str
    action: str
    context_ids: List[str] = field(default_factory=list)
    trace_id: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def build(self) -> "TeachingContext":
        """[函数名] build
        [职责] 工厂方法：校验并返回上下文
        [返回值]
          类型: TeachingContext
        [错误码]
          错误码1: ValidationError 含义 字段非法 触发 user_id 长度异常
        [来源标注] [DD-M推断:依据=Builder 模式]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError


class ActionResult(BaseModel):
    """[类名] ActionResult
    [职责] 教学动作执行结果
    [属性]
      属性1: success bool 是否成功
      属性2: payload Dict[str, Any] 业务负载
      属性3: next_state Optional[str] 下一态（TeachingState 枚举值字符串）
      属性4: error_code Optional[str] 错误码（E00901/E00902/E00903 等）
      属性5: trace_id str 32hex
    [来源标注] [DD-001:MD-009] + [DD-M推断:依据=Result Object 模式]
    """

    success: bool = Field(..., description="是否成功")
    payload: Dict[str, Any] = Field(default_factory=dict, description="业务负载")
    next_state: Optional[str] = Field(default=None, description="下一态（字符串）")
    error_code: Optional[str] = Field(default=None, description="错误码")
    trace_id: str = Field(..., description="32hex trace 标识")


TeachingHandler = Callable[[TeachingContext], Awaitable[ActionResult]]


class ActionDispatcher:
    """[类名] ActionDispatcher
    [职责] Mediator 中心：动作名到 handler 的映射与分派
    [关联设计规范] MD-009（来自 DD-001 模块细化方案）
    [属性]
      属性1: handlers Dict[str, TeachingHandler] 已注册 handler 表
      属性2: fallback_handler Optional[TeachingHandler] 未匹配时的兜底 handler
    [方法列表]
      方法1: register(action, handler) -> None - 注册 handler
      方法2: unregister(action) -> None - 注销 handler
      方法3: dispatch(context) -> ActionResult - 分发
      方法4: set_fallback(handler) -> None - 设置兜底
    [状态机] N/A
    [异常处理]
      异常1: UnknownActionError - 未知动作且无兜底时抛出
      异常2: HandlerExecutionError - handler 抛出时包装
    [来源标注] [DD-001:MD-009] + [DD-M推断:依据=Mediator 模式]
    """

    def __init__(self) -> None:
        """[函数名] __init__
        [职责] 初始化 Mediator
        [参数说明] 无
        [返回值] None
        [错误码] 无
        [前置条件] 无
        [后置条件] handlers 空表
        [并发安全] 是（启动期单线程装配）
        [幂等性] 是
        [来源标注] [DD-M推断:依据=Mediator 构造]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def register(self, action: str, handler: TeachingHandler) -> None:
        """[函数名] register
        [职责] 注册教学动作 handler
        [参数说明]
          参数1: action str 必填 动作名（白名单：feynman/fsrs/stage_change/idle）
          参数2: handler TeachingHandler 必填 异步处理函数
        [返回值]
          类型: None
        [错误码]
          错误码1: ValueError 含义 动作名非法 触发 不在白名单
        [前置条件] action ∈ 白名单
        [后置条件] handlers[action] 已更新
        [并发安全] 否（启动期注册）
        [幂等性] 否（重复注册覆盖）
        [性能约束] ≤1ms
        [来源标注] [DD-001:MD-009] + [DD-M推断:依据=Mediator 注册接口]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def unregister(self, action: str) -> None:
        """[函数名] unregister
        [职责] 注销 handler
        [参数说明]
          参数1: action str 必填 动作名
        [返回值] None
        [错误码] 无
        [前置条件] action 已注册
        [后置条件] handlers[action] 已移除
        [并发安全] 否
        [幂等性] 是（不存在则 noop）
        [来源标注] [DD-M推断:依据=Mediator 注销]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    async def dispatch(self, context: TeachingContext) -> ActionResult:
        """[函数名] dispatch
        [职责] 异步分派 context 到对应 handler
        [关联接口契约] IC-002 学习回合
        [参数说明]
          参数1: context TeachingContext 必填 教学上下文
        [返回值]
          类型: ActionResult
          描述: handler 返回值；无匹配走 fallback
        [错误码]
          错误码1: E00901 LLM 评分失败 - feynman handler 抛出
          错误码2: E00903 FSRS 版本低 - fsrs handler 抛出
        [前置条件] context.action 非空
        [后置条件] 对应 handler 已执行
        [并发安全] 是（asyncio）
        [幂等性] 否
        [性能约束] ≤200ms（P95）
        [示例]
          ```
          ctx = TeachingContext(user_id="u", session_id="s", action="feynman")
          result = await dispatcher.dispatch(ctx)
          ```
        [来源标注] [DD-001:IC-002] + [DD-M推断:依据=Mediator 异步分发]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def set_fallback(self, handler: TeachingHandler) -> None:
        """[函数名] set_fallback
        [职责] 设置兜底 handler（未匹配动作时调用）
        [参数说明]
          参数1: handler TeachingHandler 必填 兜底处理函数
        [返回值] None
        [错误码] 无
        [前置条件] 无
        [后置条件] fallback_handler 已设置
        [并发安全] 否（启动期配置）
        [幂等性] 是
        [来源标注] [DD-M推断:依据=Mediator 兜底]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError
