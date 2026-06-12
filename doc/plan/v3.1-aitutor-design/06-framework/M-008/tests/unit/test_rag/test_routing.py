"""test_routing - 路由子能力测试

> 对应模块: M-008 子模块 sm008-routing
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008]
"""
from __future__ import annotations

import pytest

# 本地模块
from aitutor.rag.routing.keyword import KeywordRouter
from aitutor.rag.routing.adapter import KeywordRoutingAdapter, RoutingAdapter


# ========== 测试场景注释 ==========

# [测试场景1: 关键字命中 "weather" 返回 web]
# 断言: route() == "web"
# Mock: 无

# [测试场景2: 关键字命中 "definition" 返回 direct]
# 断言: route() == "direct"
# Mock: 无

# [测试场景3: 无关键字命中返回 default_route]
# 断言: route() == "rag"（默认）
# Mock: 无

# [测试场景4: fallback() 兜底]
# 断言: fallback("任意 query") == "rag"
# Mock: 无

# [测试场景5: V4.5 LLM 路由可替换（OCP 验证）]
# 断言: 新增 LLMRoutingAdapter 继承 RoutingAdapter 不需要修改调用方
# Mock: MockLLMRoutingAdapter

# [测试场景6: 大小写不敏感匹配]
# 断言: "WEATHER" 与 "weather" 路由结果一致
# Mock: 无
