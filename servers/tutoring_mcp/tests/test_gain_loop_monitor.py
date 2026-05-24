"""GainLoopMonitor 契约测试。

合同来源: ai-tutor-system-design/specs/pgfga-integration.md §5

接口:
    detect_break(signals, recent_skipped_count) → GainLoopBreak | None
    repair(break_type) → TeachingAction(type=break_suggestion, content=...)

4 种断裂:
- student_withdrawal      withdrawal_pattern + help_seeking_spike
- emotional_flattening    emotional_flatness 且无正面信号
- surface_responses       withdrawal_pattern 但有 help_seeking_spike → 求表面帮助
- avoidance_pattern       recent_skipped_count ≥ 3

每种 break_type 对应一个修复 TeachingAction（不评判、不说教，PGFGA 三铁律合规）。
"""
from __future__ import annotations

import pytest

from shared.schemas import FlowSignals, TeachingAction


def _sigs(**kw) -> FlowSignals:
    return FlowSignals(**kw)


def test_detect_student_withdrawal() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import detect_break

    sigs = _sigs(withdrawal_pattern=True, emotional_flatness=True)
    brk = detect_break(signals=sigs, recent_skipped_count=0)
    assert brk is not None
    assert brk.type == "student_withdrawal"


def test_detect_emotional_flattening() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import detect_break

    # 不含 withdrawal，但持续无情绪标记 + 无正面信号
    sigs = _sigs(emotional_flatness=True)
    brk = detect_break(signals=sigs, recent_skipped_count=0)
    assert brk is not None
    assert brk.type == "emotional_flattening"


def test_detect_surface_responses() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import detect_break

    sigs = _sigs(help_seeking_spike=True, withdrawal_pattern=True)
    brk = detect_break(signals=sigs, recent_skipped_count=0)
    # 学生回答短 + 频繁求助 = 表面应付
    assert brk is not None
    assert brk.type in ("surface_responses", "student_withdrawal")


def test_detect_avoidance_pattern() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import detect_break

    sigs = _sigs()  # 信号都 OK
    brk = detect_break(signals=sigs, recent_skipped_count=3)
    assert brk is not None
    assert brk.type == "avoidance_pattern"


def test_no_break_when_signals_positive() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import detect_break

    sigs = _sigs(
        answer_length_growth=True,
        initiative_taking=True,
        depth_increasing=True,
    )
    assert detect_break(signals=sigs, recent_skipped_count=0) is None


def test_no_break_when_no_signals_no_skips() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import detect_break

    sigs = _sigs()
    assert detect_break(signals=sigs, recent_skipped_count=0) is None


def test_repair_withdrawal_offers_safety() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import repair, GainLoopBreakType

    act = repair(break_type="student_withdrawal")
    assert isinstance(act, TeachingAction)
    assert act.type == "break_suggestion"
    # PGFGA: 不要说教
    forbidden = ["你应该", "不对", "想太多", "请认真"]
    assert all(w not in act.content for w in forbidden)
    # 应含安全感建立的措辞
    assert any(w in act.content for w in ("不需要", "半成品", "可以", "我们", "试试"))


def test_repair_emotional_flattening_invites_care() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import repair

    act = repair(break_type="emotional_flattening")
    assert "休息" in act.content or "状态" in act.content or "感觉" in act.content


def test_repair_avoidance_invites_reframe() -> None:
    from servers.tutoring_mcp.gain_loop_monitor import repair

    act = repair(break_type="avoidance_pattern")
    # 跳过模式 → 提议换切入点
    assert any(w in act.content for w in ("切入", "换", "感兴趣", "换个角度"))


def test_repair_unknown_returns_safe_default() -> None:
    """未知 break_type → 返回安全默认 action（不抛错）。"""
    from servers.tutoring_mcp.gain_loop_monitor import repair

    act = repair(break_type="alien_break")  # type: ignore[arg-type]
    assert isinstance(act, TeachingAction)
    assert act.type == "break_suggestion"


def test_repair_actions_pass_firewall() -> None:
    """所有 repair action 必须通过 NonJudgmentFirewall。"""
    from servers.tutoring_mcp.gain_loop_monitor import repair
    from servers.tutoring_mcp.non_judgment_firewall import NonJudgmentFirewall

    fw = NonJudgmentFirewall()
    for bt in ("student_withdrawal", "emotional_flattening",
                "surface_responses", "avoidance_pattern"):
        act = repair(break_type=bt)
        assert fw.scan(act.content) is None, f"{bt} 修复词触犯防火墙：{act.content}"
