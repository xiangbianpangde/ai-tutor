"""session.models - M-004 Session 实体定义

> 对应模块: M-004 Session
> 关联接口: IC-002（学习回合中的 session_id）
> 关联选型: TS-001 Python / TS-003 SQLite
> 关联设计: MD-AITutor-V3.1（M-004 Session 类设计）
> 来源标注: [DD-001:MD-004]
"""

# [文件职责] 定义 Session 实体（Pydantic Model）、SessionState 枚举、状态转换异常
# [所属模块] M-004
# [关联设计规范] MD-AITutor-V3.1#m-004-sessionrepository--fsm
# [功能描述]
#   功能1: Session 实体（id, user_id, created_at, last_active, state）
#   功能2: SessionState 枚举（NEW/ACTIVE/SUSPENDED/EXPIRED/CLOSED）
#   功能3: StateTransitionError 业务异常（E00402 触发）
# [输入输出]
#   输入: 用户/上游传入的 session_id、user_id、state 等参数
#   输出: Session 实体 / SessionState 枚举值
# [依赖关系]
#   依赖文件: shared/types.py（M-017 共享类型）
#   被依赖文件: session/repository.py、session/state_machine.py、session/service.py
# [注意事项]
#   注意1: Pydantic v2 BaseModel，所有字段必填或带默认值，禁止 mutable default
#   注意2: SessionState 枚举值与 EX-010 错误码（E00401/E00402）严格对齐
#   注意3: 字段命名遵循 snake_case（CS-AITutor-V3.1 §1）
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-004 - 初始创建文件框架
# [作者] DD-M-004-20260602
# [来源标注] [DD-001:MD-004]

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ============================================================
# 枚举：SessionState（会话状态机 5 态）
# ============================================================


class SessionState(str, Enum):
    """会话状态枚举。

    [类名] SessionState
    [职责] 会话生命周期状态枚举
    [关联设计规范] MD-AITutor-V3.1#m-004（FSM 状态定义）
    [属性]
      属性1: NEW str 初始创建状态
      属性2: ACTIVE str 活跃状态（可接受回合输入）
      属性3: SUSPENDED str 暂停状态（用户主动挂起）
      属性4: EXPIRED str 过期状态（timeout 触发）
      属性5: CLOSED str 关闭状态（终态）
    [状态机]
      状态1: NEW → [activate] → ACTIVE
      状态2: ACTIVE → [suspend] → SUSPENDED
      状态3: ACTIVE → [timeout 30min] → EXPIRED
      状态4: ACTIVE → [close] → CLOSED
      状态5: SUSPENDED → [activate] → ACTIVE
      状态6: SUSPENDED → [timeout 7d] → EXPIRED
    [异常处理]
      异常1: StateTransitionError - 非法状态转换时抛出
    [来源标注] [DD-001:MD-004]
    """

    NEW = "NEW"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    CLOSED = "CLOSED"


# ============================================================
# 异常：StateTransitionError（业务异常 - 状态非法转换）
# ============================================================


class StateTransitionError(Exception):
    """会话状态非法转换异常。

    [类名] StateTransitionError
    [职责] 表达会话状态机非法转换，对应 EX-010 + E00402
    [关联设计规范] MD-AITutor-V3.1#m-004 异常处理（E00402 状态转换非法 → 422 + trace_id）
    [属性]
      属性1: current_state SessionState 当前状态
      属性2: target_state SessionState 目标状态
      属性3: event str 触发事件
    [方法列表]
      方法1: __str__() -> str - 拼接可读错误信息
    [异常处理]
      异常1: 自身继承 Exception - 触发条件：FSM 检测到不在 transitions 表中的转换
    [来源标注] [DD-001:MD-004]
    """

    def __init__(
        self,
        current_state: SessionState,
        target_state: SessionState,
        event: str,
    ) -> None:
        """初始化状态转换异常。

        [函数名] __init__
        [职责] 构造异常并保存当前/目标状态与事件
        [参数说明]
          参数1: current_state SessionState 必填 当前 FSM 状态
          参数2: target_state SessionState 必填 尝试跳转的目标状态
          参数3: event str 必填 触发转换的事件名（如 activate/suspend/timeout/close）
        [返回值]
          类型: None
          描述: 构造异常实例
        [错误码]
          错误码1: E00402 含义: 状态转换非法 触发: FSM 中无 (from, event) → to 规则
        [来源标注] [DD-001:MD-004]
        """
        self.current_state = current_state
        self.target_state = target_state
        self.event = event
        super().__init__(
            f"Illegal session state transition: {current_state.value} "
            f"--[{event}]--> {target_state.value}"
        )


# ============================================================
# 实体：Session
# ============================================================


class Session(BaseModel):
    """会话实体。

    [类名] Session
    [职责] 表示一个学习会话，含 ID、归属用户、创建/最后活跃时间、状态
    [关联设计规范] MD-AITutor-V3.1#m-004 Session 类设计
    [属性]
      属性1: id str 必填 UUIDv4 会话唯一标识
      属性2: user_id str 必填 32hex 归属用户 ID（强校验防 CE-003 串号）
      属性3: created_at datetime 必填 创建时间（UTC）
      属性4: last_active datetime 必填 最后活跃时间（用于 timeout 计算）
      属性5: state SessionState 必填 默认 NEW 当前会话状态
    [方法列表]
      方法1: activate() -> None - 状态置为 ACTIVE 并刷新 last_active
      方法2: suspend() -> None - 状态置为 SUSPENDED
      方法3: close() -> None - 状态置为 CLOSED（终态）
      方法4: mark_expired() -> None - 状态置为 EXPIRED（timeout 触发）
      方法5: touch() -> None - 刷新 last_active 为当前时间
    [状态机]
      状态1: NEW → [activate] → ACTIVE
      状态2: ACTIVE → [suspend] → SUSPENDED
      状态3: ACTIVE → [timeout 30min] → EXPIRED
      状态4: ACTIVE → [close] → CLOSED
      状态5: SUSPENDED → [activate] → ACTIVE
      状态6: SUSPENDED → [timeout 7d] → EXPIRED
    [异常处理]
      异常1: StateTransitionError - 调用方法时若不符合 FSM 规则则抛出
    [来源标注] [DD-001:MD-004]
    """

    id: str = Field(..., description="会话唯一标识（UUIDv4）", min_length=36, max_length=36)
    user_id: str = Field(..., description="归属用户 ID（32hex 强校验）", min_length=32, max_length=32)
    created_at: datetime = Field(..., description="创建时间（UTC）")
    last_active: datetime = Field(..., description="最后活跃时间（用于 timeout 计算）")
    state: SessionState = Field(
        default=SessionState.NEW, description="当前会话状态（FSM 状态）"
    )

    model_config = {
        "frozen": False,
        "populate_by_name": True,
        "validate_assignment": True,
    }

    @field_validator("user_id")
    @classmethod
    def _validate_user_id_hex(cls, v: str) -> str:
        """校验 user_id 为 32hex 字符串。

        [函数名] _validate_user_id_hex
        [职责] 校验 user_id 字段为 32hex（防 CE-003 串号）
        [参数说明]
          参数1: v str 必填 待校验的 user_id 值
        [返回值]
          类型: str
          描述: 校验通过的原始字符串
        [错误码]
          错误码1: E00401 含义: user_id 格式非法 触发: 非 32hex 字符
        [来源标注] [DD-M推断:依据=CE-003 强校验 + IC-002 user_id 强校验要求]
        """
        if not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("user_id must be 32hex string")
        return v.lower()

    def touch(self) -> None:
        """刷新 last_active 为当前 UTC 时间。

        [函数名] touch
        [职责] 将 last_active 更新为 now()，用于 timeout 计算
        [参数说明] 无
        [返回值]
          类型: None
          描述: 原地修改对象的 last_active 字段
        [并发安全] 否（仅修改本对象，无共享状态）
        [幂等性] 否（每次调用更新时间戳）
        [来源标注] [DD-001:MD-004]
        """
        self.last_active = datetime.utcnow()

    def activate(self) -> None:
        """激活会话（NEW→ACTIVE / SUSPENDED→ACTIVE）。

        [函数名] activate
        [职责] 将会话状态置为 ACTIVE 并刷新 last_active
        [参数说明] 无
        [返回值]
          类型: None
          描述: 修改 state=ACTIVE，last_active=now()
        [错误码]
          错误码1: E00402 含义: 状态非法 触发: 当前 state 不在 [NEW, SUSPENDED] 中
        [并发安全] 否
        [幂等性] 半幂等（重复调用会刷新 last_active）
        [来源标注] [DD-001:MD-004]
        """
        if self.state not in (SessionState.NEW, SessionState.SUSPENDED):
            raise StateTransitionError(self.state, SessionState.ACTIVE, "activate")
        self.state = SessionState.ACTIVE
        self.touch()

    def suspend(self) -> None:
        """挂起会话（ACTIVE→SUSPENDED）。

        [函数名] suspend
        [职责] 将会话状态置为 SUSPENDED
        [参数说明] 无
        [返回值]
          类型: None
          描述: 修改 state=SUSPENDED
        [错误码]
          错误码1: E00402 含义: 状态非法 触发: 当前 state 不在 [ACTIVE] 中
        [来源标注] [DD-001:MD-004]
        """
        if self.state != SessionState.ACTIVE:
            raise StateTransitionError(self.state, SessionState.SUSPENDED, "suspend")
        self.state = SessionState.SUSPENDED

    def close(self) -> None:
        """关闭会话（ACTIVE→CLOSED 终态）。

        [函数名] close
        [职责] 将会话状态置为 CLOSED（不可逆）
        [参数说明] 无
        [返回值]
          类型: None
          描述: 修改 state=CLOSED
        [错误码]
          错误码1: E00402 含义: 状态非法 触发: 当前 state 不在 [ACTIVE, SUSPENDED] 中
        [来源标注] [DD-001:MD-004]
        """
        if self.state not in (SessionState.ACTIVE, SessionState.SUSPENDED):
            raise StateTransitionError(self.state, SessionState.CLOSED, "close")
        self.state = SessionState.CLOSED

    def mark_expired(self) -> None:
        """标记过期（ACTIVE→EXPIRED / SUSPENDED→EXPIRED，timeout 触发）。

        [函数名] mark_expired
        [职责] 将会话状态置为 EXPIRED（timeout 事件）
        [参数说明] 无
        [返回值]
          类型: None
          描述: 修改 state=EXPIRED
        [错误码]
          错误码1: E00402 含义: 状态非法 触发: 当前 state 不在 [ACTIVE, SUSPENDED] 中
        [来源标注] [DD-001:MD-004]
        """
        if self.state not in (SessionState.ACTIVE, SessionState.SUSPENDED):
            raise StateTransitionError(self.state, SessionState.EXPIRED, "timeout")
        self.state = SessionState.EXPIRED
