"""backend.middleware —— 横切中间件（Session / Cache / Monitor / 事件总线 …）。

对应 v2 #3 中间件层 / v3.1 M-004~M-007。被 routers/app 装配使用；
架构契约：本层不反向依赖 routers/app/main。
"""
from __future__ import annotations

from .cache_layer import CacheLayer
from .event_bus import Event, EventBus, EventRecorder
from .file_manager import FileManager
from .session_manager import SessionManager
from .task_manager import ProgressReporter, TaskManager

__all__ = [
    "CacheLayer",
    "Event",
    "EventBus",
    "EventRecorder",
    "FileManager",
    "ProgressReporter",
    "SessionManager",
    "TaskManager",
]
