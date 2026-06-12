# 系统架构图 - 逻辑视图 — AITutor V2.0

> 项目：AITutor V2.0
> 日期：2026-06-01
> 角色：TD-001 顶层设计师
> 架构模式：分层架构（Presentation → Application → Domain → Infrastructure），局部插件化（GUI/CLI 适配器）

---

## 1. 总体结构（6 层 + 2 适配器）

```
┌─────────────────────────────────────────────────────────────────┐
│ L6 表现层 (Presentation)                                       │
│   ├─ P-Desktop  桌面 GUI 适配器 (Electron/Tauri/PyWebView 三选) │
│   └─ P-Web      Web 端 (Vite SPA + WebSocket)                  │
├─────────────────────────────────────────────────────────────────┤
│ L5 接口层 (Interface / OpenAPI)                                │
│   └─ FastAPI Router + WebSocket / Middleware Depends 注入      │
├─────────────────────────────────────────────────────────────────┤
│ L4 应用层 (Application / UseCase Orchestrator)                 │
│   └─ Pipeline Orchestrator: preprocess→retrieve→rerank→llm→post│
├─────────────────────────────────────────────────────────────────┤
│ L3 领域层 (Domain Engine)                                      │
│   ├─ M-002 教学策略引擎 (费曼/FSRS/阶段/休息)                  │
│   ├─ M-003 抗幻觉网关 (HaluGate NLI→SLM→LLM)                  │
│   ├─ M-008 流程状态机 (90% FSM + 10% LLM 兜底)                 │
│   └─ M-006 会话与记忆 (短期/长期/实体三层)                      │
├─────────────────────────────────────────────────────────────────┤
│ L2 数据层 (Data Service)                                       │
│   ├─ M-004 数据管线 (采集/清洗/入库/治理)                      │
│   ├─ M-005 RAG 检索 (标准/代理双路径 + 重检索)                 │
│   └─ Cache Service (SQLite / Redis 双后端)                     │
├─────────────────────────────────────────────────────────────────┤
│ L1 基础设施层 (Infrastructure)                                 │
│   ├─ M-001 启动 + 5 类中间件 (Session/Cache/Monitor/Pipeline/RAG)│
│   ├─ M-007 集成适配器 (research-tool / pdf2zh / LLM Provider)   │
│   ├─ M-009 状态推送 (STATUS.md + WebSocket)                    │
│   └─ M-010 扩展生态 (Anki / Obsidian / CLI Plugin / Web)        │
├─────────────────────────────────────────────────────────────────┤
│ L0 跨切关注 (Cross-Cutting)                                    │
│   ├─ Monitor (structlog + OTel, trace_id/span_id 强制)          │
│   ├─ Config (.env + pyproject, 密钥走环境变量)                 │
│   └─ Audit (LLM 兜底必带审计, 失败阻断)                         │
└─────────────────────────────────────────────────────────────────┘
```

[来源：TD推断 - 依据 = 4.8 模式库决策树匹配系统特征（功能主题 6+、耦合度高、单进程 FastAPI 共享 SQLite）]

---

## 2. 模块依赖图（10 模块 + 0 循环依赖）

```
M-001 启动中间件 ──→ M-002 教学策略 ──→ M-003 抗幻觉 ──→ M-009 状态推送
       │                  │                 │                 ↑
       ↓                  ↓                 ↓                 │
M-007 集成适配器 ──→ M-004 数据管线 ──→ M-005 RAG 检索 ──→ M-006 会话记忆
       │                  │                 │                 │
       └─→ M-008 状态机 (兜底 10%) ──────────────────────────┘
                                              ↓
                                       M-010 扩展生态
```

依赖规则：L1→L2→L3→L4→L5→L6 单向，禁止反向（[BR-039]）。

---

## 3. 关键设计决策点

| 决策点 | 选择 | 来源 |
|--------|------|------|
| 架构模式 | 分层（主） + 插件化适配器（GUI/CLI） | TD推断 - 4.8.1 决策树 |
| 模块粒度 | 10 模块 / 20 功能 = 0.5（在 0.3-0.8 范围内） | TD推断 - 4.2 简洁度 |
| 抗幻觉路径 | HaluGate 三级级联 NLI→SLM→LLM | [SA:BP-007] |
| 状态机/兜底 | 90% FSM + 10% LLM（[BR-020]） | [SA:BR-020] |
| RAG 路径 | 80% 标准 + 20% 代理（[BR-029]） | [SA:BR-029] |
| GUI 形态 | 三选一保留至 PM 决策（[CR-001]） | [SA:CR-001] |
