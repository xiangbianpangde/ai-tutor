"""backend.teaching —— 教学编排（M-009，对应 v2 #10 部分）。

把 v1 TeachingEngine 包成 REST 可驱动的会话编排，接线 M-004 会话 + M-006 事件。
"""
from __future__ import annotations

from .orchestrator import TeachingOrchestrator

__all__ = ["TeachingOrchestrator"]
