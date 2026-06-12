"""state_machine - 教学状态机（Teaching State Machine）

[文件路径] src/aitutor/teaching/state_machine.py
[文件职责] 教学侧 FSM 定义：IDLE/LEARN/REVIEW/PRACTICE/REST/STAGE_ADJUST 状态转换
[所属模块] M-009 教学编排（来自 DD-001）
[关联设计规范] MD-009 / FS-009（来自 DD-001）
[功能描述]
  功能1: 定义 6 个教学状态及合法转换边
  功能2: 提供 transition(event) 推进 FSM
  功能3: 检测卡死（无合法转换时抛 TeachingFSMStuckError）
[输入输出]
  输入: TeachingState（当前态）、TeachingEvent（事件）
  输出: TeachingState（下一态）
[依赖关系]
  依赖文件: shared/types.py、shared/exceptions.py
  被依赖文件: orchestrator.py（M-009）、tests/unit/test_teaching/test_state_machine.py
[注意事项]
  注意1: 转换表必须为 frozen Mapping，运行期不可变
  注意2: * 通配态仅在 STAGE_ADJUST 进入时使用，其他通配边禁止
  注意3: 卡死判定采用「当前态 + 事件无合法目标」原则
[代码风格] 遵循 CS-AITutor-V3.1（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-009 - 初版文件头注释
[作者] DD-M-M-009-20260602
[来源标注] [DD-001:MD-009] + [DD-M推断:依据=FSM 教学域标准化]
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet, Optional

from pydantic import BaseModel, Field


class TeachingState(str, Enum):
    """[类名] TeachingState
    [职责] 教学状态枚举
    [关联设计规范] MD-009（来自 DD-001）
    [属性]
      属性1: IDLE 字符串 "IDLE" 初始态
      属性2: LEARN 字符串 "LEARN" 学习态
      属性3: REVIEW 字符串 "REVIEW" 复习态
      属性4: PRACTICE 字符串 "PRACTICE" 练习态
      属性5: REST 字符串 "REST" 休息态
      属性6: STAGE_ADJUST 字符串 "STAGE_ADJUST" 阶段校准态
    [来源标注] [DD-001:MD-009]
    """

    IDLE = "IDLE"
    LEARN = "LEARN"
    REVIEW = "REVIEW"
    PRACTICE = "PRACTICE"
    REST = "REST"
    STAGE_ADJUST = "STAGE_ADJUST"


class TeachingEvent(str, Enum):
    """[类名] TeachingEvent
    [职责] 教学事件枚举
    [关联设计规范] MD-009（来自 DD-001）
    [属性]
      属性1: USER_INPUT 用户输入事件
      属性2: FEYNMAN_DONE 费曼完成事件
      属性3: FSRS_DUE FSRS 到期事件
      属性4: AGAIN_THRESHOLD Again 次数 ≥3 事件
      属性5: TIMER_DONE 休息定时器完成事件
      属性6: STAGE_CHANGE 阶段变化事件
    [来源标注] [DD-001:MD-009]
    """

    USER_INPUT = "user_input"
    FEYNMAN_DONE = "feynman_done"
    FSRS_DUE = "fsrs_due"
    AGAIN_THRESHOLD = "again_count>=3"
    TIMER_DONE = "timer_done"
    STAGE_CHANGE = "stage_change"


class TeachingFSMStuckError(RuntimeError):
    """[类名] TeachingFSMStuckError
    [职责] 教学 FSM 卡死异常
    [关联设计规范] MD-009 / EX-009（来自 DD-001）
    [异常处理]
      异常1: 触发条件 状态机无合法转换
      异常2: 处理路径 LLM 兜底 + audit_log（E00902）
    [来源标注] [DD-001:EX-009] + [DD-M推断:依据=FSM 标准异常]
    """


class TeachingStateMachine(BaseModel):
    """[类名] TeachingStateMachine
    [职责] 教学侧有限状态机
    [关联设计规范] MD-009（来自 DD-001 模块细化方案）
    [属性]
      属性1: current_state TeachingState 当前态，默认 IDLE
      属性2: transitions Dict 转换表，key=(from_state, event)，value=next_state
      属性3: last_event Optional[TeachingEvent] 最近一次事件
    [方法列表]
      方法1: transition(event) -> TeachingState - 推进 FSM
      方法2: get_state() -> TeachingState - 取当前态
      方法3: reset() -> None - 复位到 IDLE
      方法4: can_transition(event) -> bool - 判定当前态下事件是否合法
    [状态机]
      状态1: IDLE → [user_input] → LEARN
      状态2: LEARN → [feynman_done] → REVIEW
      状态3: REVIEW → [fsrs_due] → PRACTICE
      状态4: PRACTICE → [again_count>=3] → REST
      状态5: REST → [timer_done] → LEARN
      状态6: * → [stage_change] → STAGE_ADJUST
    [异常处理]
      异常1: TeachingFSMStuckError - 无合法转换（E00902）
    [来源标注] [DD-001:MD-009] + [DD-M推断:依据=Python FSM 最佳实践]
    """

    model_config = {"frozen": False, "arbitrary_types_allowed": True}

    current_state: TeachingState = Field(default=TeachingState.IDLE, description="当前教学态")
    transitions: Dict[str, str] = Field(
        default_factory=lambda: _DEFAULT_TRANSITIONS,
        description="转换表 JSON 字符串（key 形如 from_state:event）",
    )
    last_event: Optional[TeachingEvent] = Field(default=None, description="最近一次事件")

    def transition(self, event: TeachingEvent) -> TeachingState:
        """[函数名] transition
        [职责] 推进教学 FSM 到下一态
        [关联接口契约] IC-002 学习回合
        [参数说明]
          参数1: event TeachingEvent 必填 触发事件
        [返回值]
          类型: TeachingState
          描述: 推进后的状态
        [错误码]
          错误码1: E00902 含义 FSM 卡死 触发 无合法转换 处理 LLM 兜底 + audit_log
        [前置条件] 事件 ∈ TeachingEvent 白名单
        [后置条件] current_state 已更新
        [并发安全] 否（多协程并发需外层 asyncio.Lock）
        [幂等性] 否（每次推进状态都不同）
        [性能约束] 单次 ≤5ms
        [示例]
          ```
          fsm = TeachingStateMachine()
          new_state = fsm.transition(TeachingEvent.USER_INPUT)  # LEARN
          ```
        [来源标注] [DD-001:MD-009] + [DD-M推断:依据=FSM 标准接口]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def get_state(self) -> TeachingState:
        """[函数名] get_state
        [职责] 取当前教学态
        [参数说明] 无
        [返回值]
          类型: TeachingState
          描述: 当前状态
        [错误码] 无
        [前置条件] 无
        [后置条件] 无副作用
        [并发安全] 是
        [幂等性] 是
        [性能约束] ≤1ms
        [来源标注] [DD-M推断:依据=状态访问器标准模式]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def reset(self) -> None:
        """[函数名] reset
        [职责] 复位到 IDLE
        [参数说明] 无
        [返回值]
          类型: None
        [错误码] 无
        [前置条件] 无
        [后置条件] current_state = IDLE、last_event = None
        [并发安全] 否
        [幂等性] 是
        [性能约束] ≤1ms
        [来源标注] [DD-M推断:依据=FSM 复位接口]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def can_transition(self, event: TeachingEvent) -> bool:
        """[函数名] can_transition
        [职责] 判定当前态 + 事件是否合法
        [参数说明]
          参数1: event TeachingEvent 必填 待判定事件
        [返回值]
          类型: bool
          描述: True 合法可推进，False 非法将卡死
        [错误码] 无
        [前置条件] 无
        [后置条件] 无副作用
        [并发安全] 是
        [幂等性] 是
        [性能约束] ≤1ms
        [来源标注] [DD-M推断:依据=守卫接口]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError


_DEFAULT_TRANSITIONS: Dict[str, str] = {
    "IDLE:user_input": "LEARN",
    "LEARN:feynman_done": "REVIEW",
    "REVIEW:fsrs_due": "PRACTICE",
    "PRACTICE:again_count>=3": "REST",
    "REST:timer_done": "LEARN",
    "IDLE:stage_change": "STAGE_ADJUST",
    "LEARN:stage_change": "STAGE_ADJUST",
    "REVIEW:stage_change": "STAGE_ADJUST",
    "PRACTICE:stage_change": "STAGE_ADJUST",
    "REST:stage_change": "STAGE_ADJUST",
    "STAGE_ADJUST:user_input": "LEARN",
}


# 供转换合法性静态校验使用
LEGAL_TRANSITIONS: FrozenSet[str] = frozenset(_DEFAULT_TRANSITIONS.keys())
