"""session - M-004 会话管理模块（导出公共接口）

> 对应模块: M-004 Session
> 关联接口: IC-002（学习回合 session_id 关联）
> 关联选型: TS-001 Python / TS-003 SQLite
> 关联设计: FS-AITutor-V3.1 / MD-AITutor-V3.1（Repository + FSM 模式）
> 来源标注: [DD-001:FS-004/MD-004]
"""

# [文件职责] 模块初始化与公共接口导出
# [所属模块] M-004
# [依赖关系]
#   依赖文件: models.py / repository.py / state_machine.py / service.py
#   被依赖文件: api/v1/session.py（M-002 网关）/ api/v1/turn.py（IC-002 学习回合）
# [注意事项]
#   注意1: 仅 re-export 公共类/函数，私有成员以下划线开头不导出
#   注意2: Import Linter contract 1+3 约束：API 层必须经 service.py 访问，禁止直接 import repository.py
# [代码风格] 遵循 CS-AITutor-V3.1（PEP8 + Google Docstring + 4 空格缩进 + 120 字符行宽）
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-004 - 初始创建文件框架
# [作者] DD-M-004-20260602
# [来源标注] [DD-001:FS-004]

from aitutor.session.models import Session, SessionState, StateTransitionError
from aitutor.session.repository import SessionRepository
from aitutor.session.service import SessionService
from aitutor.session.state_machine import SessionStateMachine

__all__ = [
    "Session",
    "SessionState",
    "StateTransitionError",
    "SessionRepository",
    "SessionService",
    "SessionStateMachine",
]
