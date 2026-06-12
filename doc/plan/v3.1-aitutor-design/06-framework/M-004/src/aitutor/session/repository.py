"""session.repository - M-004 Session 数据访问层

> 对应模块: M-004 Session
> 关联接口: IC-002（学习回合）
> 关联选型: TS-001 Python / TS-003 SQLite / SQLAlchemy 2.0 async
> 关联设计: MD-AITutor-V3.1#m-004 SessionRepository 类设计
> 来源标注: [DD-001:MD-004]
"""

# [文件职责] Session 数据的 CRUD 持久化访问，封装 SQLAlchemy 2.0 async 引擎
# [所属模块] M-004
# [关联设计规范] MD-AITutor-V3.1#m-004
# [功能描述]
#   功能1: 异步创建/查询/更新/删除 Session
#   功能2: 按 user_id 列出用户所有 Session
#   功能3: DB 写失败重试 1 次（EX-011，错误码 E00403）
# [输入输出]
#   输入: Session 实体 / session_id / user_id
#   输出: Session 实体 / List[Session]
# [依赖关系]
#   依赖文件: session/models.py、storage/sqlite_repo.py（M-017）、shared/exceptions.py
#   被依赖文件: session/service.py
# [注意事项]
#   注意1: 仅被 service.py 调用，禁止被 API 层直接 import（Import Linter contract 1+3）
#   注意2: 写操作异常必须包含 trace_id 上下文
#   注意3: SQLite WAL 模式 + asyncio 协程，事务边界由 UnitOfWork 统一管理
#   注意4: 重试策略仅适用于 OperationalError（瞬时锁等待），不允许静默吞错
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [修改历史]
#   2026-06-02: DD-M-004 - 初始创建文件框架
# [作者] DD-M-004-20260602
# [来源标注] [DD-001:MD-004]

import asyncio
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from aitutor.session.models import Session, SessionState
from aitutor.shared.exceptions import StorageError
from aitutor.storage.sqlite_repo import BaseRepository  # [DD-M推断:依据=Import Linter contract 3 跨模块依赖声明]


# ============================================================
# 类：SessionRepository
# ============================================================


class SessionRepository:
    """会话数据仓储。

    [类名] SessionRepository
    [职责] 封装 Session 实体的持久化 CRUD 操作（SQLAlchemy 2.0 async）
    [关联设计规范] MD-AITutor-V3.1#m-004 SessionRepository 类设计
    [属性]
      属性1: engine AsyncEngine 必填 SQLAlchemy 异步引擎（来自 M-017 存储）
      属性2: _retry_count int 内部 默认 1 写失败重试次数（EX-011）
      属性3: _retry_backoff_sec float 内部 默认 0.2 重试退避秒数
    [方法列表]
      方法1: create(user_id: str) -> Session - 新建会话（分配 UUIDv4 id）
      方法2: get(session_id: str) -> Optional[Session] - 按 ID 查询（None 表示不存在 → E00401）
      方法3: update(session: Session) -> None - 整体更新（state/last_active 变更）
      方法4: delete(session_id: str) -> None - 删除（软删除可在此扩展，硬删除仅 DEBUG 模式）
      方法5: list_by_user(user_id: str, limit: int = 50) -> List[Session] - 按用户列表
    [异常处理]
      异常1: StorageError - DB 写失败且重试 1 次仍失败（E00403）
      异常2: SessionNotFoundError - get 返回 None 时由 service 层翻译为 E00401
    [并发安全] 是（SQLite WAL + 协程）
    [幂等性] create 非幂等（每次生成新 UUID），get/update/delete 幂等
    [来源标注] [DD-001:MD-004]
    """

    def __init__(self, engine: AsyncEngine) -> None:
        """初始化仓储。

        [函数名] __init__
        [职责] 注入异步引擎并初始化重试参数
        [参数说明]
          参数1: engine AsyncEngine 必填 来自 M-017 UnitOfWork 提供的 SQLAlchemy 引擎
        [返回值]
          类型: None
        [来源标注] [DD-001:MD-004]
        """
        self.engine = engine
        self._retry_count = 1
        self._retry_backoff_sec = 0.2

    async def create(self, user_id: str) -> Session:
        """创建新会话。

        [函数名] create
        [职责] 为指定用户新建 Session（UUIDv4 id，state=NEW）
        [关联接口契约] IC-002（学习回合的前置：session 必须存在）
        [参数说明]
          参数1: user_id str 必填 32hex 强校验（防 CE-003）
        [返回值]
          类型: Session
          描述: 新创建的会话对象（state=NEW）
        [错误码]
          错误码1: E00403 含义: DB 写失败 触发: OperationalError 重试 1 次仍失败
        [前置条件] user_id 通过 32hex 校验
        [后置条件] 数据库新增一行；id 全局唯一
        [并发安全] 是（id 唯一约束保护）
        [幂等性] 否（每次创建不同 UUID）
        [性能约束] 单写 ≤50ms（P95）
        [示例]
          ```
          session = await repo.create(user_id="a"*32)
          assert session.state == SessionState.NEW
          ```
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def get(self, session_id: str) -> Optional[Session]:
        """按 ID 查询会话。

        [函数名] get
        [职责] 根据 session_id 查询 Session 实体
        [关联接口契约] IC-002（学习回合前置：session 必须存在）
        [参数说明]
          参数1: session_id str 必填 UUIDv4 会话 ID
        [返回值]
          类型: Optional[Session]
          描述: 找到返回 Session；未找到返回 None（由 service 层翻译为 E00401）
        [错误码]
          错误码1: E00401 含义: session 不存在 触发: service 层在 None 时抛出
        [并发安全] 是
        [幂等性] 是
        [性能约束] 单查 ≤30ms（P95，含索引）
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def update(self, session: Session) -> None:
        """更新会话（state/last_active 变更）。

        [函数名] update
        [职责] 整体覆盖更新 Session 记录
        [关联接口契约] IC-002（学习回合后置：session 状态更新）
        [参数说明]
          参数1: session Session 必填 携带最新字段的实体
        [返回值]
          类型: None
        [错误码]
          错误码1: E00403 含义: DB 写失败 触发: OperationalError 重试 1 次仍失败
        [前置条件] session.id 已存在（由 get 获得）
        [后置条件] 数据库该行字段已更新
        [并发安全] 是（SQLite WAL + 协程锁）
        [幂等性] 是（相同输入产生相同结果）
        [性能约束] 单写 ≤50ms（P95）
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def delete(self, session_id: str) -> None:
        """删除会话（硬删除，DEBUG 模式限定）。

        [函数名] delete
        [职责] 按 ID 删除 Session 记录
        [关联接口契约] N/A（运维接口，非业务主流程）
        [参数说明]
          参数1: session_id str 必填 UUIDv4
        [返回值]
          类型: None
        [错误码]
          错误码1: E00403 含义: DB 写失败 触发: 重试 1 次仍失败
        [注意事项] 注意1: 生产环境禁用，仅测试/DEBUG 模式可用
        [并发安全] 是
        [幂等性] 是（删除不存在的行不报错）
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def list_by_user(self, user_id: str, limit: int = 50) -> list[Session]:
        """按用户列出其所有会话。

        [函数名] list_by_user
        [职责] 查询 user_id 关联的所有 Session（按 last_active DESC）
        [参数说明]
          参数1: user_id str 必填 32hex
          参数2: limit int 可选 默认 50 规则 [1, 200] 返回条数上限
        [返回值]
          类型: List[Session]
          描述: 倒序排列的会话列表（最多 limit 条）
        [错误码]
          错误码1: E00403 含义: DB 查询失败 触发: OperationalError
        [并发安全] 是
        [幂等性] 是
        [性能约束] 单查 ≤100ms（P95）
        [来源标注] [DD-001:MD-004]
        """
        ...

    async def _execute_with_retry(self, operation_name: str, coro_factory):  # type: ignore[no-untyped-def]
        """执行写操作并在瞬时 OperationalError 时重试 1 次。

        [函数名] _execute_with_retry
        [职责] 包装写操作，捕获 OperationalError 后退避重试 1 次
        [参数说明]
          参数1: operation_name str 必填 操作名（用于日志 trace）
          参数2: coro_factory Callable 必填 协程工厂（避免 await 提前执行）
        [返回值]
          类型: Any
          描述: 协程执行结果
        [错误码]
          错误码1: E00403 含义: 写失败 触发: 2 次尝试均失败
        [并发安全] 是
        [幂等性] 依赖具体操作
        [来源标注] [DD-001:EX-011] + [DD-M推断:依据=EX-011 重试 1 次策略]
        """
        last_error: Optional[Exception] = None
        for attempt in range(self._retry_count + 1):
            try:
                return await coro_factory()
            except OperationalError as e:
                last_error = e
                if attempt < self._retry_count:
                    await asyncio.sleep(self._retry_backoff_sec)
                    continue
                raise StorageError(
                    f"session_{operation_name}_failed",
                    code="E00403",
                    cause=str(e),
                ) from e
        # 不可达：循环内部已 raise；保留以满足类型检查
        raise StorageError(
            f"session_{operation_name}_failed",
            code="E00403",
            cause=str(last_error) if last_error else "unknown",
        )

    @staticmethod
    def _map_row_to_entity(row) -> Session:  # type: ignore[no-untyped-def]
        """将 SQLAlchemy 行映射为 Session 实体。

        [函数名] _map_row_to_entity
        [职责] 数据访问层内部辅助：行 → 实体
        [参数说明]
          参数1: row Any 必填 SQLAlchemy Row 对象
        [返回值]
          类型: Session
          描述: 重建的 Pydantic Session 实体
        [并发安全] 是（纯函数）
        [幂等性] 是
        [来源标注] [DD-M推断:依据=Repository 模式标准行映射]
        """
        ...
