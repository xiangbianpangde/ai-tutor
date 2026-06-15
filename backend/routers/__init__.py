"""backend.routers —— 四引擎 REST/WS 路由。

各引擎一个 router，挂在 ``/api/{engine}`` 前缀下；由 :func:`backend.app.create_app` 装配。
"""
from __future__ import annotations

from . import digest, knowledge, meta, sync, tasks, tutoring, ws  # noqa: F401

# (engine 名, router) —— create_app 按此挂载到 /api/{engine}
ENGINE_ROUTERS = [
    ("knowledge", knowledge.router),
    ("tutoring", tutoring.router),
    ("digest", digest.router),
    ("sync", sync.router),
]

__all__ = ["ENGINE_ROUTERS"]
