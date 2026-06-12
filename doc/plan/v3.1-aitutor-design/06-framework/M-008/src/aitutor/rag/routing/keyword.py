"""keyword - 关键字路由策略（M-008）

> 对应模块: M-008 子模块 sm008-routing
> 关联接口: IC-003（route_decision 字段）
> 关联选型: TS-001 Python
> 设计模式: Strategy（默认实现）
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-001:IC-003]
"""
from __future__ import annotations

# 标准库
from typing import Dict, Literal

# 第三方库
import structlog

# 本地模块
from aitutor.shared.types import RouteDecision

logger = structlog.get_logger(__name__)


class KeywordRouter:
    """关键字路由器 - 默认路由策略。

    [职责] 基于关键字匹配决定 direct / rag / web 路由
    [关联设计规范] MD-M-008

    [属性]
        keywords: Dict[str, List[str]] - 关键字集合 {意图: [词]}
        default_route: RouteDecision - 默认路由（默认 rag）

    [方法列表]
        route(query) -> RouteDecision - 路由决策
        _match_intent(query) -> str - 内部关键字匹配

    [状态机] N/A
    [异常处理]
        RoutingError: 路由匹配过程异常

    [来源标注] [DD-001:MD-M-008] + [DD-001:IC-003 route_decision]
    """

    # 路由决策字面量（IC-003 出参）
    ROUTE_DIRECT = "direct"
    ROUTE_RAG = "rag"
    ROUTE_WEB = "web"
    ROUTE_CANNOT_CONFIRM = "cannot_confirm"

    def __init__(
        self,
        keywords: Dict[str, list[str]],
        *,
        default_route: RouteDecision = "rag",
    ) -> None:
        """构造关键字路由器。

        [函数名] __init__
        [职责] 加载关键字配置并设置默认路由

        [参数说明]
            参数1: keywords Dict[str, List[str]] 必填 {意图: 词列表}
            参数2: default_route RouteDecision 可选 默认 rag 兜底路由

        [来源标注] [DD-001:MD-M-008 KeywordRouter]
        """
        # [DD-M推断:依据=MD-M-008 类设计 keywords: Dict]
        self.keywords = keywords
        self.default_route = default_route

    async def route(self, query: str) -> RouteDecision:
        """根据 query 内容决策路由。

        [函数名] route
        [职责] 关键字匹配 + 兜底 default_route
        [关联接口契约] IC-003（route_decision 字段）

        [参数说明]
            参数1: query str 必填 规则 长度 [1, 2000] 用户 query

        [返回值]
            类型: RouteDecision
            描述: "direct" | "rag" | "web" | "cannot_confirm"
            特殊值: 无匹配时返回 default_route

        [错误码]
            错误码1: E00803 含义: 重路由失败 触发: 1 次重试仍败

        [前置条件] query 非空
        [后置条件] trace_id 关联
        [并发安全] 是
        [幂等性] 是 / 幂等键: query_hash
        [性能约束] ≤50ms

        [示例]
            ```
            # 调用示例
            decision = await router.route("今天天气如何")
            # 命中 web 关键字 → 返回 "web"
            ```

        [来源标注] [DD-001:MD-M-008] + [DD-001:IC-003]
        """
        # [DD-M推断:依据=MD-M-008 KeywordRouter.route(query)]
        pass


# 文件头注释覆盖
# [文件路径] src/aitutor/rag/routing/keyword.py
# [文件职责] 关键字路由策略（默认 Strategy 实现）
# [所属模块] M-008 子模块 sm008-routing
# [关联设计规范] FS-M-008 / MD-M-008 / IC-003
# [输入输出]
#   输入: query 字符串
#   输出: RouteDecision 字面量
# [依赖关系]
#   依赖文件: shared/types.py
#   被依赖文件: routing/adapter.py
# [注意事项]
#   注意1: 关键字匹配大小写不敏感（统一 lowercase）
#   注意2: V4.5 POC 可替换为 LLM 路由（接口一致）
# [代码风格] 遵循 CS-NNN
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-008 - 初始创建
# [作者] DD-M-008-20260602
# [来源标注] [DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-001:IC-003]
