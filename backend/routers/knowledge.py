"""knowledge 引擎 router（前缀 /api/knowledge）。

C1：仅 /health。后续波次迁入 acquire / graphs / query / review / update / diff /
rollback / conflicts（设计文档-后端API层 §knowledge 9 endpoint）。
"""
from __future__ import annotations

from ._common import engine_router

router = engine_router("knowledge")
