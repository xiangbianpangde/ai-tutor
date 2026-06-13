"""sync 引擎 router（前缀 /api/sync）。

C1：仅 /health。后续波次迁入 obsidian/push|pull|watch、git/init|push（设计文档-后端API层 §sync）。
"""
from __future__ import annotations

from ._common import engine_router

router = engine_router("sync")
