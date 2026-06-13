"""backend —— v2 FastAPI 统一后端（M-001 服务入口 / M-002 API 网关 / …）。

v1 的 4 个 MCP server（`servers/`）与基础设施（`shared/`）逐步迁入此处；
C1 阶段复用而非重写（走向决议 C'），`backend.core` 桥接 `shared/`，
`backend.routers` 经各引擎对外暴露 REST/WS。
"""
from __future__ import annotations

__version__ = "2.0.0"
