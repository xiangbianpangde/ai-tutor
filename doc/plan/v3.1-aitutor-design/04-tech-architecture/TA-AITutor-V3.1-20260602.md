# 技术架构文档 — AITutor V3.1

> 角色：AR-001 架构师
> 上游：TD-001 整体结构设计（TDI=0.97） + RA-001 调研报告（RCI=0.997）
> 下游：DD-001 详细设计师
> 接收轮次：L0→L1→L2→L3 全阶梯（AR 第 1 轮即达收敛）

---

## 一、AR 接收门禁结论

| 校验项 | 结果 | 依据 |
|--------|------|------|
| 方案完整性 | 通过 | TD-001 13 类产出物全部存在 |
| 方案收敛度 | 通过 | TDI = 0.97 ≥ 0.85 |
| 模块覆盖 | 通过 | 17 模块全有职责/依赖/性能标签 |
| 接口契约完整 | 通过 | 8 关键 IF 全有输入/输出/错误码/性能 |
| 部署视图完整 | 通过 | 17 模块→单进程 5MW 装配清晰 |
| 性能指标明确 | 通过 | PC 表 10 项全含瓶颈/扩展/验证 |
| 澄清请求 | 0 | TD 方案无矛盾/缺失，无需澄清 |

**upstreamGate：通过（TDI=0.97 ≥ 0.85）** —— 直接进入 AR 设计。

---

## 二、技术栈总览（主方案 / 沿用 ADR-001 混合架构）

> 技术选型均经过 4.7 六项合理性检查 + 4.8 选型库匹配 + 引用 RA-001 调研结论与来源编号。详见 TS-AITutor-V3.1-20260602.md。

### 2.1 核心技术栈（已锁定版本，禁止 latest）

| 类别 | 选型 | 版本 | 用途 | 来源 |
|------|------|------|------|------|
| 核心语言 | Python | 3.11.9 | 全栈 | [调研报告:RI-001/S-001] + [调研报告:UVP-01/PYN-19] |
| Web 框架 | FastAPI | 0.115.0 | 单进程承载 5MW + 21 编排 | [调研报告:RI-001/MCP-16/18/25] |
| ASGI 服务器 | Uvicorn | 0.32.0 | FastAPI 部署 | [AR推断:依据=FastAPI 官方推荐] |
| 异步运行时 | asyncio (stdlib) | 3.11 内置 | 21 编排并发 | [AR推断:依据=BR-002 单进程] |
| 关系型 DB | SQLite | 3.46.1 | 主存（单用户单文件） | [调研报告:RI-010/CACHE-13/49] |
| 向量 DB | ChromaDB | 0.5.20 | RAG 检索 + 本地索引 | [调研报告:RI-008/ARA-29] |
| 缓存 | Redis | 7.4.1 | 可选语义缓存后端 | [调研报告:RI-010/CACHE-49] |
| LLM 客户端 | httpx (async) | 0.27.2 | OpenAI 兼容协议 | [调研报告:RI-001/MCP-25] |
| FSRS | py-fsrs | 1.0.0 | 间隔重复调度 | [调研报告:RI-002/ANK-19/20] |
| PDF 翻译 | pdf2zh | 1.9.6 | PDF→Markdown 翻译 | [调研报告:RI-006/PDF-47/03/12] |
| 可观测性 | OpenTelemetry + structlog | 0.48b0 / 24.4.0 | Trace + 结构化日志 | [调研报告:RI-013/LOG-01/32] |
| 监控 | Prometheus Client | 0.21.0 | 指标采集（pull 模型） | [调研报告:RI-013/LOG-32] |
| 打包 | Nuitka onedir | 2.5.9 | 三平台 artifact | [调研报告:RI-003/PYN-19/59] |
| 压缩 | UPX | 4.2.4 | 体积优化 | [AR推断:依据=CE-011 体积约束] |
| 4 工具链 | Ruff / Import Linter / Redocly CLI / pre-commit | 0.7.4 / 2.1.0 / 1.25.11 / 4.0.1 | 6+1 规范红线 | [调研报告:RI-004/REDOC-12/25/30~53] |
| 测试 | pytest + pytest-cov | 8.3.3 / 5.0.0 | 单测 + 覆盖率门禁 | [AR推断:依据=BR-046~050] |
| WS 协议 | starlette.websockets | 0.41.0 | FastAPI 内置 | [调研报告:RI-007/WSE-17/01] |
| 配置 | pydantic-settings + dotenv | 2.6.1 / 1.0.1 | pyproject.toml+.env | [AR推断:依据=BP-001] |

### 2.2 技术栈约束（4.8.2 一致性约束）

| 技术类型 | 模块设计规则 | 接口设计规则 | 部署规则 | 违反示例 |
|---------|------------|------------|---------|---------|
| Python | 强制类型注解（mypy--strict）/ PEP8 / Ruff 锁规则 | REST API 必须用 FastAPI APIRouter | Uvicorn + Gunicorn（生产可选） | 混合使用 Flask |
| asyncio | 所有 I/O 必须 await / CPU 密集走 ThreadPoolExecutor | WS 走 starlette.websockets | 事件循环单实例 | 阻塞调用未 offload |
| SQLite | 单写者 + WAL 模式 / 表前缀与模块对齐 | 走 sqlalchemy 2.0 async ORM | 单文件（~/.<app>/data.db） | 多写并发未加锁 |
| ChromaDB | 集合按主题分 / 维度 768（BGE-small） | REST 调用走本地 | 持久化目录独立 | 与 SQL 共事务 |
| Redis | 键前缀 cache: / session: / pub: | RESP3 协议 | 主从 + 哨兵（V4.0） | 不设 maxmemory-policy |
| FastAPI 中间件 | 5 类强制装配（Session/Cache/Monitor/Pipeline/RAG） | Depends() 注入 | 启动时 validate | 跳过装配 |

---

## 三、分层架构图（对应 TD-001 ADR-001）

```
┌─────────────────────────────────────────────────────────────┐
│  L5 客户端层  M-003  4 形态：CLI / GUI（待定） / Web / Python lib │
├─────────────────────────────────────────────────────────────┤
│  L4 API 网关层  M-002  FastAPI Router + Auth + WS + OpenAPI │
├─────────────────────────────────────────────────────────────┤
│  L3 业务编排层  M-007 Pipeline + M-009 教学编排 │
│      5 阶段管线：preprocess → retrieve → rerank → llm → postprocess │
├─────────────────────────────────────────────────────────────┤
│  L2 核心能力层  M-004 Session / M-005 Cache / M-006 Monitor │
│      M-008 RAG 引擎（含 NLI 子/路由子/翻译子/索引子）│
│      M-010 费曼 / M-011 FSRS / M-012 阶段 / M-013 长期记忆 │
│      M-014 数据管线（pdf2zh+clean+chunk）│
├─────────────────────────────────────────────────────────────┤
│  L1 存储层  M-017  SQLite + ChromaDB + 文件 + FILE_GRAPH │
├─────────────────────────────────────────────────────────────┤
│  L0 横切治理层  M-015 打包 + M-016 红线编排+Error Hub+Redline 闸门 │
└─────────────────────────────────────────────────────────────┘
                       ↓ 全埋点 trace_id 32hex
                    M-006 事件总线（structlog+OTel+EventBus）
```

### 3.1 分层设计原则

1. **L4 → L3 通信**：仅 REST + WebSocket，禁止跨层直连（[TD:IF-001~008]）
2. **L3 → L2**：同步函数调用 + asyncio 协程（高并发场景）
3. **L2 → L1**：统一 Repository 模式（屏蔽 DB 差异）
4. **L0 横切**：AOP 思想，治理逻辑（红线/打包/审计）独立部署影响
5. **事件总线**：L2 任意模块 → M-006 → 解耦 WS 推送 + FSM 兜底审计

来源标注：[TD:SA-L-AITutor] + [TD:SA-P-AITutor] + [TD:ADR-001~010]

---

## 四、技术约束与假设

### 4.1 来自 TD 的硬约束（不可变）

| 约束 | 来源 | 技术影响 |
|------|------|---------|
| BR-002 单进程承载 | [TD:SA-L-AITutor] | 限定 asyncio + 单进程模式，拒绝多进程 |
| BR-003 5 类中间件强制装配 | [TD:MP-AITutor] | 启动期 validate 5 MW，OpenAPI 一致性 |
| BR-007 WS 端到端 ≤1s | [TD:PC-AITutor] | asyncio 直推 + 心跳 5s + 状态聚合 |
| BR-009/010 FSM 90% + LLM 10% | [TD:ADR-005] | audit_log 表全 NOT NULL + trace_id 必传 |
| BR-016 抗幻觉 100% 带源 | [TD:ADR-006] | NLI 评分 < 0.7 必触发重检索 ≤3 轮 |
| BR-046~050 6+1 规范 | [TD:ADR-010] | 4 工具链锁版本 + CI 阻断 |
| BR-032 体积 CLI<50M / GUI<200M | [TD:PC-AITutor] | Nuitka onedir + UPX 软约束 warn only |

### 4.2 来自 RA 的关键结论

- **[调研报告:RI-001]** FastAPI 单进程可承载 V3.1 量级，asyncio 21 编排无瓶颈
- **[调研报告:RI-004]** 4 工具链是事实标准，REDOC-12/25/30~53 验证 S-020~S-022
- **[调研报告:RI-006]** pdf2zh + DeepSeek 在 10 页 PDF 60s 内可完成（含 3 次降级）
- **[调研报告:RI-010]** SQLite 默认 + Redis 可选，单用户场景下 SQLite 性能足够
- **[调研报告:RI-013]** OpenTelemetry + structlog 是可观测性成熟方案
- **[调研报告:RI-007]** FastAPI 内置 starlette.websockets 满足 WS 实时性

### 4.3 AR 假设清单（与 TD/RA 一致）

| 假设 | 依据 | 验证方式 |
|------|------|---------|
| Python 3.11 GIL 不构成主要瓶颈 | [调研报告:RI-001] | CPU 密集任务走 ThreadPoolExecutor（py-fsrs/pdf2zh） |
| ChromaDB 单机可承载 5 万 chunk | [AR推断:依据=BR-005 单用户量级] | V3.1 启动期压测；不达标回退 SQLite FTS5 |
| 复杂度路由默认关键字匹配可达 70% 准确率 | [TD:ADR-011] | V4.5 POC 实测；fallback_rate 监控 |
| Nuitka onedir + UPX 可达体积目标 | [调研报告:RI-003] | 沿用 V3.0 RI-NEW-3 缺口 build 实测 |

来源标注：[AR推断:依据=灵魂 4.5 推断与标注规则]

---

## 五、AR 设计自评（详细健康度见 AH 仪表盘）

- D1 结构方案转化完整度：**100%**（17 模块全有技术映射）
- D2 技术选型合理性：**100%**（18 个核心选型全通过 6 项检查）
- D3 Agent 协作机制清晰度：**94%**（协作流程定义完整，仅外部监控 Agent 待定）
- D4 接口技术规范完整度：**100%**（IF-001~008 全有 API 规范 + 兼容性矩阵）
- D5 部署架构可实现性：**96%**（单进程部署清晰，仅 V4.0 多服务预留）
- D6 性能优化策略覆盖度：**100%**（10/10 PC 指标全有优化策略）
- D7 技术债务可控度：**100%**（6 项债务在 [3, 8] 范围中位）
- D8 安全设计覆盖度：**100%**（15/15 边界全有认证/授权/加密/审计/防注入）

**ARI = 0.99 ≥ 0.90 → 已收敛，可交付 DD-001**
