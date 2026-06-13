"""backend.app —— FastAPI 应用工厂（M-001 服务入口 + M-002 API 网关）。

职责：装配 FastAPI 应用 = CORS + 统一异常信封 + 生命周期（DB 自动初始化）+
四引擎 router 挂载。入口见 :mod:`backend.main`。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .config import AppConfig, get_config
from .core import RelationalStore, TutorError, get_logger
from .middleware import CacheLayer
from .responses import error_payload, ok, status_for
from .routers import ENGINE_ROUTERS, meta

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger("backend.app")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动时建库（``RelationalStore`` 构造即 create_all 14 张表）。

    DB 初始化失败不让整个进程崩——记录到 ``app.state.db_error``，由触库请求时
    经 DATABASE_ERROR 信封上报（liveness 探针 /health 不依赖 DB，仍可用）。
    """
    config: AppConfig = app.state.config
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        store = RelationalStore(config.db_url)
        store.init_schema()  # 建 14 表（开发期一键；生产走 alembic）
        app.state.store = store
        app.state.cache = CacheLayer(config.db_url)  # 落同库 cache_entries 表
        app.state.db_error = None
        logger.info(
            "backend.startup",
            host=config.host,
            port=config.port,
            db=str(config.db_path),
        )
    except SQLAlchemyError as exc:
        app.state.store = None
        app.state.cache = None
        app.state.db_error = str(exc)
        logger.error("backend.db_init_failed", error=str(exc))
    yield
    logger.info("backend.shutdown")


def create_app(config: AppConfig | None = None) -> FastAPI:
    """构造并返回 FastAPI 应用。``config`` 省略时取进程单例配置。"""
    config = config or get_config()

    app = FastAPI(title="AI-Tutor", version=config.app_version, lifespan=_lifespan)
    app.state.config = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_exception_handlers(app)

    @app.get("/", tags=["meta"], summary="服务信息")
    async def root() -> dict:
        return ok(
            {
                "app": config.app_name,
                "version": config.app_version,
                "docs": "/docs",
                "engines": [name for name, _ in ENGINE_ROUTERS],
            }
        )

    for name, router in ENGINE_ROUTERS:
        app.include_router(router, prefix=f"/api/{name}")
    app.include_router(meta.router, prefix="/api/meta")

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """把 TutorError / 数据库错误 / 兜底异常统一成失败信封。"""

    @app.exception_handler(TutorError)
    async def _on_tutor_error(request: Request, exc: TutorError) -> JSONResponse:
        return JSONResponse(status_code=status_for(exc.code), content=error_payload(exc))

    @app.exception_handler(SQLAlchemyError)
    async def _on_db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("backend.db_error", path=request.url.path, error=str(exc))
        err = TutorError("DATABASE_ERROR", "数据库错误", hint="检查 data/tutor.db 是否可用")
        return JSONResponse(status_code=500, content=error_payload(err))

    @app.exception_handler(Exception)
    async def _on_unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("backend.unhandled", path=request.url.path, error=str(exc))
        err = TutorError("INTERNAL_ERROR", "服务器内部错误", hint=str(exc))
        return JSONResponse(status_code=500, content=error_payload(err))
