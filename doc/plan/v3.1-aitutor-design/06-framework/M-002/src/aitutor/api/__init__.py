"""M-002 API 网关 + WS - 模块初始化。

[文件路径] src/aitutor/api/__init__.py
[文件职责] API 网关模块初始化，导出公共接口与 Router 注册入口。
[所属模块] M-002 API 网关 + WS
[关联设计规范] FS-M-002 / MD-M-002
[功能描述]
  功能1: 导出 APIRouterRegistry、AuthDependency、WSConnectionManager、RateLimiter、OpenAPIGenerator 等公共类
  功能2: 提供 register_router(router, prefix) 入口供 M-001 AppLauncher 装配
  功能3: 定义模块级常量（MAX_CONNECTIONS、QPS_PER_USER、CONCURRENT_TURNS）
[输入输出]
  输入: 无（初始化时执行）
  输出: 暴露模块公共符号供外部 import
[依赖关系]
  依赖文件: ./deps.py / ./auth.py / ./rate_limit.py / ./openapi.py / ./v1/*
  被依赖文件: src/aitutor/main.py (M-001) / src/aitutor/app_factory.py
[注意事项]
  注意1: 严禁在 __init__.py 中实现业务逻辑（CS-NNN 规范）
  注意2: 严禁循环导入（Import Linter 强制）
  注意3: 公开符号必须显式列出（避免通配符导出）
[代码风格] 遵循 CS-NNN（DD-001 第六节）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-002 - 初始框架（占位 + 注释，无业务代码）
[作者] DD-M-002-20260602
[来源标注] [DD-001:FS-M-002] + [DD-M推断:依据=M-002 模块入口初始化]
"""

# M-002 模块公共接口（仅注释占位，无业务代码实现）
# 业务代码由 DD-S 阶段实现
#
# from .deps import get_current_user  # noqa: F401
# from .auth import AuthDependency  # noqa: F401
# from .rate_limit import RateLimiter  # noqa: F401
# from .openapi import OpenAPIGenerator  # noqa: F401
# from .v1 import session as v1_session  # noqa: F401
# from .v1 import turn as v1_turn  # noqa: F401
# from .v1 import ingest as v1_ingest  # noqa: F401
# from .v1 import health as v1_health  # noqa: F401
# from .v1 import ws as v1_ws  # noqa: F401

# [模块级常量 - 仅注释占位]
# MAX_CONNECTIONS: int = 1000  # WS 最大并发连接数（[AR:API-008]）
# QPS_PER_USER: int = 100  # 单用户 QPS 上限（[AR:API-002 限流]）
# CONCURRENT_TURNS: int = 10  # 单用户并发回合上限（[AR:API-002 限流]）

__all__ = [
    # "AuthDependency",
    # "RateLimiter",
    # "OpenAPIGenerator",
    # "v1_session",
    # "v1_turn",
    # "v1_ingest",
    # "v1_health",
    # "v1_ws",
]
