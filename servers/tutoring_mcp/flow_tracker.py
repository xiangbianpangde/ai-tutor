"""PGFGA 心流状态机 — 把 FlowSignals 映射到 FlowLevel 转移。

合同来源: ai-tutor-system-design/specs/pgfga-integration.md §2.3

规则:
- 累积净分 = #positive - #negative
- 单轮最多升 1 级 / 降 N 级（按净分绝对值）
- 防火墙违规一次 → 强制 SILENT（PGFGA "回路断裂"原则）
- SILENT 是地板，IMMERSED 是天花板
"""
from __future__ import annotations

from shared.schemas import FlowLevel, FlowSignals

_POSITIVE_FIELDS = (
    "answer_length_growth",
    "depth_increasing",
    "initiative_taking",
    "hesitation_decreasing",
    "inter_turn_speed_up",
    "self_correction_quality",
)
_NEGATIVE_FIELDS = (
    "withdrawal_pattern",
    "help_seeking_spike",
    "answer_regression",
    "emotional_flatness",
)


def _score(signals: FlowSignals) -> int:
    pos = sum(int(getattr(signals, f)) for f in _POSITIVE_FIELDS)
    neg = sum(int(getattr(signals, f)) for f in _NEGATIVE_FIELDS)
    return pos - neg


def next_flow_level(
    *,
    current_level: FlowLevel,
    signals: FlowSignals,
    firewall_violation: bool = False,
) -> FlowLevel:
    if firewall_violation:
        return FlowLevel.SILENT

    net = _score(signals)
    cur = int(current_level)

    if net >= 2:
        new = cur + 1
    elif net <= -2:
        new = cur - 2  # 负信号强 → 跌 2 级
    elif net == 1:
        new = cur + 1 if cur < int(FlowLevel.IMMERSED) else cur
    elif net == -1:
        new = cur - 1
    else:
        new = cur

    # 边界
    new = max(int(FlowLevel.SILENT), min(int(FlowLevel.IMMERSED), new))
    return FlowLevel(new)
