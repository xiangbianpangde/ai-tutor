# 接口注释清单 — M-006 事件总线

> 模块编号: M-006
> 负责实例: DD-M-M006
> 接口数量: 12 个（2 类 + 10 函数）
> 来源标注: [DD-001:IC-002] + [DD-001:IC-008] + [DD-001:MD-M-006] + [DD-M推断:依据=模块细化]

---

## API-M006-001: publish_event

- **接口编号**: API-M006-001
- **关联契约**: IC-002（隐式 trace_id 必填）/ IC-008（隐式事件发布）
- **实现文件**: `src/aitutor/monitor/bus.py`
- **函数签名注释**:
  ```python
  def publish_event(
      event_type: str,                       # 必填，事件类型（如 pipeline_stage / llm_chunk / fsrs_update / rest_prompt / error）
      payload: dict[str, Any] | None = None, # 可选，事件负载，需可 JSON 序列化
  ) -> None:
      """
      便捷发布事件（使用进程级默认 EventBus 单例）。

      Args:
          event_type: 事件类型标识；非空字符串；与 IC-008 event_type 一致
          payload: 事件负载；默认 None 转为空 dict；WS 帧大小 ≤ 64KB

      Returns:
          None

      Raises:
          无（订阅者异常被隔离 + ERROR 日志 E00602）

      Note:
          - 事件会自动从 current_trace_id() 补 trace_id
          - 订阅者异常不影响其他订阅者
          - 异步订阅者在此路径下被丢弃并 WARN（应用 publish_async）

      Example:
          >>> publish_event("llm_chunk", {"delta": "hi"})
      """
  ```
- **来源标注**: [DD-001:MD-M-006 函数签名 publish_event] + [DD-001:IC-008 隐式]

---

## API-M006-002: subscribe

- **接口编号**: API-M006-002
- **关联契约**: IC-002（业务模块订阅）/ IC-008（WS broadcast 订阅）
- **实现文件**: `src/aitutor/monitor/bus.py`
- **函数签名注释**:
  ```python
  def subscribe(
      event_type: str,                  # 必填，事件类型；非空
      handler: Callable[["Event"], "None | Awaitable[None]"],  # 必填，处理函数
  ) -> None:
      """
      便捷订阅（使用默认总线）。

      Args:
          event_type: 事件类型
          handler: 同步函数或 async 协程函数

      Returns:
          None

      Raises:
          ValueError: event_type 为空
          TypeError: handler 不可调用

      Note:
          - 重复订阅同一 handler 会重复触发（需调用方自去重）
          - 订阅数超过 max_subscribers_per_event=256 时静默拒绝 + ERROR

      Example:
          >>> def my_handler(ev): print(ev)
          >>> subscribe("pipeline_stage", my_handler)
      """
  ```
- **来源标注**: [DD-001:MD-M-006 函数签名 subscribe]

---

## API-M006-003: EventBus.subscribe

- **接口编号**: API-M006-003
- **关联契约**: N/A（事件总线内部 API）
- **实现文件**: `src/aitutor/monitor/bus.py`
- **函数签名注释**:
  ```python
  def subscribe(
      self,
      event_type: str,
      handler: Subscriber,  # Subscriber = Callable[[Event], None | Awaitable[None]]
  ) -> None:
      """
      在指定 EventBus 实例上注册订阅者。

      Args:
          event_type: 事件类型；非空
          handler: 同步 / 异步处理函数

      Returns:
          None

      Raises:
          ValueError: event_type 空
          TypeError: handler 不可调用

      Note:
          - 线程安全（_lock 保护）
          - 超过 max_subscribers_per_event 静默拒绝
      """
  ```
- **来源标注**: [DD-001:MD-M-006 EventBus.subscribe] + [DD-M推断:依据=线程安全要求]

---

## API-M006-004: EventBus.publish

- **接口编号**: API-M006-004
- **关联契约**: IC-002 / IC-008
- **实现文件**: `src/aitutor/monitor/bus.py`
- **函数签名注释**:
  ```python
  def publish(self, event: "Event") -> None:
      """
      同步发布事件（隔离订阅者异常）。

      Args:
          event: Event 实例；event_type 非空

      Returns:
          None

      Raises:
          无（订阅者异常隔离）

      Note:
          - 异步 handler 在此路径下被丢弃 + WARN
          - 性能：O(N)，N=订阅者数
          - 端到端延迟：建议 ≤ 100ms
      """
  ```
- **来源标注**: [DD-001:MD-M-006 类方法 publish]

---

## API-M006-005: EventBus.publish_async

- **接口编号**: API-M006-005
- **关联契约**: IC-008（WS 推送）
- **实现文件**: `src/aitutor/monitor/bus.py`
- **函数签名注释**:
  ```python
  async def publish_async(self, event: "Event") -> None:
      """
      异步发布事件（await 所有订阅者；并发触发）。

      Args:
          event: Event 实例

      Returns:
          None（协程完成后所有 handler 已被 await）

      Raises:
          无（订阅者异常隔离）

      Note:
          - 端到端延迟 ≤ 1s（IC-008 P95）
          - 使用 asyncio.gather 并发触发
      """
  ```
- **来源标注**: [DD-001:MD-M-006] + [DD-M推断:依据=IC-008 性能约束]

---

## API-M006-006: new_trace_id

- **接口编号**: API-M006-006
- **关联契约**: IC-002 / IC-004 / IC-007 / IC-008（所有 trace_id 必填接口）
- **实现文件**: `src/aitutor/monitor/trace.py`
- **函数签名注释**:
  ```python
  def new_trace_id() -> str:
      """
      生成 32hex 全局唯一追踪 ID。

      Args:
          (无)

      Returns:
          str: 32 位小写 hex 字符串（与 OTel trace_id 兼容）

      Raises:
          无

      Note:
          - 使用 secrets.token_hex(16) 强随机
          - 与进程内任何已有 trace_id 冲突概率 < 2^-128
          - 性能：O(1)
      """
  ```
- **来源标注**: [DD-001:MD-M-006 函数签名 new_trace_id] + [AR:TS-009]

---

## API-M006-007: bind_trace_id

- **接口编号**: API-M006-007
- **关联契约**: IC-002 / IC-004 / IC-007 / IC-008
- **实现文件**: `src/aitutor/monitor/trace.py`
- **函数签名注释**:
  ```python
  def bind_trace_id(trace_id: str) -> contextvars.Token:
      """
      将 trace_id 绑定到当前协程 ContextVar，返回 Token 用于 reset。

      Args:
          trace_id: 32hex 字符串；非法时自动生成 + WARN E00601

      Returns:
          contextvars.Token: 用于 reset_trace_id(token) 还原

      Raises:
          无

      Note:
          - 协程隔离（ContextVar）
          - 推荐用法：with trace_scope(trace_id): ...
      """
  ```
- **来源标注**: [DD-001:MD-M-006 函数签名 bind_trace_id] + [DD-M推断:依据=ContextVar 模式]

---

## API-M006-008: trace_scope (contextmanager)

- **接口编号**: API-M006-008
- **关联契约**: IC-002 / IC-004 / IC-007 / IC-008
- **实现文件**: `src/aitutor/monitor/trace.py`
- **函数签名注释**:
  ```python
  @contextlib.contextmanager
  def trace_scope(trace_id: Optional[str] = None) -> Iterator[str]:
      """
      上下文管理器：with 块内自动绑定 / 还原 trace_id。

      Args:
          trace_id: 32hex；None 时自动生成

      Yields:
          str: 当前生效的 trace_id

      Raises:
          无

      Note:
          - 退出时自动 reset（即便异常）
          - 嵌套使用按 ContextVar 语义工作

      Example:
          >>> with trace_scope() as tid:
          ...     publish_event("pipeline_stage", {"stage": "llm"})
      """
  ```
- **来源标注**: [DD-M推断:依据=ContextVar contextmanager 模式]

---

## API-M006-009: TraceContext.inject / extract

- **接口编号**: API-M006-009
- **关联契约**: IC-002（跨进程 trace 传播）
- **实现文件**: `src/aitutor/monitor/trace.py`
- **函数签名注释**:
  ```python
  class TraceContext:
      def inject(self) -> dict[str, str]:
          """
          序列化为跨进程传播头。

          Returns:
              dict: 包含 x-aitutor-trace-id / x-aitutor-span-id / x-aitutor-parent-span-id
          """

      @classmethod
      def extract(cls, headers: dict[str, str]) -> "TraceContext":
          """
          从传播头解析 TraceContext（缺失 / 非法时自动生成）。

          Args:
              headers: HTTP 头（键名小写）

          Returns:
              TraceContext
          """
  ```
- **来源标注**: [DD-001:MD-M-006 类 TraceContext.inject/extract] + [DD-M推断:依据=W3C traceparent 简化]

---

## API-M006-010: get_logger

- **接口编号**: API-M006-010
- **关联契约**: IC-002（所有日志字段含 trace_id）
- **实现文件**: `src/aitutor/monitor/logger.py`
- **函数签名注释**:
  ```python
  def get_logger(name: str) -> structlog.stdlib.BoundLogger:
      """
      获取带自动 trace_id 注入的 BoundLogger。

      Args:
          name: logger 名称（通常传 __name__）

      Returns:
          structlog BoundLogger（已 bind 当前 trace_id）

      Note:
          - 首次调用自动 configure_logging
          - 输出 JSON 至 stderr
      """
  ```
- **来源标注**: [DD-001:MD-M-006 StructuredLogger.bind] + [DD-M推断:依据=structlog 最佳实践]

---

## API-M006-011: StructuredLogger.error (含 E00603 降级)

- **接口编号**: API-M006-011
- **关联契约**: IC-002（异常路径日志）
- **实现文件**: `src/aitutor/monitor/logger.py`
- **函数签名注释**:
  ```python
  def error(
      self,
      event: str,         # 必填，事件名 snake_case
      **kwargs: Any,      # 可选，结构化字段
  ) -> None:
      """
      记录 ERROR 级别日志（OTel 导出失败时降级本地输出）。

      Note:
          - 触发 E00603 时降级至 stderr 文本输出，不抛错
          - 自动包含 trace_id / span_id
      """
  ```
- **来源标注**: [DD-001:MD-M-006 StructuredLogger.error] + [DD-001:MD-M-006 异常 E00603]

---

## API-M006-012: StructuredLogger.bind

- **接口编号**: API-M006-012
- **关联契约**: N/A
- **实现文件**: `src/aitutor/monitor/logger.py`
- **函数签名注释**:
  ```python
  def bind(self, **kwargs: Any) -> "StructuredLogger":
      """
      返回绑定新上下文的新 StructuredLogger（不可变）。

      Args:
          **kwargs: 附加字段（如 user_id="u-1"）

      Returns:
          StructuredLogger 新实例
      """
  ```
- **来源标注**: [DD-001:MD-M-006 StructuredLogger.bind]

---

## 接口覆盖率统计

| 指标 | 数量 | 覆盖率 |
|------|------|--------|
| M-006 函数签名（来自 MD-M-006） | 4 | 100% 注释化 |
| IC 涉及 M-006 的接口 | 5 (IC-002/004/007/008) | 100% 体现 |
| 类方法 + 内部函数 | ~25 | 100% 注释 |
| 测试覆盖 | 30+ 场景 | 3 文件 |

来源标注：[DD-001:IC-002/004/007/008] + [DD-001:MD-M-006] + [DD-M推断:依据=Observer+Mediator 实现]
