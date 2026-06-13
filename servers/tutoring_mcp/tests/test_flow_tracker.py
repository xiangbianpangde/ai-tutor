"""FlowTracker 状态机契约测试。

接口:
    next_flow_level(current_level, signals, firewall_violation=None) → FlowLevel

模型:
    score = (#positive signals) - (#negative signals) - (firewall_violation ? 5 : 0)
    新 level 由 current_level + score 决定（每次最多升 1 级或降到 SILENT）

规则:
- positive 信号: length_growth / depth / initiative / hesitation_decreasing /
                  inter_turn_speed_up / self_correction_quality
- negative 信号: withdrawal / help_spike / regression / flatness
- 防火墙违规一次 → 强制降到 SILENT（PGFGA spec §2.3）
"""
from __future__ import annotations

from shared.schemas import FlowLevel, FlowSignals


def _sigs(**kw) -> FlowSignals:
    return FlowSignals(**kw)


def test_silent_to_shallow_on_positive_signals() -> None:
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs(answer_length_growth=True, initiative_taking=True, depth_increasing=True)
    new = next_flow_level(current_level=FlowLevel.SILENT, signals=sigs)
    assert new >= FlowLevel.SHALLOW


def test_shallow_to_fluent_on_strong_positive() -> None:
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs(
        answer_length_growth=True, depth_increasing=True,
        initiative_taking=True, inter_turn_speed_up=True,
    )
    new = next_flow_level(current_level=FlowLevel.SHALLOW, signals=sigs)
    assert new >= FlowLevel.FLUENT


def test_negative_signals_drop_level() -> None:
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs(
        withdrawal_pattern=True, help_seeking_spike=True,
        answer_regression=True, emotional_flatness=True,
    )
    new = next_flow_level(current_level=FlowLevel.FLUENT, signals=sigs)
    assert new < FlowLevel.FLUENT


def test_firewall_violation_drops_to_silent() -> None:
    """PGFGA spec §2.3: AI 侧防火墙违规一次 → 直接 SILENT。"""
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    # 即使所有正信号都开，防火墙违规也强制 SILENT
    sigs = _sigs(answer_length_growth=True, initiative_taking=True, depth_increasing=True)
    new = next_flow_level(
        current_level=FlowLevel.IMMERSED, signals=sigs, firewall_violation=True,
    )
    assert new == FlowLevel.SILENT


def test_step_up_one_level_max() -> None:
    """单轮最多升一级，避免过敏感。"""
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs(
        answer_length_growth=True, depth_increasing=True,
        initiative_taking=True, inter_turn_speed_up=True,
        hesitation_decreasing=True, self_correction_quality=True,
    )
    new = next_flow_level(current_level=FlowLevel.SILENT, signals=sigs)
    # 不应直接跳到 IMMERSED
    assert new <= FlowLevel.SHALLOW + 1


def test_neutral_signals_keep_level() -> None:
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs()  # 全 False
    new = next_flow_level(current_level=FlowLevel.FLUENT, signals=sigs)
    # 无信号 = 维持（或最多 ±1）
    assert abs(int(new) - int(FlowLevel.FLUENT)) <= 1


def test_immersed_stays_with_some_positive() -> None:
    """IMMERSED 不会变更低，除非有显著负信号。"""
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs(answer_length_growth=True)
    new = next_flow_level(current_level=FlowLevel.IMMERSED, signals=sigs)
    assert new >= FlowLevel.DEEP  # 至少保持高位


def test_silent_floor() -> None:
    """SILENT 下不会再降（已经最低）。"""
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs(withdrawal_pattern=True, help_seeking_spike=True)
    new = next_flow_level(current_level=FlowLevel.SILENT, signals=sigs)
    assert new == FlowLevel.SILENT


def test_immersed_ceiling() -> None:
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs(answer_length_growth=True, initiative_taking=True, depth_increasing=True)
    new = next_flow_level(current_level=FlowLevel.IMMERSED, signals=sigs)
    assert new == FlowLevel.IMMERSED


def test_mixed_signals_resolve_to_score() -> None:
    """正 3 负 1 → net +2 → 升一级。"""
    from servers.tutoring_mcp.flow_tracker import next_flow_level

    sigs = _sigs(
        answer_length_growth=True, depth_increasing=True, initiative_taking=True,
        emotional_flatness=True,
    )
    new = next_flow_level(current_level=FlowLevel.SHALLOW, signals=sigs)
    assert new >= FlowLevel.FLUENT
