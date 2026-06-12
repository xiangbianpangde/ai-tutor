# 框架决策记录 — M-006 事件总线

> 模块编号: M-006
> 负责实例: DD-M-M006
> 决策数: 5
> 来源标注: [DD-M推断:依据=模块细化方案与最佳实践] + [DD-001:MD-M-006]

---

## FDR-M006-001: 事件总线采用 Observer + Mediator 组合模式

- **决策编号**: FDR-M006-001
- **决策标题**: 事件总线采用 Observer + Mediator 组合
- **决策状态**: 已接受
- **决策内容**: `EventBus` 同时承担 Observer（订阅/分发）与 Mediator（统一事件路由 + 单例访问）角色；进程内单例由 `get_default_bus()` 提供
- **决策理由**:
  - 简化模块拓扑：业务模块只需 `from aitutor.monitor import publish_event, subscribe`
  - Mediator 单例避免总线多实例导致事件丢失
  - Observer 解耦发布者与订阅者，符合 IC-002/IC-008 的 fan-out 需求
- **拒绝的替代方案**:
  - 方案 A（纯 Observer，无单例）：导致多实例下事件丢失 → 拒绝
  - 方案 B（强类型 event class 继承）：增加复杂度，与 Python 动态类型不符 → 拒绝
- **影响范围**: M-006 全部源文件 / IC-002 / IC-008
- **来源标注**: [DD-001:MD-M-006 设计模式] + [DD-M推断:依据=FS-M-006 文件职责]

---

## FDR-M006-002: trace_id 传播使用 ContextVar 而非 threading.local

- **决策编号**: FDR-M006-002
- **决策标题**: trace_id 跨协程传播使用 ContextVar
- **决策状态**: 已接受
- **决策内容**: `trace_id` / `span_id` 存储于 `contextvars.ContextVar`，配合 `trace_scope` contextmanager 使用
- **决策理由**:
  - FastAPI 异步栈需要协程隔离；threading.local 在 asyncio 协程间不可见
  - ContextVar 是 Python 3.7+ 标准方案，PEP 567 官方推荐
  - 与 `trace_scope` contextmanager 配合实现 with 块作用域
- **拒绝的替代方案**:
  - 方案 A（threading.local）：协程不安全 → 拒绝
  - 方案 B（显式参数透传）：侵入业务代码 → 拒绝
- **影响范围**: trace.py / bus.py / logger.py
- **来源标注**: [DD-M推断:依据=FastAPI 异步栈 + PEP 567]

---

## FDR-M006-003: 订阅者异常隔离（不阻塞主流程）

- **决策编号**: FDR-M006-003
- **决策标题**: 订阅者异常隔离 + ERROR 日志
- **决策状态**: 已接受
- **决策内容**: `EventBus.publish` / `publish_async` 捕获每个 handler 的异常，单独记录 ERROR，不影响其他订阅者
- **决策理由**:
  - MD-M-006 明确要求 E00602 处理
  - 防止单一坏订阅者拖垮整个事件流（IC-008 WS 推送高可用）
  - 与"日志不静默吞掉"原则一致（CS-AITutor-V3.1 §5.2）
- **拒绝的替代方案**:
  - 方案 A（任一 handler 异常即中断）：WS 推送易雪崩 → 拒绝
  - 方案 B（静默 pass）：违反 CS 异常处理规范 → 拒绝
- **影响范围**: bus.py `_safe_await` / `publish`
- **来源标注**: [DD-001:MD-M-006 异常 E00602] + [DD-001:CS-AITutor-V3.1 §5]

---

## FDR-M006-004: structlog + 标准 logging 双层桥接

- **决策编号**: FDR-M006-004
- **决策标题**: 日志采用 structlog 业务门面 + 标准 logging 桥接
- **决策状态**: 已接受
- **决策内容**: `StructuredLogger` 封装 structlog，处理 OTel 导出失败时降级本地 stderr 输出
- **决策理由**:
  - MD-M-006 要求 E00603 OTel 导出失败降级本地日志
  - structlog 自动 JSON 化、字段类型化
  - 双层桥接兼容 Python 标准 logging（被 FastAPI / SQLAlchemy 使用）
- **拒绝的替代方案**:
  - 方案 A（纯 structlog）：与第三方库的 logging 集成割裂 → 拒绝
  - 方案 B（纯 logging）：字段结构化能力弱 → 拒绝
- **影响范围**: logger.py
- **来源标注**: [DD-001:MD-M-006 StructuredLogger + E00603] + [AR:TS-009 OTel]

---

## FDR-M006-005: 测试文件按类拆分（test_bus / test_trace / test_logger）

- **决策编号**: FDR-M006-005
- **决策标题**: 测试目录按源文件 1:1 拆分
- **决策状态**: 已接受
- **决策内容**: `tests/unit/test_monitor/` 下分 3 个测试文件，分别覆盖 EventBus / TraceContext / StructuredLogger
- **决策理由**:
  - 与源文件结构 1:1 镜像，便于定位失败
  - 单测聚焦 + 集成留给上层（FS 已有 tests/integration/）
  - 符合 CS §6 测试规范（每个测试文件职责单一）
- **拒绝的替代方案**:
  - 方案 A（单文件 test_monitor.py）：函数过多、定位困难 → 拒绝
  - 方案 B（按测试类型拆分 unit/integration/e2e）：M-006 暂不涉及 e2e → 拒绝
- **影响范围**: tests/unit/test_monitor/
- **来源标注**: [DD-001:FS-M-006] + [DD-M推断:依据=1:1 镜像]

---

## FDR 状态汇总

| FDR 编号 | 标题 | 状态 | 影响范围 |
|---------|------|------|---------|
| FDR-M006-001 | Observer+Mediator 组合 | 已接受 | M-006 全模块 |
| FDR-M006-002 | ContextVar 传播 | 已接受 | trace/bus/logger |
| FDR-M006-003 | 订阅者异常隔离 | 已接受 | bus.py |
| FDR-M006-004 | structlog 双层桥接 | 已接受 | logger.py |
| FDR-M006-005 | 测试按类拆分 | 已接受 | tests/ |

**覆盖率：5/5 重大决策已记录（100%）**

来源标注：[DD-001:MD-M-006] + [DD-001:FS-M-006] + [DD-001:CS-AITutor-V3.1] + [DD-M推断:依据=模块细化与最佳实践]
