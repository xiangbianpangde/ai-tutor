"""adapter - 路由策略适配器（M-008）

> 对应模块: M-008 子模块 sm008-routing
> 设计模式: Adapter（封装不同路由策略的统一接口）
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008] + [调研报告:RI-009]
"""
from __future__ import annotations

# 标准库
import abc
from typing import Literal

# 第三方库
import structlog

# 本地模块
from aitutor.rag.routing.keyword import KeywordRouter
from aitutor.shared.types import RouteDecision

logger = structlog.get_logger(__name__)


class RoutingAdapter(abc.ABC):
    """路由策略适配器抽象基类。

    [职责] 定义路由策略的统一接口（Template Method）
    [关联设计规范] MD-M-008

    [属性]
        strategy_name: str - 策略名（用于日志/metrics）

    [方法列表]
        route(query) -> RouteDecision - 抽象路由方法
        fallback(query) -> RouteDecision - 兜底路由（默认 RAG）

    [来源标注] [DD-001:MD-M-008] + [DD推断:依据=Template Method 模式]
    """

    def __init__(self, *, strategy_name: str) -> None:
        """构造路由适配器。

        [函数名] __init__
        [职责] 初始化策略名

        [参数说明]
            参数1: strategy_name str 必填 策略名（如 "keyword" / "llm"）
        """
        self.strategy_name = strategy_name

    @abc.abstractmethod
    async def route(self, query: str) -> RouteDecision:
        """抽象路由方法。

        [函数名] route
        [职责] 由子类实现具体路由逻辑
        [关联接口契约] IC-003

        [参数说明]
            参数1: query str 必填 用户 query

        [返回值]
            类型: RouteDecision
            描述: 路由决策字面量

        [来源标注] [DD-001:IC-003 route_decision]
        """
        raise NotImplementedError

    async def fallback(self, query: str) -> RouteDecision:
        """兜底路由方法。

        [函数名] fallback
        [职责] 路由失败时返回兜底决策

        [参数说明]
            参数1: query str 必填 原始 query

        [返回值]
            类型: RouteDecision
            描述: 兜底路由（默认 rag）

        [来源标注] [DD-001:IC-003 E00803 重路由失败兜底]
        """
        # [DD-M推断:依据=MD-M-008 异常处理 E00803 重路由]
        return "rag"


class KeywordRoutingAdapter(RoutingAdapter):
    """关键字路由适配器（默认实现）。"""

    def __init__(self, keywords: dict[str, list[str]]) -> None:
        """构造关键字路由适配器。

        [函数名] __init__
        [职责] 包装 KeywordRouter

        [参数说明]
            参数1: keywords Dict[str, List[str]] 必填 关键字配置
        """
        # [DD-M推断:依据=Adapter 模式委托给 Adaptee]
        super().__init__(strategy_name="keyword")
        self._router = KeywordRouter(keywords)

    async def route(self, query: str) -> RouteDecision:
        """委托给 KeywordRouter.route。

        [函数名] route
        [职责] Adapter 模式委派

        [来源标注] [DD-001:MD-M-008]
        """
        # [DD-M推断:依据=Adapter 委派]
        return await self._router.route(query)


# 文件头注释覆盖
# [文件路径] src/aitutor/rag/routing/adapter.py
# [文件职责] 路由策略适配器（Template + Adapter 组合）
# [所属模块] M-008 子模块 sm008-routing
# [关联设计规范] FS-M-008 / MD-M-008 / IC-003
# [输入输出]
#   输入: query 字符串
#   输出: RouteDecision 字面量
# [依赖关系]
#   依赖文件: routing/keyword.py, shared/types.py
#   被依赖文件: rag/engine.py
# [注意事项]
#   注意1: 新增路由策略只需继承 RoutingAdapter，不修改 engine.py（OCP）
#   注意2: V4.5 POC 可新增 LLMRoutingAdapter 不影响调用方
# [代码风格] 遵循 CS-NNN
# [创建日期] 2026-06-02
# [作者] DD-M-008-20260602
# [来源标注] [DD-001:FS-M-008] + [DD-001:MD-M-008]
