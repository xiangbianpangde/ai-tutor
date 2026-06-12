"""M-002 API 网关 + WS - v1 APIRouter 注册入口。

[文件路径] src/aitutor/api/v1/__init__.py
[文件职责] v1 命名空间初始化，统一注册 session/turn/ingest/health/ws 五个 APIRouter。
[所属模块] M-002 API 网关 + WS
[关联设计规范] FS-M-002 / MD-M-002
[功能描述]
  功能1: 导出 v1 APIRouter 聚合根（v1_router）
  功能2: 提供 register_v1(app) 入口供 M-001 AppLauncher 装配
  功能3: 统一添加 v1 前缀（/api/v1）、统一 tags、统一依赖
[输入输出]
  输入: FastAPI app 实例
  输出: app 上挂载 v1_router
[依赖关系]
  依赖文件: ./session.py / ./turn.py / ./ingest.py / ./health.py / ./ws.py
  被依赖文件: ../__init__.py
[注意事项]
  注意1: 严禁循环导入（Import Linter 强制）
  注意2: 统一错误响应格式（RFC 7807）
  注意3: v1 前缀硬编码 /api/v1（V2 时再升级）
[代码风格] 遵循 CS-NNN（DD-001 第六节）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-002 - 初始框架（占位 + 注释，无业务代码）
[作者] DD-M-002-20260602
[来源标注] [DD-001:FS-M-002] + [DD-M推断:依据=FastAPI APIRouter 聚合]
"""

# 仅注释占位，无业务代码（由 DD-S 实现）
# from fastapi import APIRouter
# v1_router = APIRouter(prefix="/api/v1")
# from .session import router as session_router
# from .turn import router as turn_router
# from .ingest import router as ingest_router
# from .health import router as health_router
# from .ws import router as ws_router
# v1_router.include_router(session_router, prefix="/session", tags=["session"])
# v1_router.include_router(turn_router, prefix="/turn", tags=["turn"])
# v1_router.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
# v1_router.include_router(health_router, prefix="/health", tags=["health"])
# v1_router.include_router(ws_router, prefix="/ws", tags=["ws"])


# [类注释] APIRouterRegistry
# [类名] APIRouterRegistry
# [职责] APIRouter 注册中心（Proxy 模式），统一管理 v1/* 子路由挂载
# [关联设计规范] MD-M-002
# [属性]
#   属性1: routes  类型: List[APIRouter]  描述: 已注册 router 列表
#   属性2: prefix  类型: str  默认 "/api/v1"  描述: 统一前缀
#   属性3: tags  类型: List[str]  描述: 路由 tag 列表（OpenAPI 用）
# [方法列表]
#   方法1: register(router: APIRouter, prefix: str) -> None 职责: 注册单个 router
#   方法2: mount(app: FastAPI) -> None 职责: 挂载到 FastAPI app
#   方法3: list_routes() -> List[APIRouter] 职责: 列出所有已注册 router
# [状态机] N/A
# [异常处理]
#   异常1: DuplicateRouteError 触发: 同 prefix 重复注册
#   异常2: MountError 触发: app 挂载失败
# [来源标注] [DD-001:MD-M-002] + [DD-M推断:依据=Proxy 模式封装路由]
# class APIRouterRegistry:
#     def __init__(self) -> None:
#         self.routes: List[APIRouter] = []
#         self.prefix = "/api/v1"
#         self.tags: List[str] = []
#         pass


# [函数签名注释] register_router
# [函数名] register_router
# [职责] 注册单个 APIRouter 到 registry
# [关联接口契约] IC-001 服务启动
# [参数说明]
#   参数1: router  类型: APIRouter  必填  描述: 要注册的 FastAPI APIRouter
#   参数2: prefix  类型: str  必填  描述: 子路径前缀（如 "/session"）  校验规则: 必须以 "/" 开头
# [返回值] None
# [错误码] N/A
# [前置条件] router 内部路由无冲突
# [后置条件] registry.routes 长度 +1
# [并发安全] N/A（启动期单线程）
# [幂等性] 否（重复注册会触发 DuplicateRouteError）
# [性能约束] ≤ 1ms
# [来源标注] [DD-001:MD-M-002] + [DD-M推断:依据=FastAPI include_router 包装]
# def register_router(router: APIRouter, prefix: str) -> None:
#     pass
