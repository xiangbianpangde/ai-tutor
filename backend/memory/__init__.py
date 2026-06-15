"""backend.memory —— 长期记忆（M-013，对应 v2 #18 长期幻觉）。

已确认事实跨会话长存 + LRU 淘汰，供后续回答检索接地。
"""
from __future__ import annotations

from .longterm import LongTermMemory, extract_facts

__all__ = ["LongTermMemory", "extract_facts"]
