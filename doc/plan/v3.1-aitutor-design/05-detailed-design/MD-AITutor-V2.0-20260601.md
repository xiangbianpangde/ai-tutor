# 模块细化方案 — AITutor V2.0

> 角色：DD-001 | 日期：2026-06-01 | 上游：[AR:TA] 10 模块 | 下游：DD-M 按 M-NNN 分工

---

## MD-001 启动与中间件装配（M-001）

**关联技术选型**：TS-001 Python 3.11 / TS-002 FastAPI 0.115 / TS-003 uvicorn / TS-004 Pydantic 2.9 / TS-019 structlog / TS-020 OTel

### 子模块拆分
- `bootstrap.config_loader`：加载 .env 与 pyproject 配置
- `bootstrap.middleware_chain`：注册 Session/Cache/Monitor/Pipeline/RAG 5 类中间件
- `bootstrap.health`：暴露 /health 与 OpenAPI
- `bootstrap.ws_server`：启动 WebSocket 服务（M-009 调用）

### 类设计
- `AppConfig`（Pydantic BaseSettings）— 配置聚合根
- `MiddlewareRegistry` — 中间件注册表（链式）
- `BootstrapService` — 启动协调器
- `HealthChecker` — 健康检查聚合
- `StartupProbe` — 启动前就绪检查（端口/DB/凭证）

### 函数签名
- `load_config(env_path: str) -> AppConfig`
- `register_middlewares(app: FastAPI, registry: MiddlewareRegistry) -> None`
- `check_db_compatible(db_path: str) -> bool`  → 抛 `DBIncompatibleError`
- `start_ws_server(host: str, port: int) -> None`  → 抛 `PortInUseError` (EX-002)
- `ping_health() -> HealthReport`

### 状态机
`UNINIT → LOAD_CONFIG → CHECK_DB → REGISTER_MW → START_WS → READY → DEGRADED → STOPPED`

### 异常处理
- `PortInUseError`：EX-002 端口冲突递增重试 3 次
- `DBIncompatibleError`：EX-001 启动阻断 + 自动迁移尝试
- `MiddlewareRegisterError`：标记降级状态（DE-004）继续启动

### 日志策略
- 级别：INFO（启动阶段）/ ERROR（异常）/ DEBUG（配置详情）
- 内容：阶段名 + trace_id + 耗时
- 格式：structlog JSONL `[bootstrap] stage=register_mw trace_id=... duration_ms=...`

### 测试策略
- 范围：单元测试 + 集成测试
- 用例数：核心 6 + 边界 4 + 异常 5
- Mock：os.environ / aiosqlite
- 覆盖率：行 ≥85% / 分支 ≥75%
- 测试数据：临时 .env 文件

### 来源标注
[AR:TA-§二 L1/M-001] + [AR:BR-003/BR-008] + [AR:AC-AG-001]

---

## MD-002 教学引擎（M-002）

**关联技术选型**：TS-008 py-fsrs 0.16 / TS-009 langchain-core 0.3

### 子模块拆分
- `pedagogy.feynman`（费曼学习法评分）
- `pedagogy.fsrs`（FSRS 调度）
- `pedagogy.stage`（学习阶段判定）
- `pedagogy.break_check`（休息提醒）
- `pedagogy.recall`（复述）

### 类设计
- `PedagogyOrchestrator`（门面）— 调度 5 策略
- `FeynmanScorer`（Strategy）— 评分执行
- `FSRSScheduler`（Strategy）— py-fsrs 包装
- `StageAssessor`（Strategy）— 阶段判定
- `BreakAdvisor`（Strategy）— 休息建议
- `LearnerProfile`（实体）— 学习者档案

### 函数签名
- `score_feynman(answer: str, question_id: str) -> FeynmanReport`
- `schedule_card(card_id: str, grade: int) -> FSRSSchedule`  → 抛 `AGAINStormError`
- `assess_stage(profile: LearnerProfile) -> Stage`
- `recommend_break(elapsed_min: int) -> BreakAdvice`

### 状态机
`BEGINNER → INTERMEDIATE → ADVANCED → MASTER`（按 7 天正确率 hysteresis 切换，BR-014）
`FeynmanState: ATTEMPT → SCORED → PASSED/RETRY`
`FSRSState: NEW → LEARNING → REVIEW → RELEARNING`

### 异常处理
- `AGAINStormError`：EX-008 5min/卡 1 次（ADR-006）
- `LLMScoreError`：EX-009 10% 兜底
- `FSRSAlgorithmError`：维持原档位 + WARN 日志

### 日志策略
- 级别：INFO（调度）/ WARN（风暴/降级）/ ERROR（异常）
- 内容：strategy 名 + user_id + 输入摘要 + 结果
- 格式：structlog `[pedagogy] strategy=fsrs user_id=u1 grade=1 retry_after=...`

### 测试策略
- 范围：单元测试 + 集成测试 + 端到端测试（5 策略串联）
- 用例数：核心 15 + 边界 8 + 异常 6
- Mock：M-007 LLM Provider / py-fsrs.Card
- 覆盖率：行 ≥85% / 分支 ≥75%
- 测试数据：固定 LearnerProfile fixture

### 来源标注
[AR:TA-§二 L3/M-002] + [AR:BR-011~BR-015] + [AR:AC-AG-002] + [调研报告:RI-002]

---

## MD-003 抗幻觉网关（M-003）

**关联技术选型**：TS-011 transformers 4.45 / TS-012 DeBERTa-v3-large-mnli / TS-013 optimum+onnxruntime

### 子模块拆分
- `halugate.nli_layer`（NLI 模型推理，CPU/ONNX）
- `halugate.slm_layer`（本地小模型，二级）
- `halugate.llm_judge`（异构 LLM 法官，三级）
- `halugate.cascade`（三级级联编排）

### 类设计
- `HaluGateOrchestrator`（门面）— 串联 3 级
- `NLILayer`（Chain Handler）— DeBERTa 推理
- `SLMLayer`（Chain Handler）— 本地小模型
- `LLMJudgeLayer`（Chain Handler）— LLM 调用
- `ClaimExtractor`（M-005 调用辅助）

### 函数签名
- `verify(claims: list[Claim], response_text: str) -> HaluReport`  → 抛 `AllJudgesFailedError`
- `extract_claims(text: str) -> list[Claim]`
- `warmup_nli() -> None`（启动预热，AR-洞察-001）
- `set_gpu_enabled(flag: bool) -> None`（V-1 路由）

### 状态机
`IDLE → NLI_RUNNING → NLI_PASSED/NLI_FAILED → SLM_RUNNING → LLM_RUNNING → VERDICT`
Circuit Breaker 状态：`CLOSED → OPEN → HALF_OPEN → CLOSED`

### 异常处理
- `AllJudgesFailedError`：EX-016 阻断回答，返回"无法验证"
- `NLILoadError`：跳过 NLI 直接走 SLM
- `LLMJudgeTimeout`：30s 超时 + 1 次重试

### 日志策略
- 级别：INFO（每级裁决结果）/ WARN（降级路径）/ ERROR（全部失败）
- 内容：claim_id + 各层 score + final verdict + trace_id
- 格式：structlog `[halugate] claim_id=c1 nli=0.92 slm=0.88 llm=0.95 final=PASSED trace_id=...`

### 测试策略
- 范围：单元测试 + 集成测试 + 离线评测
- 用例数：核心 12 + 边界 6 + 异常 8
- Mock：DeBERTa 模型输出 / LLM Provider
- 覆盖率：行 ≥85% / 分支 ≥75%
- 测试数据：HaluEval 子集 200 条 + 自建 50 条

### 来源标注
[AR:TA-§二 L3/M-003] + [AR:BR-016~BR-019] + [AR:AC-AG-003] + [调研报告:NLI-01/05/13] + [AR洞察-001] + [ADR-003]

---

## MD-004 数据管线（M-004）

**关联技术选型**：TS-017 pdf2zh / TS-018 research-tool

### 子模块拆分
- `pipeline.collect`（采集）
- `pipeline.clean`（清洗）
- `pipeline.ingest`（入库）
- `pipeline.chunk`（分块）
- `pipeline.govern`（治理/去重）

### 类设计
- `DataPipeline`（门面）
- `SourceAdapter`（Strategy × 10 源）
- `DocumentCleaner`（Pipeline step）
- `DocumentRepository`（Repository 模式）
- `PipelineTask`（实体）— 任务状态

### 函数签名
- `start_ingest(source: str, path: str, options: dict) -> TaskId`
- `get_task_status(task_id: str) -> TaskStatus`
- `cancel_task(task_id: str) -> bool`
- `retry_failed_step(task_id: str, step: str) -> bool`

### 状态机
`PENDING → COLLECTING → CLEANING → INGESTING → CHUNKING → GOVERNING → COMPLETED`
`PENDING → FAILED (with retry) → COMPLETED/DEAD_LETTER`

### 异常处理
- `SourceUnreachableError`：EX-027 跳过该源继续
- `LLMExtractError`：EX-023 退化为关键词匹配
- `PDFTranslateError`：EX-028 3 次降级 LM Studio
- `ContentHashConflict`：ADR-010 UPSERT 幂等

### 日志策略
- 级别：INFO（步进）/ WARN（降级/跳过）/ ERROR（最终失败）
- 内容：task_id + step + source + progress
- 格式：structlog `[pipeline] task_id=t1 step=cleaning source=arxiv progress=0.65`

### 测试策略
- 范围：单元测试 + 集成测试（真实 PDF）+ 离线评测
- 用例数：核心 18 + 边界 10 + 异常 8
- Mock：research-tool 子包
- 覆盖率：行 ≥80% / 分支 ≥70%
- 测试数据：固定 PDF/MD 样本 20 个

### 来源标注
[AR:TA-§二 L2/M-004] + [AR:BR-023~BR-026] + [AR:AC-AG-004] + [调研报告:RI-005/RI-006/S-008] + [ADR-010]

---

## MD-005 RAG 检索与生成（M-005）

**关联技术选型**：TS-006 sqlite-vec / TS-009 langchain-core / TS-010 langgraph 1.0

### 子模块拆分
- `rag.preprocess`（查询规范化）
- `rag.retrieve`（向量检索）
- `rag.rerank`（cross-encoder 重排）
- `rag.llm_generate`（LLM 生成）
- `rag.postprocess`（抗幻觉后处理 + source 附加）

### 类设计
- `RAGStateGraph`（LangGraph StateGraph）
- `VectorIndex`（Protocol 抽象层，封装 sqlite-vec，DD-洞察-004）
- `CrossEncoderReranker`
- `RAGCache`（Cache-Aside 模式）
- `RAGContext`（实体）— 检索上下文

### 函数签名
- `query(question: str, session_id: str, options: dict) -> RAGAnswer`  → 抛 `MaxRoundsExceeded`
- `get_eval(ctx_id: str) -> EvalReport`
- `warmup_index() -> None`（启动预热）

### 状态机（LangGraph StateGraph）
`START → preprocess → retrieve → rerank → llm_generate → postprocess → END`
`postprocess` 失败 → 触发 `retrieve` 重试（max_total_rounds=5，ADR-005）

### 异常处理
- `MaxRoundsExceeded`：EX-031 返回"已尽力"（≤5 轮）
- `AllLLMFailed`：EX-009 10% 兜底
- `CacheMiss`：EX-005 SQLite LRU 降级

### 日志策略
- 级别：INFO（节点完成）/ WARN（重试）/ ERROR（超限/失败）
- 内容：节点名 + round + ctx_id + trace_id
- 格式：structlog `[rag] node=rerank round=2 ctx_id=c1 trace_id=...`

### 测试策略
- 范围：单元测试 + 集成测试 + 端到端 RAG
- 用例数：核心 20 + 边界 10 + 异常 8
- Mock：sqlite-vec / LLM Provider
- 覆盖率：行 ≥85% / 分支 ≥75%
- 测试数据：固定文档集 100 段

### 来源标注
[AR:TA-§二 L4/M-005] + [AR:BR-019/BR-029/BR-032] + [AR:AC-AG-005] + [调研报告:RI-002/RI-007] + [ADR-005] + [AR洞察-004/007]

---

## MD-006 会话与长期记忆（M-006）

**关联技术选型**：TS-006 sqlite-vec / TS-009 langchain-core / TS-010 langgraph-store

### 子模块拆分
- `session.manager`（CRUD 会话）
- `session.switcher`（会话切换）
- `memory.short_term`（ConversationSummaryBufferMemory）
- `memory.long_term`（LangGraph Store + sqlite-vec）

### 类设计
- `SessionManager`（Repository）
- `Session`（实体）
- `ShortTermMemory`
- `LongTermMemory`（Repository + VectorIndex）
- `MemoryExporter`

### 函数签名
- `list_sessions() -> list[Session]`
- `switch_session(session_id: str) -> bool`
- `get_long_term_facts(user_id: str) -> list[Fact]`
- `export_session(session_id: str) -> ExportPath`  → 抛 `CorruptedJSONError` (EX-036)

### 状态机
`Session: ACTIVE → ARCHIVED → DELETED`
`Memory: SHORT_TERM → SUMMARIZED → LONG_TERM`

### 异常处理
- `CorruptedJSONError`：EX-036 NDJSON 回退
- `UserIDMismatchError`：CE-012 user_id 强校验
- `SessionNotFound`：404

### 日志策略
- 级别：INFO（CRUD）/ WARN（回退降级）/ ERROR（损坏）
- 内容：session_id + user_id + 操作
- 格式：structlog `[memory] op=export session_id=s1 user_id=u1`

### 测试策略
- 范围：单元测试 + 集成测试
- 用例数：核心 12 + 边界 6 + 异常 5
- Mock：LangGraph Store
- 覆盖率：行 ≥85% / 分支 ≥75%
- 测试数据：固定 5 会话 fixture

### 来源标注
[AR:TA-§二 L3/M-006] + [AR:DE-033~DE-036] + [AR:CE-012] + [调研报告:MEM-48/05]

---

## MD-007 集成适配器（M-007）

**关联技术选型**：TS-014 OpenAI / TS-015 Anthropic / TS-016 Ollama / TS-017 pdf2zh / TS-018 research-tool

### 子模块拆分
- `llm.openai_adapter`
- `llm.anthropic_adapter`
- `llm.ollama_adapter`
- `llm.token_bucket`（限流）
- `research.adapter`（research-tool 封装）
- `pdf.adapter`（pdf2zh CLI 包装）

### 类设计
- `LLMProvider`（Protocol 抽象）
- `OpenAIProvider`（Adapter）
- `AnthropicProvider`（Adapter）
- `OllamaProvider`（Adapter）
- `TokenBucketLimiter`
- `ResearchAdapter`
- `PDFTranslateAdapter`

### 函数签名
- `infer(prompt: str, model: str, options: dict) -> LLMResult`  → 抛 `AllProviderFailedError`
- `translate_pdf(file_path: str, target_lang: str) -> TranslateResult`
- `research_collect(subcommand: str, args: dict) -> ResearchResult`
- `get_provider_health(provider: str) -> HealthStatus`

### 状态机
`Provider: AVAILABLE → DEGRADED → UNAVAILABLE → RECOVERING → AVAILABLE`
（基于连续失败次数与最近成功时间）

### 异常处理
- `AllProviderFailedError`：EX-009 阻断回答
- `ProviderRateLimit`：EX-009 Token Bucket 拒绝
- `PDFTranslateTimeout`：60s/10 页 + 3 次降级
- `APIKeyMissing`：E002 401 阻断

### 日志策略
- 级别：INFO（成功）/ WARN（限流/降级）/ ERROR（失败）
- 内容：provider + model + token 数 + 延迟 + trace_id
- 格式：structlog `[llm] provider=anthropic model=haiku4.5 tokens=256 latency_ms=1830 trace_id=...`

### 测试策略
- 范围：单元测试 + 集成测试（含真实 API 离线录制）
- 用例数：核心 15 + 边界 8 + 异常 10
- Mock：OpenAI/Anthropic SDK
- 覆盖率：行 ≥85% / 分支 ≥75%
- 测试数据：VCR.py 录制 50 段

### 来源标注
[AR:TA-§二 L1/M-007] + [AR:BR-027/BR-028/BR-035] + [AR:AC-AG-007] + [调研报告:RI-007] + [AR洞察-005/008/009]

---

## MD-008 流程状态机（M-008）

**关联技术选型**：TS-010 langgraph / TS-019 structlog

### 子模块拆分
- `fsm.table_loader`（加载状态机表）
- `fsm.matcher`（匹配器）
- `fsm.observer`（变更广播）
- `fsm.audit`（审计写入）
- `fsm.llm_fallback`（10% LLM 兜底）

### 类设计
- `StateMachine`（Finite State Machine）
- `TransitionTable`（dataclass）
- `FSMObservers`（Observer 列表）
- `AuditLogger`（强制写，BR-021）
- `LLMFallbackOrchestrator`（10% 兜底）

### 函数签名
- `match(input: dict, context: dict) -> MatchResult`
- `fallback(input: dict, llm_response: dict) -> StateChange`  → 抛 `AuditWriteFailedError`
- `get_proposals() -> list[Proposal]`
- `load_table(version: str) -> bool`  → 抛 `VersionMismatchError`

### 状态机
`FsmState: BOOTING → READY → MATCHING → FALLBACK → MATCHING → READY`
`AuditState: WRITING → COMMITTED / FAILED_BLOCK`

### 异常处理
- `AuditWriteFailedError`：BR-021 阻断兜底不执行
- `VersionMismatchError`：CE-007 强制升级
- `NoTransitionFound`：调用 LLM 兜底（10%）

### 日志策略
- 级别：INFO（每次匹配）/ WARN（兜底触发）/ ERROR（审计失败）
- 内容：state_from + state_to + input_hash + version + trace_id
- 格式：structlog `[fsm] from=ATTEMPT to=SCORED version=v1.2 trace_id=...`

### 测试策略
- 范围：单元测试 + 集成测试 + 状态机路径覆盖
- 用例数：核心 14 + 边界 8 + 异常 6
- Mock：LLM Provider
- 覆盖率：行 ≥90% / 分支 ≥85%（状态机要求高）
- 测试数据：固定 TransitionTable fixture

### 来源标注
[AR:TA-§二 L3/M-008] + [AR:BR-020~BR-022] + [AR:AC-AG-008] + [AR洞察-003] + [ADR-003/008]

---

## MD-009 状态推送（M-009）

**关联技术选型**：TS-002 FastAPI WebSocket / TS-019 structlog / TS-020 OTel

### 子模块拆分
- `ws.server`（WebSocket 服务）
- `ws.heartbeat`（心跳）
- `ws.event_bus`（事件总线）
- `ws.broadcaster`（推送器）
- `status.md_writer`（STATUS.md 原子写）

### 类设计
- `WSConnectionManager`（连接池管理）
- `HeartbeatScheduler`（30s ping/pong）
- `EventBus`（内存发布订阅）
- `Broadcaster`（Observer 模式）
- `StatusMDWriter`（aiofiles 原子写）

### 函数签名
- `connect(ws: WebSocket, token: str) -> bool`  → 抛 `CSWSHRejected`
- `disconnect(ws: WebSocket) -> None`
- `broadcast(event: StatusEvent) -> None`
- `write_status_md(markdown: str) -> bool`  → 抛 `AtomicWriteFailed`
- `heartbeat() -> None`

### 状态机
`Connection: CONNECTING → AUTHENTICATING → OPEN → CLOSING → CLOSED`
`Heartbeat: PING_SENT → PONG_RECEIVED / TIMEOUT → PING_SENT (exponential backoff)`

### 异常处理
- `CSWSHRejected`：EX-024 跨站劫持拒绝
- `HeartbeatTimeout`：EX-025 指数退避关闭
- `AtomicWriteFailed`：EX-040 写失败阻断推送
- `MessageTooLarge`：>64KB 拒绝

### 日志策略
- 级别：INFO（连接/断开）/ WARN（心跳超时）/ ERROR（推送失败）
- 内容：client_id + event_type + 延迟
- 格式：structlog `[ws] event=state_change client_id=w1 latency_ms=...`

### 测试策略
- 范围：单元测试 + 集成测试 + 端到端 WS 客户端测试
- 用例数：核心 10 + 边界 8 + 异常 6
- Mock：WebSocket 客户端
- 覆盖率：行 ≥85% / 分支 ≥75%
- 测试数据：固定事件序列 fixture

### 来源标注
[AR:TA-§二 L1/M-009] + [AR:BR-005] + [AR:DE-040] + [AR:AC-AG-009] + [AR洞察-002] + [调研报告:RI-007]

---

## MD-010 扩展生态（M-010）

**关联技术选型**：TS-021 genanki 0.13

### 子模块拆分
- `extension.anki`（Anki .apkg 生成）
- `extension.obsidian`（Obsidian vault 同步）
- `extension.plugin`（CLI 插件加载）
- `extension.registry`（插件注册表）

### 类设计
- `AnkiExporter`（Adapter）
- `ObsidianSyncer`（Adapter，git CLI 包装）
- `PluginLoader`（entry_point 加载）
- `PluginRegistry`（Repository）
- `ExtensionOrchestrator`（门面）

### 函数签名
- `generate_apkg(session_id: str, options: dict) -> ApkgPath`  → 抛 `AnkiConnectUnavailable`
- `sync_obsidian(vault_path: str) -> CommitId`
- `install_plugin(name: str) -> bool`  → 抛 `PluginSignatureInvalid`
- `list_plugins() -> list[Plugin]`

### 状态机
`Plugin: DISCOVERED → INSTALLED → ENABLED → DISABLED → UNINSTALLED`
`Anki: NOT_STARTED → GENERATING → WRITTEN → CONNECTED/FAILED`

### 异常处理
- `AnkiConnectUnavailable`：EX-042 仅生成 .apkg 不推送
- `PluginSignatureInvalid`：跳过 + WARN（V-4 签名校验）
- `GitCommitFailed`：每日 ≤1 commit 节流

### 日志策略
- 级别：INFO（生成/同步）/ WARN（降级）/ ERROR（失败）
- 内容：plugin_name + 操作 + 结果
- 格式：structlog `[extension] op=anki_generate session_id=s1 result=ok`

### 测试策略
- 范围：单元测试 + 集成测试
- 用例数：核心 8 + 边界 5 + 异常 4
- Mock：genanki / git CLI
- 覆盖率：行 ≥80% / 分支 ≥70%
- 测试数据：固定 session fixture

### 来源标注
[AR:TA-§二 L1/M-010] + [AR:DE-042~DE-045] + [调研报告:RI-011/RI-012] + [调研报告:ANK-19]
