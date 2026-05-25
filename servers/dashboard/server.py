"""状态面板 Web server — Starlette + uvicorn（零新依赖，二者由 fastmcp 传递引入）。

只读：GET / 返回单文件 HTML；GET /api/state 返回 get_dashboard_state 的 JSON。
启动： uv run python -m servers.dashboard.server   →  http://localhost:8501
与 4 个 MCP server 共享同一 SQLite（DATABASE_URL / 默认 data/tutor.db），独立进程。
"""
from __future__ import annotations

import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from servers.dashboard.layer_state import LAYER_FUNCS
from servers.dashboard.state import get_dashboard_state
from shared.logging_config import get_logger
from shared.storage import RelationalStore

logger = get_logger("dashboard.server")
_TEMPLATES = Path(__file__).parent / "templates"
_INDEX = _TEMPLATES / "index.html"
_LAYERS = _TEMPLATES / "layers.html"


def _db() -> RelationalStore:
    return RelationalStore.from_env()


async def index(_request: Request) -> HTMLResponse:
    return HTMLResponse(_INDEX.read_text(encoding="utf-8"))


async def layers_page(_request: Request) -> HTMLResponse:
    return HTMLResponse(_LAYERS.read_text(encoding="utf-8"))


async def api_state(_request: Request) -> JSONResponse:
    try:
        return JSONResponse(get_dashboard_state(_db()))
    except Exception as exc:  # noqa: BLE001 — 面板永不因数据异常而崩
        logger.warning("dashboard.state_failed", error=str(exc))
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=200)


async def api_layer(request: Request) -> JSONResponse:
    """GET /api/layer/{layer} —— 单层只读状态。未知层 → 404 风格 JSON。"""
    layer = request.path_params.get("layer", "")
    fn = LAYER_FUNCS.get(layer)
    if fn is None:
        return JSONResponse(
            {"error": f"unknown layer {layer!r}", "valid": list(LAYER_FUNCS)},
            status_code=404,
        )
    try:
        return JSONResponse({"layer": layer, **fn(_db())})
    except Exception as exc:  # noqa: BLE001 — 面板永不因数据异常而崩
        logger.warning("dashboard.layer_failed", layer=layer, error=str(exc))
        return JSONResponse({"layer": layer, "error": str(exc)}, status_code=200)


app = Starlette(routes=[
    Route("/", index),
    Route("/layers", layers_page),
    Route("/api/state", api_state),
    Route("/api/layer/{layer}", api_layer),
])


def main() -> None:
    import uvicorn

    port = int(os.environ.get("DASHBOARD_PORT", "8501"))
    logger.info("dashboard.start", port=port, db=_db().url)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
