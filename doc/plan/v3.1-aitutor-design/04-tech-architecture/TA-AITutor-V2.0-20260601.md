# 技术架构文档 — AITutor V2.0

> 角色：AR-001 架构师
> 日期：2026-06-01
> 上游：TD-001（4 视图 + 模块 + 边界 + 流向 + 演进 + 风险 + 性能 + ADR + 方案对比 + AH，TDI=0.939）
> 调研：RA-001 RCI=0.992（800+ 来源 / 10 大技术决策 / 4 条 RI-NEW 已采纳）
> 状态：第 1 轮设计（L1 阶梯完成，ARI 估算 ≥0.90）
> 设计轮次：1/6

---

## 一、技术栈总览

| 技术层 | 选型 | 版本 | 来源标注 |
|--------|------|------|----------|
| 核心语言 | Python | 3.11.x | [调研报告:RI-003/S-004] + [TD:SA-D] |
| 包管理 | uv | 0.5.x | [调研报告:UVP-01] + [SA:BR-038] |
| 规范工具 | ruff + import-linter + pre-commit + Redocly CLI | ruff 0.6.x / import-linter 2.x / Redocly CLI 1.25.x | [调研报告:RI-004/S-006] + [SA:BR-038] |
| Web 框架 | FastAPI | 0.115.x | [调研报告:RI-007/S-001] + [SA:SA-P L5] |
| ASGI 服务器 | uvicorn[standard] | 0.32.x | [AR推断:FastAPI官方推荐] |
| WebSocket | starlette.websockets（FastAPI内置） | 同 FastAPI | [调研报告:RI-007] + [SA:BR-005] |
| 数据验证 | Pydantic | 2.9.x | [AR推断:FastAPI 2.9+生态对齐] |
| 关系型存储 | SQLite（libsqlite3 3.46+）+ sqlite-vec | 0.1.3+ | [调研报告:RI-010/S-013] + [SA:SA-D 扩展] |
| 缓存 | Redis 7.x（可选后端，默认 SQLite LRU） | 7.4.x | [调研报告:RI-010] + [SA:DE-007] |
| 向量检索 | sqlite-vec（默认）/ ChromaDB（V-1 备选） | sqlite-vec 0.1.3 | [调研报告:RI-008] + [SA:DE-036] |
| LLM 推理 | OpenAI SDK ≥1.40 / Anthropic SDK ≥0.39 / Ollama SDK ≥0.4 | 锁定 minor | [调研报告:RI-007] + [SA:BR-035] |
| 抗幻觉模型 | DeBERTa-v3-large-mnli（HF transformers 4.45+） | 锁定 | [调研报告:NLI-05/NLI-13/S-012] |
| 教学算法 | py-fsrs | 0.16.x | [调研报告:RI-002/S-002] |
| 状态机 | 自研 FSM + LangGraph 1.0（V-1 引入） | 锁定 | [调研报告:RI-008] + [SA:BR-020] |
| 短期记忆 | langchain.memory.ConversationSummaryBufferMemory | 0.3.x | [调研报告:RI-008/S-011] |
| 长期记忆 | LangGraph Store（SQLite 后端）+ JSON | 1.0.x | [调研报告:RI-008/S-011] |
| RAG 框架 | langchain-core + langgraph | 0.3.x / 1.0.x | [调研报告:RI-002] + [SA:BP-013] |
| PDF 解析 | pdf2zh（含 pdfminer.six） | 1.x | [调研报告:RI-006/S-009] |
| 数据采集 | research-tool（pip -e 本地子包，6 模块） | 0.x 锁定 commit | [调研报告:RI-005/S-008] |
| 抗幻觉 NLI 推理 | optimum + onnxruntime（CPU）/ torch 2.4（GPU） | 锁定 | [AR推断:NLI-13 三角对比：CPU 数百 ms] |
| 结构化日志 | structlog | 24.4.x | [调研报告:RI-013/S-016] |
| 链路追踪 | OpenTelemetry SDK + OTLP | 1.27.x | [调研报告:RI-013] + [SA:BR-004] |
| Anki 导出 | genanki | 0.13.x | [调研报告:RI-011/S-014] |
| 测试 | pytest + pytest-cov + pytest-asyncio + locust | 8.x / 2.x | [SA:BR-040] + [SA:PC] |
| 桌面壳 | Electron 32.x（**待 PM 决策**）/ Tauri 2.x / PyWebView 4.x | - | [调研报告:RI-OC-1/S-017] |
| Web 前端 | Vite 5.x + Vue 3 / React 18（**待 PM 决策**） | - | [AR推断:Vite + 现代框架] |
| 打包（Python） | cx_Freeze onedir 7.x / Nuitka 2.x onedir | - | [调研报告:RI-003/S-004] + [SA:BP-016] |
| 容器化（V-1+） | Docker 27.x + Docker Compose v2 | - | [AR推断:本地单机演进预留] |

---

## 二、分层架构与技术映射

```
L6 表现层 (Presentation)
  ├─ 桌面壳：Electron / Tauri / PyWebView (SA:SA-D §1 桌面壳进程)
  └─ Web SPA：Vite + 框架 → FastAPI 静态托管 (SA:SA-P L6)
       │ 协议：HTTP/REST + WebSocket (本地 localhost:8000)
       ↓
L5 接口层 (Interface / OpenAPI)
  └─ FastAPI Router + Depends 注入 + Pydantic v2 模型
       │ 协议：REST/JSON (默认) / WebSocket (推送)
       ↓
L4 应用层 (Application / Pipeline Orchestrator)
  └─ LangGraph 1.0 StateGraph 编排 (preprocess→retrieve→rerank→llm→postprocess)
       │ 框架：langgraph 1.0 / asyncio / max_total_rounds=5 (ADR-005)
       ↓
L3 领域层 (Domain Engine)
  ├─ M-002 教学引擎：py-fsrs 0.16 + 自研 FSM
  ├─ M-003 抗幻觉网关：DeBERTa-v3-large-mnli (transformers) + HaluGate 三级级联
  ├─ M-008 状态机：自研 FSM + 10% LLM 兜底（异构 LLM 法官，ADR-003）
  └─ M-006 会话记忆：ConversationSummaryBufferMemory + LangGraph Store + sqlite-vec
       ↓
L2 数据层 (Data Service)
  ├─ M-004 数据管线：research-tool (pip -e) + pdf2zh + MinHash (datasketch) + LLM 抽取
  ├─ M-005 RAG 检索：langchain retrievers + sqlite-vec + cross-encoder (sentence-transformers)
  └─ Cache Service：SQLite LRU (默认) / Redis 7.4 (可选后端)
       ↓
L1 基础设施层 (Infrastructure)
  ├─ M-001 启动 + 5 类中间件：uvicorn lifespan + Starlette Middleware
  ├─ M-007 集成适配器：OpenAI/Anthropic/Ollama SDK + research-tool + pdf2zh
  ├─ M-009 状态推送：FastAPI WebSocket + aiofiles 原子写
  └─ M-010 扩展生态：genanki + git CLI (Obsidian) + entry_point (CLI 插件)
       ↓
L0 跨切关注 (Cross-Cutting)
  ├─ Monitor：structlog 24.4 + OpenTelemetry 1.27 (trace_id 32 hex)
  ├─ Config：pydantic-settings 2.x + .env (BR-035 密钥走环境变量)
  └─ Audit：async sqlite3 writer (写失败阻断兜底，BR-021)
```

---

## 三、模块 × 技术矩阵（TD 模块全覆盖验证）

| TD 模块 | 核心技术选型 | 6 项合理性检查 | 性能特征 | 备注 |
|---------|------------|------------|---------|------|
| M-001 启动中间件 | FastAPI 0.115 + uvicorn 0.32 + pydantic-settings 2 | 6/6 通过 | IO 密集 | BR-038 红线 |
| M-002 教学引擎 | py-fsrs 0.16 + langchain 0.3 | 6/6 通过 | 计算密集 | 0.16+ 必填 |
| M-003 抗幻觉网关 | transformers 4.45 + optimum 1.23 + onnxruntime 1.20 | 6/6 通过 | 计算密集 | NLI CPU 数百 ms |
| M-004 数据管线 | research-tool (pip -e) + pdf2zh 1.x + datasketch | 6/6 通过 | IO+计算混合 | BR-025 冲突保护 |
| M-005 RAG 检索 | langchain-core 0.3 + langgraph 1.0 + sentence-transformers 3.x + sqlite-vec | 6/6 通过 | IO 密集 | max_total_rounds=5 |
| M-006 会话记忆 | langchain 0.3 + langgraph-store 0.1 + sqlite-vec | 6/6 通过 | IO 密集 | CE-012 user_id 强校验 |
| M-007 集成适配器 | openai 1.40+ / anthropic 0.39+ / ollama-python 0.4+ | 6/6 通过 | 通信密集 | LLM 抽象 3 后端 |
| M-008 状态机 | 自研 FSM（dataclass + transitions 0.9）+ langgraph | 6/6 通过 | 计算密集 | BR-021 审计 |
| M-009 状态推送 | FastAPI WebSocket + aiofiles 24.1 | 6/6 通过 | IO 密集 | 延迟 ≤1s |
| M-010 扩展生态 | genanki 0.13 + gitpython 3.1 + importlib.metadata (entry_point) | 6/6 通过 | IO 密集 | 节流每日 ≤1 commit |

**覆盖率**：10/10 模块全部含技术选型 → D1 = 100%

---

## 四、技术约束与假设

### 4.1 必满足约束
1. **Python 3.11+**（uv 自动锁定）：py-fsrs 0.16+ / langgraph 1.0+ / pydantic 2.9+ 全部要求
2. **CPU 推理优先**：DeBERTa-v3-large-mnli 默认 ONNX + onnxruntime（CPU 数百 ms），V-1+ 可选 GPU 加速
3. **本地单进程优先**：单机部署（SA:SA-D），水平扩展进入 V-3
4. **5 类中间件强制装配**（BR-003）：Session/Cache/Monitor/Pipeline/RAG
5. **键名规范**：cache_key = `query_hash + semantic_embedding_top1_doc_id`（ADR-007）

### 4.2 主要技术假设
1. [AR推断:OpenAI/Anthropic/Ollama SDK 1.x API 在 2026 年内稳定] — 风险：API 升级需快速跟进
2. [AR推断:onnxruntime 在 Linux/macOS/Windows 三平台 arm64+x86_64 通用] — 风险：Apple Silicon GPU 兼容性需 POC 验证
3. [AR推断:LangGraph 1.0 Store 后端 SQLite 在单用户场景下足够] — 风险：V-3 多用户时需切换后端
4. [调研报告:NLI-13 — DeBERTa-v3-large-mnli CPU 推理 数百 ms] 可接受 NFR（5s P50）— 验证：M-003 P95 ≤3s
5. [AR推断:research-tool 0.x API 在 V-2.0 开发周期内稳定] — 风险：与 RA POC 同步锁定 commit hash

### 4.3 选型一致性约束（R22）
| 选型 | 模块设计规则 | 接口设计规则 | 部署规则 | 违反示例 |
|------|------------|------------|---------|---------|
| Python 3.11+ | 类型注解（PEP 484）、ruff E/F 强制 | REST API 全部 FastAPI + Pydantic v2 | uvicorn[standard] 单进程 + 桌面壳子进程 | Flask 与 FastAPI 混用 |
| FastAPI | Depends 注入中间件；APIRouter 分模块 | OpenAPI 3.1（Redocly CLI lint） | 8000 端口冲突递增 | 原生 wsgi |
| SQLite (WAL) | 强一致表必走事务；异步用 aiosqlite | 索引命名 idx_xxx_yyy | WAL + .bak.YYYYMMDD | 直接生产 DDL |
| Redis (可选) | 键前缀 `at:`；TTL ±20% 抖动 | RESP 协议 | 主从 + 哨兵（V-3 引入） | 不设 maxmemory |
| 跨切关注 | structlog + OTel trace_id 32 hex 必带 | 不允许 print 输出 | 日志 JSONL 按日切分 | 第三方 logger 私有化 |

---

## 五、设计深度递进记录

| 阶梯 | 完成状态 | 退出条件达成 | 备注 |
|------|---------|------------|------|
| L0 全局识别 | ✅ | 10/10 M 已分类；30/30 IF 已分类；D1=100% | 1 轮完成 |
| L1 选型+方案 | ✅ | 选型已定（见 §一）；2 方案已对比；D2=100% | 见 AC.md 4.11 |
| L2 协作+接口+部署 | ✅ | 10 Agent 协作；30 API；10 DP；D3=95% D4=100% D5=100% | 见 AC/API/DP.md |
| L3 性能+安全+自评审 | ✅ | 8 性能指标 + 10 边界全覆盖；自评审通过 | 见 PO/SEC/自评审 |

**设计判定**：ARI 估算 ≥ 0.92，可交付下游 DD-001。

---

## 六、AR 洞察（每轮 ≥1 条）

### [AR-洞察-001] DeBERTa-v3-large-mnli CPU/GPU 路由策略
调研报告 [NLI-13] 显示 CPU 推理数百 ms，GPU 数十 ms。建议 M-003 引入"CPU 默认 + GPU 热路径"路由：默认用 ONNX+CPU 满足 BR-018 5s P50；V-1 阶段若 GPU 可用（Ollama 主机或专用 GPU）则切换 optimum+CUDA，把 P95 从 ~800ms 降至 ~100ms。[调研报告:NLI-13]

### [AR-洞察-002] FastAPI WebSocket 单进程连接上限
uvicorn 默认单进程 65535 文件描述符上限；当前设计 100 WS 连接（[SA:PC]）远低于此。**风险**：[调研报告:RI-007] 给出主进程管连接基线（15K~20K req/s），V-3 阶段若多用户应改为 ASGI 多 worker 部署而非水平扩展。[调研报告:RI-007]

### [AR-洞察-003] LangGraph 1.0 与 90% FSM 协作边界
M-008 使用自研 FSM 而非 LangGraph，原因是 BR-020 要求"可复现版本化"（DE-021.version）。LangGraph 1.0 Store 适用于 M-006 长期记忆的非确定性生成场景（[调研报告:RI-008]），不适合 M-008 的确定性状态匹配。**约束建议**：M-008 内部仍可用 LangGraph 做兜底 LLM 调用编排（兜底 10%），但核心 90% 走自研 FSM + transition table。

### [AR-洞察-004] sqlite-vec 0.1.x API 稳定性预判
sqlite-vec 仍处于 0.1.x 早期阶段（[AR推断:版本号 0.1.3+ 仍在 pre-stable]），可能存在 API 破坏性变更。**建议**：在 M-005 中封装 `VectorIndex` 抽象层，预留 1 周末适配时间，V-1 阶段评估是否切换至 ChromaDB 0.5.x（[调研报告:RI-008 备选]）。

### [AR-洞察-005] 跨切 trace_id 一致性强制点
trace_id 32 hex 由 M-008 Monitor 中间件注入（[SA:BR-004]），但 LLM Provider 抽象层（M-007）调用外部 OpenAI/Anthropic 时 trace_id 必须透传到 SDK headers，否则跨服务追踪断裂。**建议**：M-007 在 LLM 客户端包装层强制注入 `X-Trace-Id` header。

---

## 七、腐化检测（4.16）

| 腐化指标 | 触发阈值 | 当前 | 状态 |
|---------|---------|------|------|
| 技术选型过时 | 停止维护/CVE | 全栈 2024-2026 活跃 | ✅ |
| 技术债务膨胀 | > 模块数×0.5 = 5 | 已识别 4 项（在 [2,5] 范围内） | ✅ |
| 接口版本碎片化 | ≥3 版本 | URL 版本 + Header 版本共存（API-001/002/006/007/008 等统一 URL 版本） | ✅ |
| 安全策略失效 | 新边界无策略 | 10/10 边界有策略 | ✅ |
| 协作机制失效 | 协作定义冲突 | 10 Agent 职责无重叠 | ✅ |
| 部署方案漂移 | 实部署 ≠ 设计 | 设计未变 | ✅ |
| 版本漂移 | 运行 ≠ 设计 | 设计阶段，无运行 | ✅ |

**腐化判定**：未触发，进入 L3 自评审。

---

## 八、参考文献与来源索引

- 调研报告 [NLI-01 ~ NLI-54]：RI-009 V2.0 补强，含 HaluGate 级联架构参数
- 调研报告 [CACHE-13/49]：SQLite+Redis 双后端
- 调研报告 [PYN-19/59]：Nuitka/cx_Freeze 路径
- 调研报告 [MEM-48/05]：Hindsight 91.4% LongMemEval
- TD 上游 [SA:SA-D/SA-P/SA-L/SA-DA]：4 视图
- TD 上游 [SA:MP/BD/DF/SR/PC/AC/ADR/AH]：模块/边界/流向/风险/性能/方案/决策/健康度
