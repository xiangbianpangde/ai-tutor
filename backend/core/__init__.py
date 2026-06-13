"""backend.core —— 基础设施桥接层。

C1 阶段复用 v1 的 `shared/`（迁移而非重写，走向决议 C'）：backend 其余层
**只从这里取基础设施**，未来 `shared/` 物理迁入此处时上层 import 不必改动。

架构契约（import-linter）：本层不得反向依赖 `backend.routers/app/main`，
也不得直接依赖 `servers`（引擎由 routers 层装配）。
"""
from __future__ import annotations

from shared.errors import ERROR_CODES, TutorError, TutorErrorDetail
from shared.logging_config import get_logger
from shared.storage import RelationalStore

__all__ = [
    "ERROR_CODES",
    "RelationalStore",
    "TutorError",
    "TutorErrorDetail",
    "get_logger",
]
