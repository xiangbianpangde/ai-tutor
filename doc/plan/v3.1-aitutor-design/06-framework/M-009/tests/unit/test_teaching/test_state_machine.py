"""test_state_machine - TeachingStateMachine 单元测试

[文件路径] tests/unit/test_teaching/test_state_machine.py
[文件职责] 教学 FSM 单测：6 状态 + 6 事件 + 转换合法性
[所属模块] M-009 测试
[关联设计规范] MD-009
[测试场景与断言]
  场景1: IDLE + user_input → LEARN
    断言: 转换合法
    Mock: 无
  场景2: LEARN + feynman_done → REVIEW
    断言: 转换合法
    Mock: 无
  场景3: REVIEW + fsrs_due → PRACTICE
    断言: 转换合法
    Mock: 无
  场景4: PRACTICE + again_count>=3 → REST
    断言: 转换合法
    Mock: 无
  场景5: REST + timer_done → LEARN
    断言: 转换合法
    Mock: 无
  场景6: 任意态 + stage_change → STAGE_ADJUST
    断言: 通配转换合法
    Mock: 无
  场景7: STAGE_ADJUST + user_input → LEARN
    断言: 退出校准
    Mock: 无
  场景8: 非法事件
    断言: 抛 TeachingFSMStuckError（E00902）
    Mock: 无
  场景9: 状态机复位
    断言: current_state=IDLE、last_event=None
    Mock: 无
  场景10: can_transition 守卫
    断言: 合法 True、非法 False
    Mock: 无
[Mock 策略] 无外部依赖；直接 new 状态机
[代码风格] 遵循 CS-AITutor-V3.1
[创建日期] 2026-06-02
[作者] DD-M-M-009-20260602
[来源标注] [DD-001:MD-009] + [DD-M推断:依据=FSM 单测标准]
"""

from __future__ import annotations

import pytest

# 预留：from aitutor.teaching.state_machine import TeachingStateMachine, TeachingState, TeachingEvent, TeachingFSMStuckError


@pytest.mark.parametrize(
    "current_state,event,expected",
    [
        ("IDLE", "user_input", "LEARN"),
        ("LEARN", "feynman_done", "REVIEW"),
        ("REVIEW", "fsrs_due", "PRACTICE"),
        ("PRACTICE", "again_count>=3", "REST"),
        ("REST", "timer_done", "LEARN"),
        ("STAGE_ADJUST", "user_input", "LEARN"),
    ],
)
def test_legal_transitions(current_state: str, event: str, expected: str) -> None:
    """[测试场景] 场景1-5,7 合法转换
    [断言] transition 返回 expected
    [Mock] 无"""
    # TODO: DD-S 将在此填充实现
    pytest.skip("DD-S 待实现")


@pytest.mark.parametrize(
    "current_state",
    ["IDLE", "LEARN", "REVIEW", "PRACTICE", "REST"],
)
def test_stage_change_wildcard(current_state: str) -> None:
    """[测试场景] 场景6 通配 stage_change
    [断言] 任意态下 stage_change → STAGE_ADJUST
    [Mock] 无"""
    # TODO: DD-S 将在此填充实现
    pytest.skip("DD-S 待实现")


def test_illegal_transition_raises() -> None:
    """[测试场景] 场景8 非法事件
    [断言] 抛 TeachingFSMStuckError
    [Mock] 无"""
    # TODO: DD-S 将在此填充实现
    pytest.skip("DD-S 待实现")


def test_reset_returns_to_idle() -> None:
    """[测试场景] 场景9 复位
    [断言] current_state=IDLE、last_event=None
    [Mock] 无"""
    # TODO: DD-S 将在此填充实现
    pytest.skip("DD-S 待实现")


def test_can_transition_guard() -> None:
    """[测试场景] 场景10 can_transition 守卫
    [断言] 合法 True、非法 False
    [Mock] 无"""
    # TODO: DD-S 将在此填充实现
    pytest.skip("DD-S 待实现")
