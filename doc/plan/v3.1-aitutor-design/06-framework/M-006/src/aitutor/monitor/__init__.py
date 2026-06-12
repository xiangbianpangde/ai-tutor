"""monitor - 事件总线模块（Observer + Mediator）

> 对应模块: M-006
> 关联接口: IC-002（学习回合，含 trace_id）/ IC-008（WS 推送，含事件广播）
> 关联选型: TS-009 OpenTelemetry / TS-010 Prometheus
> 职责一句话: 提供 trace_id 传播、结构化日志与事件总线广播能力
> 来源标注: [AR:TS-009/010] + [AR:SEC-010] + [DD-001:MD-M-006]
"""
from __future__ import annotations

# 公共接口导出（仅 re-export，禁止业务实现）
# 注：所有 import 来自本包内部（bus / trace / logger），禁止跨模块 import
from aitutor.monitor.bus import EventBus, publish_event, subscribe
from aitutor.monitor.logger import StructuredLogger, get_logger
from aitutor.monitor.trace import (
    TraceContext,
    bind_trace_id,
    current_trace_id,
    new_trace_id,
)

__all__ = [
    "EventBus",
    "publish_event",
    "subscribe",
    "StructuredLogger",
    "get_logger",
    "TraceContext",
    "bind_trace_id",
    "current_trace_id",
    "new_trace_id",
]
