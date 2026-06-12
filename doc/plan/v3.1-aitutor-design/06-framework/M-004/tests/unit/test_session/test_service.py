"""test_session.test_service - M-004 Session 业务服务层单元测试

> 对应模块: M-004 Session
> 关联选型: TS-017 pytest
> 关联设计: CS-AITutor-V3.1 §6
> 来源标注: [DD-001:CS-001] + [DD-M推断:依据=MD-004 测试策略 14 用例]
"""

# [文件职责] SessionService 业务逻辑层单元测试（编排 Repository + StateMachine）
# [所属模块] M-004
# [测试策略] 单测+集成 / 14 用例中归属本文件 3 个核心场景
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-004 - 初始创建
# [作者] DD-M-004-20260602
# [来源标注] [DD-001:MD-004 测试策略]

import pytest

from aitutor.session.models import Session, SessionState
from aitutor.session.service import SessionService
from aitutor.shared.exceptions import SessionNotFoundError, StateTransitionError


class TestSessionService:
    """SessionService 业务编排测试。"""

    # --------------------------------------------------------
    # 测试场景 1：端到端创建+查询+状态变更
    # --------------------------------------------------------
    # [测试场景] 业务主流程 happy path
    # [断言] create → get → transition_state(activate) 链路通畅
    # [Mock] 内存 SQLite（conftest）
    async def test_end_to_end_create_get_transition(
        self,
        session_service: SessionService,
        sample_user_id: str,
    ) -> None:
        """验证创建→查询→激活全链路。"""
        ...

    # --------------------------------------------------------
    # 测试场景 2：session 不存在（404）异常
    # --------------------------------------------------------
    # [测试场景] get_session 传入不存在的 ID
    # [断言] 抛 SessionNotFoundError（E00401 → 404）
    # [Mock] 无
    async def test_get_nonexistent_session_raises(
        self,
        session_service: SessionService,
    ) -> None:
        """验证查询不存在 session 翻译为 E00401。"""
        ...

    # --------------------------------------------------------
    # 测试场景 3：状态非法转换（422）异常
    # --------------------------------------------------------
    # [测试场景] transition_state 传入非法事件
    # [断言] 抛 StateTransitionError（E00402 → 422 + trace_id）
    # [Mock] 无
    async def test_transition_state_illegal_event_raises(
        self,
        session_service: SessionService,
        sample_user_id: str,
    ) -> None:
        """验证非法事件触发 E00402。"""
        ...
