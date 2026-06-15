"""backend.redline —— 红线编排（M-016，v3.1 新增模块）。

把 ruff / import-linter / pytest 等红线工具收进可编程入口，统一成 ToolResult 聚合。
"""
from __future__ import annotations

from .orchestrator import (
    RedlineOrchestrator,
    RedlineTool,
    ToolResult,
    default_runner,
    default_tools,
)

__all__ = ["RedlineOrchestrator", "RedlineTool", "ToolResult", "default_runner", "default_tools"]
