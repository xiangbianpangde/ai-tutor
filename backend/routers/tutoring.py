"""tutoring 引擎 router（前缀 /api/tutoring）。

C1：仅 /health。后续波次迁入 cold-start / sessions / progress / checkpoint /
insight / review-plan（REST）+ /ws/tutoring/{session_id}（WebSocket 教学循环）。
"""
from __future__ import annotations

from ._common import engine_router

router = engine_router("tutoring")
