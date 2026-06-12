"""session.state_machine - M-004 Session 状态机（FSM）

> 对应模块: M-004 Session
> 关联接口: IC-002（学习回合 session 状态更新）
> 关联选型: TS-001 Python
> 关联设计: MD-AITutor-V3.1#m-004 状态机定义
> 来源标注: [DD-001:MD-004]
"""

# [文件职责] 会话状态机（FSM），定义合法状态转换表
# [所属模块] M-004
# [关联设计规范] MD-AITutor-V3.1#m-004
# [功能描述]
#   功能1: 维护状态转换表 (from, event) -> to
#   功能2: 转换合法性校验（非法抛 StateTransitionError → E00402）
#   功能3: 暴露查询接口 get_state
# [输入输出]
#   输入: Session 实体 + 事件名（activate/suspend/close/timeout）
#   输出: 转换后的 SessionState
# [依赖关系]
#   依赖文件: session/models.py
#   被依赖文件: session/service.py
# [注意事项]
#   注意1: 纯逻辑层，不涉及 DB 写入（持久化由 service 调 repository 完成）
#   注意2: timeout 事件由定时器（service 层 cron）触发
#   注意3: transitions 表只读（模块级常量），禁止运行时修改
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-004 - 初始创建文件框架
# [作者] DD-M-004-20260602
# [来源标注] [DD-001:MD-004]

from typing import Dict, Tuple

from aitutor.session.models import Session, SessionState, StateTransitionError


# ============================================================
# 模块级常量：合法状态转换表
# ============================================================


# [常量说明] 状态转换表 (from_state, event) -> to_state
# 事件集: activate / suspend / close / timeout
# 规则来源: MD-AITutor-V3.1#m-004 状态机
TRANSITIONS: Dict[Tuple[SessionState, str], SessionState] = {
    (SessionState.NEW, "activate"): SessionState.ACTIVE,
    (SessionState.ACTIVE, "suspend"): SessionState.SUSPENDED,
    (SessionState.ACTIVE, "close"): SessionState.CLOSED,
    (SessionState.ACTIVE, "timeout"): SessionState.EXPIRED,
    (SessionState.SUSPENDED, "activate"): SessionState.ACTIVE,
    (SessionState.SUSPENDED, "timeout"): SessionState.EXPIRED,
}


# ============================================================
# 类：SessionStateMachine
# ============================================================


class SessionStateMachine:
    """会话状态机。

    [类名] SessionStateMachine
    [职责] 提供 Session 状态转换合法性校验与执行
    [关联设计规范] MD-AITutor-V3.1#m-004 SessionStateMachine 类设计
    [属性]
      属性1: transitions Dict[Tuple[SessionState, str], SessionState] 必填 状态转换表（默认引用模块级 TRANSITIONS）
    [方法列表]
      方法1: transition(session: Session, event: str) -> str - 执行转换并返回新状态值
      方法2: get_state(session: Session) -> str - 查询当前状态值（不修改）
      方法3: can_transition(session: Session, event: str) -> bool - 预检（不抛异常）
    [状态机]
      状态1: NEW → [activate] → ACTIVE
      状态2: ACTIVE → [suspend] → SUSPENDED
      状态3: ACTIVE → [timeout] → EXPIRED
      状态4: ACTIVE → [close] → CLOSED
      状态5: SUSPENDED → [activate] → ACTIVE
      状态6: SUSPENDED → [timeout] → EXPIRED
    [异常处理]
      异常1: StateTransitionError - 转换表中无 (from, event) 时抛出（E00402）
    [并发安全] 是（无状态，transitions 为只读）
    [幂等性] can_transition 是幂等；transition 非幂等（每次修改状态）
    [来源标注] [DD-001:MD-004]
    """

    def __init__(
        self,
        transitions: Dict[Tuple[SessionState, str], SessionState] | None = None,
    ) -> None:
        """初始化状态机。

        [函数名] __init__
        [职责] 注入转换表（默认使用模块级 TRANSITIONS）
        [参数说明]
          参数1: transitions Dict 可选 默认 None（使用 TRANSITIONS） 自定义转换表
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-004]
        """
        self.transitions: Dict[Tuple[SessionState, str], SessionState] = (
            transitions if transitions is not None else TRANSITIONS
        )

    def transition(self, session: Session, event: str) -> str:
        """执行状态转换。

        [函数名] transition
        [职责] 根据事件在转换表中查找目标状态，修改 session 并返回新状态值
        [关联接口契约] IC-002（学习回合后置：session 状态更新）
        [参数说明]
          参数1: session Session 必填 待转换的会话实体
          参数2: event str 必填 事件名 ∈ {activate, suspend, close, timeout}
        [返回值]
          类型: str
          描述: 转换后的状态值（"NEW"/"ACTIVE"/"SUSPENDED"/"EXPIRED"/"CLOSED"）
        [错误码]
          错误码1: E00402 含义: 状态转换非法 触发: 转换表无 (current, event) 规则
        [前置条件] session.state 在合法状态枚举中
        [后置条件] session.state 已更新为转换表目标状态
        [并发安全] 是（输入对象由调用方独占）
        [幂等性] 否（每次调用修改状态）
        [性能约束] 字典查找 O(1)，无 I/O
        [示例]
          ```
          sm = SessionStateMachine()
          new_state = sm.transition(session, "activate")
          assert new_state == "ACTIVE"
          ```
        [来源标注] [DD-001:MD-004]
        """
        ...

    def get_state(self, session: Session) -> str:
        """查询当前状态值（不修改）。

        [函数名] get_state
        [职责] 返回 session 当前 state 的字符串值
        [参数说明]
          参数1: session Session 必填 会话实体
        [返回值]
          类型: str
          描述: 状态枚举的 value
        [并发安全] 是
        [幂等性] 是
        [来源标注] [DD-001:MD-004]
        """
        ...

    def can_transition(self, session: Session, event: str) -> bool:
        """预检：是否可执行指定事件。

        [函数名] can_transition
        [职责] 不抛异常的转换可行性检查
        [参数说明]
          参数1: session Session 必填 会话实体
          参数2: event str 必填 事件名
        [返回值]
          类型: bool
          描述: True 可转换 / False 不可转换
        [并发安全] 是
        [幂等性] 是
        [来源标注] [DD-001:MD-004]
        """
        ...
