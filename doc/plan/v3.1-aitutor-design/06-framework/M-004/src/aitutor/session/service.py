"""session.service - M-004 Session 业务逻辑编排层

> 对应模块: M-004 Session
> 关联接口: IC-002（学习回合 session_id）/ IC-007（长期记忆 user_id 强校验共用）
> 关联选型: TS-001 Python
> 关联设计: MD-AITutor-V3.1#m-004 函数签名
> 来源标注: [DD-001:MD-004]
"""

# [文件职责] 编排 Repository + StateMachine，对外暴露业务流程入口
# [所属模块] M-004
# [关联设计规范] MD-AITutor-V3.1#m-004
# [功能描述]
#   功能1: 创建会话（强校验 user_id）
#   功能2: 查询会话（不存在抛 SessionNotFoundError → E00401）
#   功能3: 更新会话状态（非法转换抛 StateTransitionError → E00402）
#   功能4: 状态转换入口（统一 FSM 转换 + 持久化）
# [输入输出]
#   输入: user_id / session_id / event
#   输出: Session 实体 / 新状态字符串
# [依赖关系]
#   依赖文件: session/repository.py、session/state_machine.py、session/models.py、shared/exceptions.py
#   被依赖文件: api/v1/session.py（M-002 网关）、api/v1/turn.py（IC-002 学习回合）
# [注意事项]
#   注意1: 唯一对上层（API 层）暴露的模块入口（Import Linter contract 1）
#   注意2: 所有异常需携带 trace_id 上下文
#   注意3: 用户 ID 强校验（防 CE-003 串号）
#   注意4: 业务异常统一翻译为 API 错误码 E00401/E00402/E00403
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-004 - 初始创建文件框架
# [作者] DD-M-004-20260602
# [来源标注] [DD-001:MD-004]

from typing import Optional

from aitutor.session.models import Session, SessionState, StateTransitionError
from aitutor.session.repository import SessionRepository
from aitutor.session.state_machine import SessionStateMachine
from aitutor.shared.exceptions import SessionNotFoundError  # [DD-M推断:依据=EX-010 E00401 业务异常]


# ============================================================
# 类：SessionService
# ============================================================


class SessionService:
    """会话业务服务。

    [类名] SessionService
    [职责] 编排 Repository + StateMachine，对外提供会话生命周期管理
    [关联设计规范] MD-AITutor-V3.1#m-004 SessionService 业务流程
    [属性]
      属性1: repository SessionRepository 必填 数据访问层
      属性2: state_machine SessionStateMachine 必填 状态机
      属性3: _default_timeout_minutes int 内部 默认 30 ACTIVE→EXPIRED 超时（分钟）
      属性4: _suspend_timeout_days int 内部 默认 7 SUSPENDED→EXPIRED 超时（天）
    [方法列表]
      方法1: create_session(user_id: str) -> Session - 创建会话
      方法2: get_session(session_id: str) -> Session - 查询会话（不存在抛 E00401）
      方法3: update_session_state(session_id: str, new_state: SessionState) -> None - 直接设置状态
      方法4: transition_state(session_id: str, event: str) -> str - FSM 事件转换
      方法5: list_sessions_by_user(user_id: str, limit: int = 50) -> list[Session] - 用户会话列表
    [状态机]
      状态1: NEW → [activate] → ACTIVE
      状态2: ACTIVE → [suspend] → SUSPENDED
      状态3: ACTIVE → [timeout 30min] → EXPIRED
      状态4: ACTIVE → [close] → CLOSED
      状态5: SUSPENDED → [activate] → ACTIVE
      状态6: SUSPENDED → [timeout 7d] → EXPIRED
    [异常处理]
      异常1: SessionNotFoundError - get_session 未找到（E00401 → 404）
      异常2: StateTransitionError - 非法转换（E00402 → 422 + trace_id）
      异常3: StorageError - DB 写失败（E00403 → 5xx，重试 1 次）
    [并发安全] 是（asyncio.Lock 保护单 session 写，SQLite WAL）
    [幂等性] create 非幂等；get/transition_state 幂等
    [来源标注] [DD-001:MD-004]
    """

    def __init__(
        self,
        repository: SessionRepository,
        state_machine: SessionStateMachine,
    ) -> None:
        """初始化业务服务。

        [函数名] __init__
        [职责] 注入 Repository 与 StateMachine
        [参数说明]
          参数1: repository SessionRepository 必填 数据访问层
          参数2: state_machine SessionStateMachine 必填 状态机
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-004]
        """
        self.repository = repository
        self.state_machine = state_machine
        self._default_timeout_minutes = 30
        self._suspend_timeout_days = 7

    async def create_session(self, user_id: str) -> Session:
        """创建新会话。

        [函数名] create_session
        [职责] 为指定用户创建 Session（user_id 32hex 强校验）
        [关联接口契约] IC-002（学习回合前置：session 必须存在）
        [参数说明]
          参数1: user_id str 必填 32hex 强校验
        [返回值]
          类型: Session
          描述: 创建的会话（state=NEW）
        [错误码]
          错误码1: E00403 含义: DB 写失败 触发: 仓储层重试 1 次仍失败
        [前置条件] user_id 通过 32hex 强校验
        [后置条件] 数据库新增一行；id 全局唯一
        [并发安全] 是
        [幂等性] 否（每次生成新 UUID）
        [性能约束] 单写 ≤50ms（P95）
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def get_session(self, session_id: str) -> Session:
        """查询会话（不存在抛 SessionNotFoundError）。

        [函数名] get_session
        [职责] 根据 session_id 查询会话；未找到时翻译为业务异常 E00401
        [关联接口契约] IC-002（学习回合前置：session 必须存在）
        [参数说明]
          参数1: session_id str 必填 UUIDv4
        [返回值]
          类型: Session
          描述: 找到的会话实体
        [错误码]
          错误码1: E00401 含义: session 不存在 触发: 仓储层 get 返回 None
        [并发安全] 是
        [幂等性] 是
        [性能约束] 单查 ≤30ms（P95）
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def update_session_state(
        self,
        session_id: str,
        new_state: SessionState,
    ) -> None:
        """直接设置会话状态（不经 FSM）。

        [函数名] update_session_state
        [职责] 直接写入新状态（管理员/迁移场景专用）
        [关联接口契约] IC-002（学习回合后置：session 状态更新）
        [参数说明]
          参数1: session_id str 必填 UUIDv4
          参数2: new_state SessionState 必填 目标状态
        [返回值]
          类型: None
        [错误码]
          错误码1: E00401 含义: session 不存在
          错误码2: E00403 含义: DB 写失败
        [注意事项] 注意1: 业务主流程请使用 transition_state；本方法仅供运维/迁移
        [并发安全] 是
        [幂等性] 是
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def transition_state(self, session_id: str, event: str) -> str:
        """FSM 事件驱动的状态转换。

        [函数名] transition_state
        [职责] 通过事件触发状态转换，校验合法性后持久化
        [关联接口契约] IC-002（学习回合后置：session 状态更新）
        [参数说明]
          参数1: session_id str 必填 UUIDv4
          参数2: event str 必填 ∈ {activate, suspend, close, timeout}
        [返回值]
          类型: str
          描述: 转换后的状态值
        [错误码]
          错误码1: E00401 含义: session 不存在
          错误码2: E00402 含义: 状态转换非法（FSM 中无规则）
          错误码3: E00403 含义: DB 写失败
        [前置条件] session 存在
        [后置条件] 数据库中该 session 的 state 已更新
        [并发安全] 是（asyncio.Lock + SQLite WAL）
        [幂等性] 半幂等（相同事件重复触发可能因状态已变而失败）
        [性能约束] 单转换 ≤80ms（P95，含 DB 写）
        [示例]
          ```
          new_state = await service.transition_state(session_id, "activate")
          assert new_state == "ACTIVE"
          ```
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def list_sessions_by_user(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[Session]:
        """按用户列出会话。

        [函数名] list_sessions_by_user
        [职责] 查询用户的所有会话（按 last_active DESC）
        [参数说明]
          参数1: user_id str 必填 32hex
          参数2: limit int 可选 默认 50 规则 [1, 200]
        [返回值]
          类型: List[Session]
        [错误码]
          错误码1: E00403 含义: DB 查询失败
        [并发安全] 是
        [幂等性] 是
        [性能约束] 单查 ≤100ms（P95）
        [来源标注] [DD-001:MD-004]
        """
        ...
