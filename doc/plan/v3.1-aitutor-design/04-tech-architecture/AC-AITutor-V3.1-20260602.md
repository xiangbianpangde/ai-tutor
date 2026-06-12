# Agent 协作方案 — AITutor V3.1

> 角色：AR-001 架构师
> 接收：TD-001 模块划分 + 数据流向 + 演进路线
> 配套：API-AITutor-V3.1-20260602.md（接口技术规范）

---

## 一、Agent 角色清单（17 个业务 Agent + 1 个编排 Agent）

> 单进程内部按"业务模块=逻辑 Agent"建模，物理上仍是 1 个 Python 进程 + 17 个协程 Agent。外部监控系统（Prometheus）作为旁观 Agent 存在。

| Agent 编号 | 名称 | 业务模块 | 生命周期 | 资源配额 |
|----------|------|---------|---------|---------|
| AG-001 | 服务入口 Agent | M-001 | 进程级 | 0.2 CPU / 256MB |
| AG-002 | API 网关 Agent | M-002 | 进程级 | 0.5 CPU / 512MB |
| AG-003 | 客户端入口 Agent | M-003 | 进程级 | 0.3 CPU / 256MB |
| AG-004 | Session Agent | M-004 | 进程级 | 0.2 CPU / 256MB |
| AG-005 | Cache Agent | M-005 | 进程级 | 0.3 CPU / 512MB |
| AG-006 | 事件总线 Agent | M-006 | 进程级 | 0.2 CPU / 128MB |
| AG-007 | Pipeline 调度 Agent | M-007 | 进程级 | 0.5 CPU / 512MB |
| AG-008 | RAG 引擎 Agent | M-008 | 进程级 | 1.0 CPU / 1.5GB（NLI 加载） |
| AG-009 | 教学编排 Agent | M-009 | 进程级 | 0.5 CPU / 512MB |
| AG-010 | 费曼评分 Agent | M-010 | 请求级 | 0.3 CPU / 256MB |
| AG-011 | FSRS 调度 Agent | M-011 | 请求级 | 0.2 CPU / 128MB |
| AG-012 | 阶段校准 Agent | M-012 | 请求级 | 0.1 CPU / 64MB |
| AG-013 | 会话编排 Agent | M-013 | 进程级 | 0.3 CPU / 256MB |
| AG-014 | 数据管线 Agent | M-014 | 请求级 | 0.5 CPU / 512MB（PDF 翻译） |
| AG-015 | 打包调度 Agent | M-015 | 任务级 | 1.0 CPU / 1GB（CI 触发） |
| AG-016 | 红线编排 Agent | M-016 | 进程级 | 0.3 CPU / 256MB |
| AG-017 | 存储 Agent | M-017 | 进程级 | 0.3 CPU / 512MB |
| AG-018 | 监控旁观 Agent | M-006 → Prom | 进程级 | 0.1 CPU / 64MB（独立 scrape 进程） |

**协作关系说明**：M-001 是启动器，依次创建 M-002~M-017；M-007 协调 M-008/M-009/M-010/M-014 完成管线；M-006 负责全埋点；M-016 治理所有模块。

来源标注：[TD:MP-AITutor] + [TD:SA-L-AITutor]

---

## 二、Agent 协作协议（核心 8 类 Agent 详化）

### AG-001 服务入口 Agent

- **职责边界**：负责 FastAPI 启动 + 5MW 装配 + 健康端点 + 配置加载；**不负责**业务路由
- **输入接口**：`config_path: str` (pyproject.toml+.env)
- **输出接口**：`app: FastAPI`、`middleware_status: dict`
- **通信协议**：进程内函数调用 / `Depends()` 注入
- **状态同步**：无状态（仅持有 app 实例引用）
- **冲突解决**：启动期 validate 失败 → 拒绝启动 + 输出错误码 E00101/E00102/E00103
- **故障恢复**：Uvicorn 自动重启（worker 模式可选）；启动失败不留 PID
- **资源配额**：0.2 CPU / 256MB / 启动 ≤30s
- **生命周期**：进程级（创建于 OS 启动时，销毁于 SIGTERM）
- **来源标注**：[TD:IF-001] + [TD:MP-M-001]

### AG-002 API 网关 Agent（含 WS）

- **职责边界**：HTTP 路由 + Auth 校验 + WS 推送 + OpenAPI 生成；**不负责**业务逻辑
- **输入接口**：HTTP Request / WebSocket Frame
- **输出接口**：HTTP Response / WS Event (`{event_type, payload, ts}`)
- **通信协议**：FastAPI Router（HTTP）+ starlette.websockets（WS）
- **状态同步**：WS 连接表（DE-005，内存）+ session 引用 M-004
- **冲突解决**：max_connections=1000 限流；超限 → E00202 + 指数退避
- **故障恢复**：WS 断连 → 自动重连 + 状态补发（30s 内）
- **资源配额**：0.5 CPU / 512MB / max_connections=1000
- **生命周期**：进程级
- **来源标注**：[TD:IF-008] + [TD:B-007] + [TD:SR-008]

### AG-007 Pipeline 调度 Agent

- **职责边界**：5 阶段管线调度（preprocess→retrieve→rerank→llm→postprocess）；**不负责**单阶段实现
- **输入接口**：`query, query_features, session_id, user_id`
- **输出接口**：`{answer, sources, trace_id, route_decision}`
- **通信协议**：进程内 async 协程 + 状态机（FSM）
- **状态同步**：DE-009 pipeline_state 内存状态机（强一致）
- **冲突解决**：FSM 卡死 → 走 LLM 兜底 10%（DE-023/024 audit_log）
- **故障恢复**：单阶段失败 → 上一阶段缓存结果恢复 / 整体失败 → LLM 兜底
- **资源配额**：0.5 CPU / 512MB / 5 阶段总耗时 ≤10s
- **生命周期**：进程级（FSM 实例按请求级创建）
- **来源标注**：[TD:DE-009] + [TD:ADR-005] + [TD:PC-AITutor:NLI 重检索]

### AG-008 RAG 引擎 Agent

- **职责边界**：RAG 路由 + NLI 评分 + 本地索引 + 翻译管线；**不负责**管线调度
- **输入接口**：`query, query_features, threshold`
- **输出接口**：`{top_k_chunks, nli_score, sources, route_decision}`
- **通信协议**：进程内 async 协程 + ChromaDB REST
- **状态同步**：DE-010 rag_state 内存（round=0..3）
- **冲突解决**：NLI 评分 < 0.7 → 强制重检索 ≤3 轮 → 仍 < 0.7 标"无法确认"+切 web 搜索
- **故障恢复**：NLI 不可用 → 降级 LLM 法官兜底（DE-021 异常）
- **资源配额**：1.0 CPU / 1.5GB（NLI 模型加载）/ 单次 ≤10s
- **生命周期**：进程级（NLI 模型 lazy load 一次）
- **来源标注**：[TD:IF-003] + [TD:ADR-006] + [TD:SR-005] + [调研报告:RI-009/HAL-16/NLI-01/05/13]

### AG-009 教学编排 Agent

- **职责边界**：费曼+FSRS+阶段+休息 总调度；**不负责**单能力实现
- **输入接口**：`{user_id, session_id, action: learn|review|rest}`
- **输出接口**：`{next_step, fsrs_card_update, feynman_question, rest_prompt}`
- **通信协议**：进程内 async 协程 + 状态机
- **状态同步**：DE-009 pipeline_state + DE-019 rest_log
- **冲突解决**：FSM 卡死 → LLM 兜底 10%（E00902）
- **故障恢复**：单能力失败 → 跳过该能力 + audit_log 记录
- **资源配额**：0.5 CPU / 512MB / 单回合 ≤5s
- **生命周期**：进程级
- **来源标注**：[TD:IF-002] + [TD:PC-AITutor:LLM 兜底]

### AG-014 数据管线 Agent

- **职责边界**：pdf2zh 翻译 + clean + chunk(≤2000tok+200overlap) + 入库；**不负责**检索
- **输入接口**：`pdf_path: str` 或 `chunk_text: str`
- **输出接口**：`{doc_id, status: READY|FAILED, chunk_count}`
- **通信协议**：进程内 async + 线程池（pdf2zh 阻塞）
- **状态同步**：DE-025/DE-026 SQLite + ChromaDB
- **冲突解决**：pdf2zh 失败 → pdfplumber → LM Studio 3 次降级（E01401）
- **故障恢复**：clean 后重复率 >30% → 增强 clean + WARN（不阻塞）
- **资源配额**：0.5 CPU / 512MB / 10 页 PDF ≤60s
- **生命周期**：请求级（按 PDF 处理任务创建）
- **来源标注**：[TD:IF-004] + [TD:DE-025/026] + [调研报告:RI-006/PDF-47/03/12]

### AG-015 打包调度 Agent

- **职责边界**：Nuitka onedir 三平台矩阵构建 + UPX 压缩 + sha256 校验；**不负责**开发期 build
- **输入接口**：`{platform, format}`
- **输出接口**：`{artifact_path, size_bytes, sha256, build_log}`
- **通信协议**：进程内 subprocess + CI 集成
- **状态同步**：DE-033/034 artifact 表（SQLite）
- **冲突解决**：体积超目标 → UPX 压缩 + 标 ⚠️（warn only，ADR-009 软约束）
- **故障恢复**：工具链不兼容 → 锁版本回退（E01502）
- **资源配额**：1.0 CPU / 1GB / 单平台 ≤10min
- **生命周期**：任务级（CI 触发或手动触发）
- **来源标注**：[TD:IF-005] + [TD:ADR-009] + [TD:SR-003]

### AG-016 红线编排 Agent（含治理）

- **职责边界**：4 工具链编排 + 6+1 规范矩阵 + CI 阻断 + Error Hub + Redline 闸门；**不负责**业务代码
- **输入接口**：`{tool: RUFF|IMPORT_LINTER|REDOCLY|PRE_COMMIT|PYTEST}`
- **输出接口**：`{exit_code, violation_count, raw_output, fix_url}`
- **通信协议**：进程内 subprocess + GitHub Actions
- **状态同步**：DE-046 redline_report + DE-047 ci_run + DE-048 tool_version_lock
- **冲突解决**：CI 阻断（branch protection） / 修复手册链接
- **故障恢复**：工具链版本破坏 → 锁版本恢复（DE-048）
- **资源配额**：0.3 CPU / 256MB / 4 工具并行 ≤5min
- **生命周期**：进程级
- **来源标注**：[TD:IF-006] + [TD:ADR-010] + [TD:SR-004] + [调研报告:RI-004/REDOC-12/25/30~53]

---

## 三、协作流程图

```
客户端触发 (AG-003)
  ↓
API 网关 (AG-002) [Auth+路由]
  ↓
教学编排 (AG-009) [action=learn|review|rest]
  ├─→ FSRS 调度 (AG-011) → Session (AG-004) → 返回 next_step
  ├─→ 阶段校准 (AG-012) → Session (AG-004) → 返回阶段
  └─→ 费曼评分 (AG-010)
        ↓
Pipeline 调度 (AG-007) [5 阶段]
  ├─→ preprocess
  ├─→ retrieve (AG-008) [路由→NLI→重检索]
  ├─→ rerank
  ├─→ llm (httpx→LLM Provider) [兜底 10%]
  └─→ postprocess
        ↓
数据管线 (AG-014) [可选：PDF 入库]
  ↓
存储 (AG-017) [SQLite+ChromaDB+文件]
  ↓
事件总线 (AG-006) [埋点+Trace+WS 推送]
  ↓
红线编排 (AG-016) [CI 治理]
```

---

## 四、状态同步与冲突解决矩阵

| 状态项 | 存储 | 同步机制 | 冲突解决 | 监控指标 |
|--------|------|---------|---------|---------|
| WS 连接 | 内存 (AG-002) | 事件总线广播 | max=1000 / E00202 | 活跃连接数 / 重连率 |
| Session 状态 | SQLite (AG-004) | async write-through | 版本号 last-write-wins | session 命中率 |
| Cache 命中 | SQLite/Redis (AG-005) | LRU + TTL ±20% | 抖动 TTL 防雪崩 | hit_rate / latency |
| Pipeline FSM | 内存 (AG-007) | 协程局部 | 兜底 10% LLM | p99 响应 / 兜底率 |
| RAG 重检索 | 内存 (AG-008) | 协程局部 | ≤3 轮 → 标"无法确认" | NLI 分数分布 |
| FSRS Again | SQLite (AG-011) | 节流 5min/卡 | 计数+拒绝 | Again 频率 |
| 阶段档位 | SQLite (AG-012) | 7 天窗口 | 升/降各 2 天 hysteresis | 档位稳定率 |
| 长期记忆 | SQLite (AG-013) | LRU 淘汰最旧 10% | 重要性评分 V4.5 | 实体数 / 命中率 |
| artifact | SQLite (AG-015) | sha256 强校验 | 体积 warn | 3 平台体积 |
| Redline | SQLite (AG-016) | CI 锁版本 | branch protection 阻断 | 命中率 / 失败率 |

来源标注：[TD:DE-001~048] + [TD:SR-001~012]

---

## 五、协作闭环检测（4.15 灵魂要求）

| 检测项 | 状态 | 措施 |
|--------|------|------|
| 死锁检测 | 通过 | 模块依赖图无环（D3=100%）；所有协程超时 30s |
| 活锁检测 | 通过 | 重检索 ≤3 轮 / Again 节流 5min / 阶段 hysteresis 2 天 |
| 超时机制 | 通过 | 5MW 启动 ≤30s / 学习回合 ≤5s / RAG 单次 ≤10s / PDF ≤60s / 打包 ≤10min / CI ≤5min |
| 降级策略 | 通过 | Redis→SQLite / NLI→LLM / pdf2zh→pdfplumber→LM Studio / FSM→LLM 10% |
| 状态一致性 | 通过 | SQLite WAL + 强一致；FSM 内存强一致；Cache 最终一致 |
| TraceID 串联 | 通过 | trace_id 32hex 全埋点（M-006）→ 跨 Agent 调用链可追踪 |
| 互认证 | 通过 | WS token / LLM API key / Agent 间 Depends() 注入校验 |
| 最小权限 | 通过 | AG-018 Prom 仅 scrape 公开指标；M-017 存储仅 AG-004/005/007/008/009/013 写 |

**协作闭环检测：8/8 通过**

---

## 六、故障恢复策略

| 故障场景 | 检测方式 | 恢复策略 | 责任 Agent |
|---------|---------|---------|----------|
| 进程崩溃 | systemd / Uvicorn supervisor | 自动重启 + 启动期 validate | AG-001 |
| 5MW 启动失败 | E00101~E00106 错误码 | 详细日志 + 启动拒绝 | AG-001 |
| WS 断连 | CE-016 风暴检测 | 指数退避 ≤30s + 状态补发 | AG-002 |
| Redis 不可用 | EX-005 | 降级 SQLite + WARN | AG-005 |
| NLI 模型加载失败 | EX-015 | 降级 LLM 法官 + trace_id | AG-008 |
| LLM Provider 超时 | httpx Timeout 30s | LLM 兜底 10% 仍失败 → 标"无法确认" | AG-007 |
| pdf2zh 失败 | E01401 | pdfplumber → LM Studio 3 次降级 | AG-014 |
| FSM 卡死 | EX-017 | 走 LLM 兜底 10% | AG-007/AG-009 |
| 红线工具破坏 | EX-033 | 锁版本恢复 | AG-016 |
| 4 工具链 CI 红 | E01601 | 修复手册 + 本地 pre-commit 先跑 | AG-016 |

---

## 七、AR 洞察

- **INSIGHT-AR-001 NLI 资源抢占风险**：AG-008 的 NLI 模型加载（1.5GB）若与 AG-014 的 PDF 翻译（512MB）在同一 CPU 池中并发，单机 CPU 4 核下可能争抢。**缓解**：M-001 启动期绑定 NLI 到固定 CPU 亲和性（CPU 0），PDF 翻译走 ThreadPool 走 CPU 1-3。
- **INSIGHT-AR-002 M-016 治理工具链依赖外网**：pre-commit hooks 拉取远端配置时若断网会失败。**缓解**：本地缓存 `.pre-commit-cache/` + CI 加 `--no-network` 模式。
- **INSIGHT-AR-003 AG-013 长期记忆 LRU 淘汰与用户期望冲突**：M-013 LRU 淘汰最旧 10% 可能误删重要事实。**缓解**：V4.5 引入"重要性评分"（重要性 × 时间衰减），本次 V3.1 接受此债务。
