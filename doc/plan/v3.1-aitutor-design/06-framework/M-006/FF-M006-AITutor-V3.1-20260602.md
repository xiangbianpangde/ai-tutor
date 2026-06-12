# 文件框架结构 — M-006 事件总线（Observer + Mediator）

> 模块编号: M-006
> 模块名称: 事件总线（Observer + Mediator）
> 负责实例: DD-M-M006
> 来源标注: [DD-001:FS-M-006] + [DD-001:MD-M-006] + [AR:TS-009/010] + [AR:SEC-010]

---

## 一、文件框架

```
M-006/
├── src/
│   └── aitutor/
│       └── monitor/                ← M-006 根目录
│           ├── __init__.py         ← [职责: 模块初始化 + 公共接口 re-export]
│           ├── bus.py              ← [职责: 事件总线（EventBus / Event / 单例）]
│           │   - [类 Event 注释] 事件载体
│           │   - [类 EventBus 注释] Observer+Mediator 组合
│           │   - [函数 publish_event / subscribe / get_default_bus 注释]
│           ├── trace.py            ← [职责: trace_id 生成与传播]
│           │   - [函数 new_trace_id / bind_trace_id / trace_scope 注释]
│           │   - [类 TraceContext 注释] inject/extract/start/end
│           └── logger.py           ← [职责: structlog 桥接 + 业务日志门面]
│               - [函数 configure_logging / get_logger 注释]
│               - [类 StructuredLogger 注释] info/warn/error/debug/bind
└── tests/
    └── unit/
        └── test_monitor/           ← M-006 测试目录
            ├── __init__.py         ← [职责: 测试包标记]
            ├── test_bus.py         ← [职责: EventBus 单元测试，10 用例]
            │   - [测试场景1: 同步 subscribe+publish]
            │   - [测试场景2: publish_async await handler]
            │   - [测试场景3: 多订阅者全部触发]
            │   - [测试场景4: 订阅者异常隔离]
            │   - [测试场景5: event_type 隔离]
            │   - [测试场景6: unsubscribe 移除]
            │   - [测试场景7: 自动补 trace_id]
            │   - [测试场景8: 订阅者超限]
            │   - [测试场景9: 非法 event_type 抛错]
            │   - [测试场景10: clear() 清空]
            ├── test_trace.py       ← [职责: trace_id / TraceContext 单元测试]
            │   - [测试场景1: 32hex 格式]
            │   - [测试场景2: ID 不重复]
            │   - [测试场景3: bind+current 往返]
            │   - [测试场景4: reset 还原]
            │   - [测试场景5: 非法 ID 自动生成]
            │   - [测试场景6: trace_scope 自动 reset]
            │   - [测试场景7: start/end 耗时]
            │   - [测试场景8: inject/extract 往返]
            │   - [测试场景9: extract 缺失头]
            │   - [测试场景10: extract 非法 ID]
            └── test_logger.py      ← [职责: StructuredLogger 单元测试]
                - [测试场景1: configure_logging 幂等]
                - [测试场景2: get_logger 返回 logger]
                - [测试场景3: info 输出 JSON]
                - [测试场景4: warn 级别]
                - [测试场景5: error 级别]
                - [测试场景6: debug 在 DEBUG 级别可见]
                - [测试场景7: bind 返回新实例]
                - [测试场景8: error 异常降级]
                - [测试场景9: trace_id 自动注入]
                - [测试场景10: get_logger 多次调用不抛错]
```

---

## 二、文件间依赖关系

```
__init__.py
  ↓ (re-export)
bus.py  ←——→  trace.py  ←——→  logger.py
  ↑              ↑                ↑
  └──────────────┴────────────────┘
       (仅限 M-006 内部 import，无跨模块依赖)

tests/test_monitor/
  ↓
src/aitutor/monitor/   (单测从 aitutor.monitor 导入)
```

**依赖约束：**
- bus.py → logger.py（订阅者异常日志）
- bus.py → trace.py（自动补 trace_id）
- trace.py → logger.py（WARN 日志）
- logger.py → trace.py（自动注入 trace_id）
- **禁止依赖**：`api/`、`session/`、`cache/`、`pipeline/`、`rag/`、`teaching/`、`memory/`、`storage/`、`redline/`（Import Linter contract:5）

---

## 三、文件职责矩阵

| 文件 | 职责 | 依赖 | 行数预算 |
|------|------|------|---------|
| `__init__.py` | 公共接口导出（EventBus / TraceContext / StructuredLogger / 便捷函数） | bus/trace/logger | ~25 |
| `bus.py` | 事件总线核心（订阅/发布/隔离） | logger, trace | ~250 |
| `trace.py` | trace_id 生成、ContextVar 传播、跨进程头序列化 | logger | ~250 |
| `logger.py` | structlog 配置 + 业务日志门面 + OTel 降级 | trace | ~200 |
| `tests/test_bus.py` | EventBus 单元测试 10+ 用例 | bus | ~200 |
| `tests/test_trace.py` | trace 单元测试 10 用例 | trace | ~150 |
| `tests/test_logger.py` | logger 单元测试 10 用例 | logger | ~150 |

**单文件函数数校验：**
- bus.py：~7 函数 + 2 类方法 = 满足 ≤20 上限
- trace.py：~7 函数 + 4 类方法 = 满足 ≤20 上限
- logger.py：~6 函数 + 5 类方法 = 满足 ≤20 上限

---

## 四、来源标注

| 维度 | 来源 |
|------|------|
| 文件组织 | [DD-001:FS-M-006]（monitor/ 三件套） |
| 类设计 | [DD-001:MD-M-006]（EventBus / TraceContext / StructuredLogger） |
| 函数签名 | [DD-001:MD-M-006]（publish_event / subscribe / new_trace_id / bind_trace_id） |
| 状态机 | N/A |
| 异常码 | [DD-001:MD-M-006] E00601/E00602/E00603 |
| 日志策略 | [DD-001:MD-M-006] structlog JSON |
| 测试策略 | [DD-001:MD-M-006] 10 用例 / 覆盖率≥80% |
| 代码风格 | [DD-001:CS-AITutor-V3.1] Ruff + Google Docstring + mypy --strict |
| 命名规范 | [DD-001:CS-AITutor-V3.1] snake_case / PascalCase / UPPER_SNAKE_CASE |
| Import Linter | [DD-001:CS-AITutor-V3.1] contract:5（monitor 不依赖其他业务模块） |

来源标注：[DD-001:FS-M-006] + [DD-001:MD-M-006] + [AR:TS-009/010] + [AR:SEC-010] + [DD-M推断:依据=Observer+Mediator 模式]
