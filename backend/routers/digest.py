"""digest 引擎 router（前缀 /api/digest）。

C1：仅 /health。后续波次迁入 generate / quiz / slides（设计文档-后端API层 §digest）。
"""
from __future__ import annotations

from ._common import engine_router

router = engine_router("digest")
