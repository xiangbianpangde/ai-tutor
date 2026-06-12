"""test_session.conftest - M-004 Session 测试共享 Fixture

> 对应模块: M-004 Session
> 关联选型: TS-017 pytest
> 关联设计: CS-AITutor-V3.1 §6
> 来源标注: [DD-001:CS-001]
"""

# [文件职责] 提供 M-004 测试用的共享 Fixture（内存 SQLite、sample session、async engine）
# [所属模块] M-004
# [依赖关系]
#   依赖文件: session/models.py、session/repository.py、session/service.py、session/state_machine.py
# [注意事项]
#   注意1: 每个测试用独立内存 SQLite（function scope），互不干扰
#   注意2: 不得在此处编写具体测试用例（test_* 函数）
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-004 - 初始创建
# [作者] DD-M-004-20260602
# [来源标注] [DD-M推断:依据=CS-001 §6 Fixture 共享放 conftest.py]


import pytest
import pytest_asyncio
from datetime import datetime
from typing import AsyncIterator

from aitutor.session.models import Session, SessionState
from aitutor.session.repository import SessionRepository
from aitutor.session.service import SessionService
from aitutor.session.state_machine import SessionStateMachine


# ============================================================
# Fixture：sample_user_id（32hex 合法用户 ID）
# ============================================================

# [Fixture 说明] 32hex 强校验通过的样例 user_id
# [作用域] session
# [Mock 策略] 无
@pytest.fixture
def sample_user_id() -> str:
    """返回 32hex 合法的样例 user_id。"""
    ...


# ============================================================
# Fixture：sample_session（NEW 状态样例）
# ============================================================

# [Fixture 说明] 创建一个 NEW 状态的样例 Session
# [作用域] function
# [Mock 策略] 无
@pytest.fixture
def sample_session(sample_user_id: str) -> Session:
    """返回 NEW 状态的样例 Session。"""
    ...


# ============================================================
# Fixture：async_engine（内存 SQLite 引擎）
# ============================================================

# [Fixture 说明] aiosqlite + SQLAlchemy 2.0 内存引擎（每个测试独立）
# [作用域] function
# [Mock 策略] sqlite:///:memory: 替代文件 DB
@pytest_asyncio.fixture
async def async_engine() -> AsyncIterator:
    """提供内存 SQLite 异步引擎，测试结束自动释放。"""
    ...


# ============================================================
# Fixture：session_repository
# ============================================================

# [Fixture 说明] 绑定到 async_engine 的 SessionRepository 实例
# [作用域] function
@pytest_asyncio.fixture
async def session_repository(async_engine) -> SessionRepository:  # type: ignore[no-untyped-def]
    """返回已绑定引擎的 SessionRepository。"""
    ...


# ============================================================
# Fixture：state_machine
# ============================================================

# [Fixture 说明] 默认 SessionStateMachine 实例
@pytest.fixture
def state_machine() -> SessionStateMachine:
    """返回默认状态机实例。"""
    ...


# ============================================================
# Fixture：session_service
# ============================================================

# [Fixture 说明] 注入 Repository + StateMachine 的 SessionService
@pytest_asyncio.fixture
async def session_service(
    session_repository: SessionRepository,
    state_machine: SessionStateMachine,
) -> SessionService:
    """返回已注入依赖的 SessionService。"""
    ...
