# FF-M-002-AITutor-V3.1-20260602 — M-002 API 网关 + WS 文件框架结构

> 负责模块: M-002 API 网关 + WS
> 负责 DD-M: DD-M-002
> 来源标注: [DD-001:FS-M-002] + [DD-001:MD-M-002] + [DD-001:IC-001/002/008] + [DD-M推断]

---

## 一、模块文件框架

```
M-002/
├── src/aitutor/api/
│   ├── __init__.py              ← [职责：模块初始化，导出公共接口与 Router 注册入口]
│   ├── deps.py                  ← [职责：FastAPI Depends 依赖注入层]
│   ├── auth.py                  ← [职责：Auth 鉴权依赖（Token 校验）]
│   ├── rate_limit.py            ← [职责：单用户 QPS / 并发回合限流策略]
│   ├── openapi.py               ← [职责：OpenAPI Schema 定制化生成器]
│   └── v1/
│       ├── __init__.py          ← [职责：v1 APIRouter 聚合根]
│       ├── session.py           ← [职责：/session 路由（创建/查询/关闭）]
│       ├── turn.py              ← [职责：/turn 路由（核心 IC-002）]
│       ├── ingest.py            ← [职责：/ingest 路由（PDF 上传）]
│       ├── health.py            ← [职责：/health 路由（liveness/readiness）]
│       └── ws.py                ← [职责：/ws 路由（WebSocket 推送）]
└── tests/
    ├── unit/test_api/
    │   ├── __init__.py          ← [职责：测试目录初始化与公共 fixture]
    │   ├── test_auth.py         ← [职责：Auth 鉴权测试（5 用例）]
    │   ├── test_rate_limit.py   ← [职责：限流测试（5 用例）]
    │   └── test_ws.py           ← [职责：WS 连接管理测试（7 用例）]
    └── integration/
        └── test_api_e2e.py      ← [职责：M-002 端到端集成测试（4 用例）]
```

---

## 二、文件列表（16 个文件）

| 编号 | 文件路径 | 职责 | 关联类 | 来源 |
|------|---------|------|--------|------|
| F01 | src/aitutor/api/__init__.py | 模块初始化与公共符号导出 | - | [DD-001:FS-M-002] |
| F02 | src/aitutor/api/deps.py | Depends 注入层 | get_current_user / check_rate_limit_dep / get_trace_id | [DD-001:MD-M-002] |
| F03 | src/aitutor/api/auth.py | Auth 鉴权 | AuthDependency / TokenStore / UserContext | [DD-001:MD-M-002] |
| F04 | src/aitutor/api/rate_limit.py | 限流策略 | RateLimiter / RateLimitStats | [DD-001:MD-M-002] |
| F05 | src/aitutor/api/openapi.py | OpenAPI 生成 | OpenAPIGenerator | [DD-001:MD-M-002] |
| F06 | src/aitutor/api/v1/__init__.py | v1 路由聚合 | APIRouterRegistry | [DD-001:FS-M-002] |
| F07 | src/aitutor/api/v1/session.py | /session 路由 | - | [DD-001:IC-002] |
| F08 | src/aitutor/api/v1/turn.py | /turn 路由（核心） | - | [DD-001:IC-002] |
| F09 | src/aitutor/api/v1/ingest.py | /ingest 路由 | - | [DD-001:IC-004] |
| F10 | src/aitutor/api/v1/health.py | /health 路由 | - | [DD-001:IC-001] |
| F11 | src/aitutor/api/v1/ws.py | /ws 路由 | WSConnectionManager / WSEvent | [DD-001:MD-M-002] + [DD-001:IC-008] |
| F12 | tests/unit/test_api/__init__.py | 测试目录初始化 | - | [DD-001:MD-M-002 测试策略] |
| F13 | tests/unit/test_api/test_auth.py | Auth 单元测试 | - | [DD-001:MD-M-002 测试策略 16 用例] |
| F14 | tests/unit/test_api/test_rate_limit.py | 限流单元测试 | - | [DD-001:MD-M-002 测试策略] |
| F15 | tests/unit/test_api/test_ws.py | WS 单元测试 | - | [DD-001:MD-M-002 测试策略] |
| F16 | tests/integration/test_api_e2e.py | E2E 集成测试 | - | [DD-001:MD-M-002 测试策略] |

---

## 三、文件间依赖关系

```
M-001 main.py / app_factory.py
  ↓
src/aitutor/api/__init__.py
  ↓ include_router
src/aitutor/api/v1/__init__.py (APIRouterRegistry)
  ↓
  ├── v1/session.py → deps.py → auth.py + rate_limit.py
  ├── v1/turn.py    → deps.py → auth.py + rate_limit.py
  ├── v1/ingest.py  → deps.py → auth.py
  ├── v1/health.py  → (无业务依赖)
  └── v1/ws.py      → auth.py
  ↓
../monitor/trace.py (M-006 事件总线) + ../shared/types.py

测试:
  tests/unit/test_api/test_auth.py → src/aitutor/api/auth.py
  tests/unit/test_api/test_rate_limit.py → src/aitutor/api/rate_limit.py
  tests/unit/test_api/test_ws.py → src/aitutor/api/v1/ws.py
  tests/integration/test_api_e2e.py → src/aitutor/api/*
```

---

## 四、文件结构 5 项合规检查（4.7 客观检查）

| 检查项 | 通过条件 | M-002 检查结果 |
|--------|---------|---------------|
| 目录层级 | ≥ 2 层 | ✅ 3 层（aitutor/api/）|
| 文件命名 | snake_case | ✅ 全部 snake_case |
| 文件职责 | 单一明确 | ✅ 每个文件单一职责 |
| 依赖关系 | 无循环依赖 | ✅ 无循环（Import Linter 验证）|
| 最佳实践 | src layout + FastAPI 实践 | ✅ 完全符合 |

**合规度 = 5/5 = 高**

---

## 五、DD-M 洞察（1 条）

[DD-M洞察-001] **M-002 鉴权与限流解耦设计** — `auth.py` 负责 Token 校验与 UserContext 构造（无状态、可缓存），`rate_limit.py` 负责限流策略（带状态、需要锁）。两者通过 `deps.py` 解耦，避免限流逻辑污染鉴权代码。**风险**：若未来引入多租户，限流维度需扩展（per-tenant），需提前在 `RateLimiter` 中预留 tenant_id 维度。**来源**：[DD-M推断:依据=关注点分离原则]

---

## 六、阶梯退出检查

- ① 全部目录已创建: 是
- ② 全部文件已创建: 是
- ③ 命名合规: 是
- ④ D2 文件结构合规度: 100%

来源标注: [DD-001:FS-M-002] + [DD-001:MD-M-002] + [DD-M推断]
