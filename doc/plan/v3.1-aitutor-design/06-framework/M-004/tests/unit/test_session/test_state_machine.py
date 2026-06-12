"""test_session.test_state_machine - M-004 Session FSM 单元测试

> 对应模块: M-004 Session
> 关联选型: TS-017 pytest
> 关联设计: CS-AITutor-V3.1 §6
> 来源标注: [DD-001:CS-001] + [DD-M推断:依据=MD-004 测试策略 14 用例]
"""

# [文件职责] SessionStateMachine 状态机单元测试（合法/非法转换 + timeout 路径）
# [所属模块] M-004
# [测试策略] 单测 / 14 用例中归属本文件 3 个核心场景（含 6 个状态机转换用例子集）
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-004 - 初始创建
# [作者] DD-M-004-20260602
# [来源标注] [DD-001:MD-004 测试策略]

import pytest

from aitutor.session.models import Session, SessionState, StateTransitionError
from aitutor.session.state_machine import SessionStateMachine, TRANSITIONS


class TestSessionStateMachineTransitions:
    """SessionStateMachine 转换测试。"""

    # --------------------------------------------------------
    # 测试场景 1：正常状态转换（NEW→ACTIVE）
    # --------------------------------------------------------
    # [测试场景] 合法转换路径
    # [断言] transition 返回 "ACTIVE" 且 session.state 变更
    # [Mock] 无
    def test_transition_new_to_active(self, sample_session: Session) -> None:
        """验证 NEW→ACTIVE 合法转换。"""
        ...

    # --------------------------------------------------------
    # 测试场景 2：非法状态转换（CLOSED→NEW）
    # --------------------------------------------------------
    # [测试场景] 非法转换路径
    # [断言] 抛 StateTransitionError（E00402 翻译）
    # [Mock] 无
    @pytest.mark.parametrize(
        "from_state,event",
        [
            (SessionState.CLOSED, "activate"),
            (SessionState.EXPIRED, "activate"),
            (SessionState.NEW, "suspend"),
            (SessionState.NEW, "close"),
        ],
    )
    def test_illegal_transition_raises(
        self,
        sample_user_id: str,
        from_state: SessionState,
        event: str,
    ) -> None:
        """验证多种非法转换均抛 StateTransitionError。"""
        ...

    # --------------------------------------------------------
    # 测试场景 3：timeout 事件触发 EXPIRED
    # --------------------------------------------------------
    # [测试场景] ACTIVE→EXPIRED（timeout 30min）与 SUSPENDED→EXPIRED（timeout 7d）
    # [断言] 转换表覆盖两条 timeout 路径
    # [Mock] 无
    def test_timeout_transition_to_expired(self, sample_user_id: str) -> None:
        """验证 timeout 事件使 ACTIVE/SUSPENDED 转为 EXPIRED。"""
        ...

    # --------------------------------------------------------
    # 测试场景 4：can_transition 预检（不抛异常）
    # --------------------------------------------------------
    # [测试场景] can_transition 返回布尔
    # [断言] 合法 True / 非法 False
    # [Mock] 无
    def test_can_transition_predicate(self, sample_session: Session) -> None:
        """验证 can_transition 预检函数行为。"""
        ...
