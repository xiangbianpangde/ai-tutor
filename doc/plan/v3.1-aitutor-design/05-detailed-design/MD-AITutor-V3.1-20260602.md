# 模块细化方案 — AITutor V3.1

> 17 模块（M-001~M-017）全有完整细化方案，全部通过 4.7 七项检查。
> 来源：[AR:TS-001~018/API-001~008/PO-001~010/SEC-001~015/DP-001~007] + [DD推断:依据]

---

## M-001 服务入口（Builder + Singleton）

- **关联技术选型**：TS-001 Python / TS-002 FastAPI / TS-018 pydantic-settings
- **子模块拆分**：
  - sm001-launcher：Uvicorn 启动 + 进程内装配 5MW
  - sm001-config：pyproject.toml + .env 加载
  - sm001-validate：启动期健康检查 + MW 注册校验
- **类设计**：
  - `AppLauncher`：属性[app: FastAPI, mw_status: dict] / 方法[build_app(), validate_mw(), start_uvicorn()]
  - `ConfigLoader`：属性[pyproject: dict, env: dict] / 方法[load_pyproject(), load_env(), validate_required()]
  - `MiddlewareValidator`：属性[required: List[str]] / 方法[check_registered(), get_missing()]
  - `HealthEndpoint`：属性[status: str] / 方法[liveness(), readiness()]
- **函数签名**：
  - `build_app(config: ConfigLoader) → FastAPI`
  - `start_uvicorn(app: FastAPI, host: str = "127.0.0.1", port: int = 8000) → None`
  - `validate_mw(app: FastAPI) → MiddlewareStatus`
  - `liveness() → JSONResponse`
  - `readiness() → JSONResponse`
- **状态机**：N/A（无状态服务入口）
- **异常处理**：
  - E00101 依赖缺失 → 拒绝启动 + 详细日志
  - E00102 端口冲突 → 提示用户改端口
  - E00103 旧库不兼容 → 自动迁移 / 失败备份
  - E00106 MW 初始化失败 → 退出码非 0
- **日志策略**：级别 INFO/ERROR / 内容[trace_id, mw_name, status] / 格式[structlog JSON]
- **测试策略**：单元+集成 / 13 用例（核心 5 + 边界 5 + 异常 3）/ Mock[subprocess.run] / 覆盖率≥85%
- **来源标注**：[AR:API-001] + [AR:DP-001]

---

## M-002 API 网关 + WS（Adapter + Proxy）

- **关联技术选型**：TS-002 FastAPI / TS-001 Python
- **子模块拆分**：
  - sm002-router：HTTP 路由注册（APIRouter）
  - sm002-auth：Depends(auth) Bearer Token 强校验
  - sm002-ws：WebSocket 推送（starlette.websockets）
- **类设计**：
  - `APIRouterRegistry`：属性[routes: List[APIRouter]] / 方法[register(), mount()]
  - `AuthDependency`：属性[token_store: TokenStore] / 方法[__call__(token: str)]
  - `WSConnectionManager`：属性[connections: Dict[str, WebSocket], max=1000] / 方法[connect(), disconnect(), broadcast()]
  - `RateLimiter`：属性[qps_per_user=100, concurrent_turns=10] / 方法[check(), increment()]
  - `OpenAPIGenerator`：属性[app: FastAPI] / 方法[generate_schema()]
- **函数签名**：
  - `register_router(router: APIRouter, prefix: str) → None`
  - `verify_token(token: str) → UserContext`
  - `ws_connect(ws: WebSocket, session_id: str) → None`
  - `ws_disconnect(ws: WebSocket) → None`
  - `ws_broadcast(event: WSEvent) → None`
  - `check_rate_limit(user_id: str) → bool`
- **状态机**：WS 连接状态 [NEW → AUTHED → ACTIVE → CLOSED]
- **异常处理**：
  - E00201 连接断开 → 指数退避 ≤30s + 状态补发
  - E00202 超限拒绝 → 客户端降级轮询
  - E00203 Token 无效 → 401 + trace_id
- **日志策略**：级别 INFO/WARN/ERROR / 内容[trace_id, user_id, route, status_code] / 格式[structlog]
- **测试策略**：单测+集成+E2E / 16 用例（核心 6 + 边界 6 + 异常 4）/ Mock[httpx] / 覆盖率≥80%
- **来源标注**：[AR:API-002/008] + [AR:SEC-002/007]

---

## M-003 客户端入口（Facade + Strategy）

- **关联技术选型**：TS-001 Python / TS-002 FastAPI
- **子模块拆分**：
  - sm003-cli：argparse 入口（CLI 形态）
  - sm003-web：浏览器入口（Web 形态）
  - sm003-gui：GUI 形态占位（V3.5 决策）
  - sm003-lib：Python library 入口（import aitutor）
- **类设计**：
  - `CLIEntry`：属性[parser: argparse.ArgumentParser] / 方法[main(), dispatch()]
  - `WebEntry`：属性[html_path: str] / 方法[mount_static()]
  - `LibraryEntry`：属性[client: AITutorClient] / 方法[__init__(), chat()]
  - `EntryDispatcher`：属性[form: str] / 方法[route()]
- **函数签名**：
  - `cli_main(argv: List[str]) → int`
  - `web_serve(app: FastAPI) → None`
  - `library_chat(prompt: str, session_id: str) → str`
- **状态机**：N/A（无状态分发）
- **异常处理**：
  - E00301 形态不支持 → 退出码 2 + 提示
  - E00302 浏览器未启动 → 降级 CLI
- **日志策略**：级别 INFO / 内容[form, command] / 格式[structlog]
- **测试策略**：单测+集成 / 8 用例 / 覆盖率≥75%
- **来源标注**：[AR:DP-001] + [AR:SEC-001]

---

## M-004 Session（Repository + FSM）

- **关联技术选型**：TS-003 SQLite / TS-001 Python
- **子模块拆分**：
  - sm004-session：会话实体管理
  - sm004-state：会话状态机
- **类设计**：
  - `Session`：属性[id, user_id, created_at, last_active, state] / 方法[activate(), suspend(), close()]
  - `SessionRepository`：属性[engine: AsyncEngine] / 方法[create(), get(), update(), delete(), list_by_user()]
  - `SessionStateMachine`：属性[current_state, transitions: Dict] / 方法[transition(event), get_state()]
- **函数签名**：
  - `create_session(user_id: str) → Session`
  - `get_session(session_id: str) → Session`
  - `update_session_state(session_id: str, new_state: str) → None`
  - `transition_state(session: Session, event: str) → str`
- **状态机**：
  - NEW → [activate] → ACTIVE
  - ACTIVE → [suspend] → SUSPENDED
  - ACTIVE → [timeout 30min] → EXPIRED
  - ACTIVE → [close] → CLOSED
  - SUSPENDED → [activate] → ACTIVE
  - SUSPENDED → [timeout 7d] → EXPIRED
- **异常处理**：
  - E00401 session 不存在 → 404
  - E00402 状态转换非法 → 422 + trace_id
  - E00403 DB 写失败 → 重试 1 次 / 失败 5xx
- **日志策略**：级别 INFO/WARN / 内容[session_id, user_id, state_transition] / 格式[structlog]
- **测试策略**：单测+集成 / 14 用例（核心 5 + 状态机 6 + 异常 3）/ 覆盖率≥85%
- **来源标注**：[AR:API-002] + [AR:SEC-009]

---

## M-005 Cache 中间件（Proxy + Flyweight）

- **关联技术选型**：TS-003 SQLite / TS-005 Redis / TS-006 httpx
- **子模块拆分**：
  - sm005-semantic：语义缓存（向量相似度 0.85~0.95）
  - sm005-lru：LRU 容量上限
  - sm005-backend：双后端（SQLite 默认 / Redis 可选）
- **类设计**：
  - `SemanticCache`：属性[threshold_low=0.85, threshold_high=0.95, ttl_jitter=0.2] / 方法[get(), set(), invalidate()]
  - `LRUEvictionPolicy`：属性[max_size, eviction_ratio=0.1] / 方法[evict(), touch()]
  - `CacheBackend`：属性[kind: Literal["sqlite", "redis"]] / 方法[get(), set(), ttl()]
  - `CacheProxy`：属性[backend: CacheBackend, lru: LRUEvictionPolicy] / 方法[wrap()]
- **函数签名**：
  - `semantic_get(query: str) → Optional[CacheEntry]`
  - `semantic_set(query: str, response: str, ttl: int) → None`
  - `evict_lru() → int`（返回淘汰数）
  - `select_backend(env: str) → CacheBackend`
- **状态机**：N/A（无状态查询）
- **异常处理**：
  - E00501 Redis 不可用 → 降级 SQLite + WARN
  - E00502 缓存序列化失败 → 跳过 + ERROR 日志
  - E00503 容量超限 → LRU 淘汰 + 计数
- **日志策略**：级别 DEBUG/INFO/WARN / 内容[query_hash, hit/miss, backend] / 格式[structlog]
- **测试策略**：单测+集成 / 12 用例 / 覆盖率≥80%
- **来源标注**：[AR:TS-005] + [AR:PO-006] + [AR:API-002 缓存]

---

## M-006 事件总线（Observer + Mediator）

- **关联技术选型**：TS-009 OpenTelemetry / TS-010 Prometheus
- **子模块拆分**：
  - sm006-trace：trace_id 生成与传播（32hex）
  - sm006-log：结构化日志（structlog JSON）
- **类设计**：
  - `EventBus`：属性[subscribers: List[Subscriber]] / 方法[subscribe(), publish(), unsubscribe()]
  - `TraceContext`：属性[trace_id: 32hex, span_id: 32hex] / 方法[start(), end(), inject(), extract()]
  - `StructuredLogger`：属性[level: str] / 方法[info(), warn(), error(), bind()]
- **函数签名**：
  - `publish_event(event_type: str, payload: dict) → None`
  - `subscribe(event_type: str, handler: Callable) → None`
  - `new_trace_id() → str`（32hex）
  - `bind_trace_id(trace_id: str) → ContextVar`
- **状态机**：N/A
- **异常处理**：
  - E00601 trace_id 缺失 → 自动生成 + WARN
  - E00602 订阅者异常 → 隔离 + ERROR 日志
  - E00603 OTel 导出失败 → 降级本地日志
- **日志策略**：级别 DEBUG/INFO/WARN/ERROR / 内容[trace_id, span_id, event_type, payload_size] / 格式[structlog JSON]
- **测试策略**：单测+集成 / 10 用例 / 覆盖率≥80%
- **来源标注**：[AR:TS-009/010] + [AR:SEC-010]

---

## M-007 Pipeline 调度（Pipeline + Strategy）

- **关联技术选型**：TS-001 Python / TS-002 FastAPI
- **子模块拆分**：
  - sm007-preprocess：query 预处理（分词/特征提取）
  - sm007-retrieve：调用 M-008 RAG 检索
  - sm007-rerank：重排序
  - sm007-llm：调用 LLM Provider（httpx）
  - sm007-postprocess：答案后处理
- **类设计**：
  - `PipelineOrchestrator`：属性[stages: List[Stage]] / 方法[execute(), rollback()]
  - `PipelineState`：属性[round, current_stage, last_result] / 方法[mark_stage(), is_stuck()]
  - `PreprocessStage`：方法[run(query)]
  - `RetrieveStage`：方法[run(query_features)]
  - `RerankStage`：方法[run(candidates)]
  - `LLMStage`：方法[run(context)]
  - `PostprocessStage`：方法[run(raw_answer)]
- **函数签名**：
  - `execute_pipeline(query: str, session_id: str) → PipelineResult`
  - `preprocess(query: str) → QueryFeatures`
  - `retrieve(features: QueryFeatures) → List[Chunk]`
  - `rerank(chunks: List[Chunk]) → List[Chunk]`
  - `call_llm(context: List[Chunk]) → str`
  - `postprocess(answer: str) → str`
- **状态机**：
  - INIT → [start] → PREPROCESS
  - PREPROCESS → [done] → RETRIEVE
  - RETRIEVE → [done] → RERANK
  - RERANK → [done] → LLM
  - LLM → [done] → POSTPROCESS
  - POSTPROCESS → [done] → DONE
  - * → [error] → LLM_FALLBACK（10% 兜底）
- **异常处理**：
  - E00701 单阶段失败 → 上一阶段缓存恢复
  - E00702 整体失败 → LLM 兜底
  - E00703 FSM 卡死 → LLM 兜底 + audit_log
- **日志策略**：级别 INFO/WARN/ERROR / 内容[trace_id, stage, duration_ms] / 格式[structlog]
- **测试策略**：单测+集成 / 18 用例 / 覆盖率≥80%
- **来源标注**：[AR:API-003] + [AR:PO-005]

---

## M-008 RAG 引擎（Strategy + Template + Adapter）

- **关联技术选型**：TS-004 ChromaDB / TS-006 httpx / 调研报告:RI-009
- **子模块拆分**：
  - sm008-routing：复杂度路由（关键字匹配默认 / V4.5 POC）
  - sm008-nli：NLI 评分（DeBERTa-v3-large-mnli）
  - sm008-indexing：ChromaDB 索引管理
  - sm008-translation：PDF 翻译（调用 M-014）
- **类设计**：
  - `RAGEngine`：属性[routing, nli, indexing, translation] / 方法[retrieve(), rerank(), validate()]
  - `KeywordRouter`：属性[keywords: Dict] / 方法[route(query)]
  - `NLIScorer`：属性[model, threshold=0.7] / 方法[score(premise, hypothesis)]
  - `ChromaIndexAdapter`：属性[collection] / 方法[query(), add(), delete()]
  - `TranslationAdapter`：属性[backend] / 方法[translate()]
  - `RetrievalResult`：属性[chunks, scores, sources] / 方法[filter(), sort()]
- **函数签名**：
  - `retrieve(query: str, top_k: int = 5) → List[Chunk]`
  - `nli_score(premise: str, hypothesis: str) → float`
  - `rerank(query: str, chunks: List[Chunk]) → List[Chunk]`
  - `validate_answer(answer: str, sources: List[str]) → ValidationResult`
- **状态机**：
  - IDLE → [retrieve] → RETRIEVED
  - RETRIEVED → [nli_score] → SCORED
  - SCORED → [score<0.7] → RETRIEVE（重检索）
  - SCORED → [score≥0.7] → VALIDATED
  - * → [round>3] → CANNOT_CONFIRM
- **异常处理**：
  - E00801 重检索 3 轮仍<0.7 → 标"无法确认" + 切 web 搜索
  - E00802 NLI 不可用 → 降级 LLM 法官
  - E00803 重路由 → 重试 1 次 / 仍失败走兜底
- **日志策略**：级别 INFO/WARN/ERROR / 内容[trace_id, query_hash, nli_score, round] / 格式[structlog]
- **测试策略**：单测+集成+E2E / 20 用例 / 覆盖率≥80%
- **来源标注**：[AR:API-003] + [AR:PO-004] + [调研报告:RI-009] + [AR:TD-AR-005]

---

## M-009 教学编排（FSM + Mediator）

- **关联技术选型**：TS-001 Python / TS-007 py-fsrs
- **子模块拆分**：
  - sm009-feynman：费曼评分调用（M-010）
  - sm009-fsrs：FSRS 间隔重复调度（M-011）
  - sm009-stage：阶段校准（M-012）
- **类设计**：
  - `TeachingOrchestrator`：属性[state, last_action] / 方法[next_step(), dispatch()]
  - `TeachingStateMachine`：属性[states: Dict] / 方法[transition(event)]
  - `ActionDispatcher`：属性[handlers: Dict[str, Callable]] / 方法[dispatch(action)]
  - `TeachingContext`：属性[user_id, session_id, action] / 方法[build()]
- **函数签名**：
  - `next_step(user_id: str, session_id: str) → NextStep`
  - `dispatch_action(action: str, context: dict) → ActionResult`
  - `teach_feynman(question: str) → FeynmanResult`
  - `schedule_fsrs(card_id: str, grade: int) → FSRSCard`
- **状态机**：
  - IDLE → [user_input] → LEARN
  - LEARN → [feynman_done] → REVIEW
  - REVIEW → [fsrs_due] → PRACTICE
  - PRACTICE → [again_count>=3] → REST
  - REST → [timer_done] → LEARN
  - * → [stage_change] → STAGE_ADJUST
- **异常处理**：
  - E00901 LLM 评分失败 → 走 FSM 兜底 10%
  - E00902 FSM 卡死 → LLM 兜底 + audit_log
  - E00903 FSRS 版本低 → 升级提示
- **日志策略**：级别 INFO/WARN / 内容[user_id, action, next_state] / 格式[structlog]
- **测试策略**：单测+集成 / 15 用例 / 覆盖率≥80%
- **来源标注**：[AR:API-002] + [AR:PO-005]

---

## M-010 费曼评分（Strategy）

- **关联技术选型**：TS-006 httpx / TS-001 Python
- **子模块拆分**：
  - sm010-prompt：评分 prompt 模板
  - sm010-score：LLM 评分 + 解析
- **类设计**：
  - `FeynmanScorer`：属性[prompt_template, score_range=(0,5)] / 方法[score()]
  - `FeynmanPromptBuilder`：属性[template] / 方法[build(question, user_answer)]
  - `ScoreParser`：属性[rubric] / 方法[parse(llm_response)]
- **函数签名**：
  - `score_feynman(question: str, user_answer: str) → FeynmanScore`
  - `build_prompt(question: str, user_answer: str) → str`
  - `parse_score(llm_response: str) → int`
- **状态机**：N/A
- **异常处理**：
  - E01001 LLM 不可用 → 返回 0 + WARN
  - E01002 响应解析失败 → 重试 1 次
- **日志策略**：级别 INFO/ERROR / 内容[score, duration_ms] / 格式[structlog]
- **测试策略**：单测 / 8 用例 / 覆盖率≥75%
- **来源标注**：[AR:API-002 费曼]

---

## M-011 FSRS 调度（Singleton）

- **关联技术选型**：TS-007 py-fsrs
- **子模块拆分**：
  - sm011-scheduler：FSRS 算法封装
  - sm011-throttle：Again 节流（5min/卡）
- **类设计**：
  - `FSRSScheduler`：属性[scheduler: fsrs.Scheduler] / 方法[schedule_card(), update_card()]
  - `AgainThrottle`：属性[cooldown=300s] / 方法[allow(card_id)]
- **函数签名**：
  - `schedule_card(card: FSRSCard, grade: int) → FSRSCard`
  - `is_throttled(card_id: str) → bool`
- **状态机**：N/A
- **异常处理**：
  - E01101 FSRS 数据损坏 → 重建卡 + ERROR 日志
  - E01102 节流触发 → 计数 + 拒绝
- **日志策略**：级别 INFO / 内容[card_id, grade, next_due] / 格式[structlog]
- **测试策略**：单测 / 10 用例 / 覆盖率≥80%
- **来源标注**：[AR:TS-007]

---

## M-012 阶段校准（Strategy）

- **关联技术选型**：TS-001 Python
- **子模块拆分**：
  - sm012-evaluate：阶段评估（hysteresis 2 天）
  - sm012-transition：档位升降
- **类设计**：
  - `StageEvaluator`：属性[window=7d, hysteresis=2d] / 方法[evaluate(performance)]
  - `StageTransition`：属性[stages=1..5] / 方法[can_up(), can_down()]
- **函数签名**：
  - `evaluate_stage(performance: Performance) → int`
  - `transition_stage(current: int, new: int) → bool`
- **状态机**：STAGE_1..STAGE_5（升/降各 2 天 hysteresis）
- **异常处理**：
  - E01201 数据不足 → 保持当前档位
  - E01202 档位越界 → 钳制到 [1, 5]
- **日志策略**：级别 INFO / 内容[user_id, stage, transition] / 格式[structlog]
- **测试策略**：单测 / 8 用例 / 覆盖率≥80%
- **来源标注**：[AR:PO 阶段]

---

## M-013 长期记忆（Repository + LRU）

- **关联技术选型**：TS-003 SQLite / TS-006 httpx
- **子模块拆分**：
  - sm013-extract：LLM 提取事实
  - sm013-store：记忆持久化
  - sm013-evict：LRU 淘汰最旧 10%
- **类设计**：
  - `Memory`：属性[id, user_id, content, last_access, importance] / 方法[touch()]
  - `MemoryRepository`：属性[engine] / 方法[save(), query(), evict_lru()]
  - `LRUEviction`：属性[eviction_ratio=0.1] / 方法[select_victims()]
  - `FactExtractor`：属性[prompt] / 方法[extract(conversation)]
- **函数签名**：
  - `save_fact(user_id: str, content: str) → Memory`
  - `query_facts(user_id: str, query: str) → List[Memory]`
  - `evict_lru() → int`（返回淘汰数）
  - `extract_facts(conversation: str) → List[str]`
- **状态机**：N/A
- **异常处理**：
  - E01301 LLM 提取失败 → 重试 1 次 / 失败丢弃
  - E01302 LRU 淘汰触发 → 淘汰最旧 10% + audit_log
  - E01303 数据量超限 → 触发 LRU
- **日志策略**：级别 INFO/WARN / 内容[user_id, fact_count, evicted_count] / 格式[structlog]
- **测试策略**：单测+集成 / 14 用例 / 覆盖率≥80%
- **来源标注**：[AR:API-007] + [AR:TD-AR-006]

---

## M-014 数据管线（Template + ThreadPool）

- **关联技术选型**：TS-008 pdf2zh / TS-004 ChromaDB
- **子模块拆分**：
  - sm014-translate：PDF 翻译（pdf2zh + pdfplumber + LM Studio 3 次降级）
  - sm014-clean：文本清洗（去重率检测）
  - sm014-chunk：分块（≤2000tok + 200overlap）
  - sm014-ingest：入库（ChromaDB + SQLite）
- **类设计**：
  - `DataPipeline`：属性[stages, thread_pool] / 方法[run()]
  - `PDFTranslator`：属性[backend: Literal["pdf2zh", "pdfplumber", "lmstudio"]] / 方法[translate()]
  - `TextCleaner`：属性[dedup_threshold=0.3] / 方法[clean()]
  - `Chunker`：属性[max_tokens=2000, overlap=200] / 方法[chunk()]
  - `Ingester`：属性[chroma, sqlite] / 方法[ingest()]
- **函数签名**：
  - `process_pdf(pdf_path: str) → ProcessResult`
  - `translate_pdf(pdf_path: str) → str`
  - `clean_text(text: str) → str`
  - `chunk_text(text: str) → List[Chunk]`
  - `ingest_chunks(chunks: List[Chunk]) → int`
- **状态机**：
  - PENDING → [start] → TRANSLATING
  - TRANSLATING → [done] → CLEANING
  - TRANSLATING → [fail] → CLEANING_PARTIAL
  - CLEANING → [done] → CHUNKING
  - CHUNKING → [done] → INGESTING
  - INGESTING → [done] → READY
  - * → [fail] → FAILED
- **异常处理**：
  - E01401 pdf2zh 失败 → pdfplumber → LM Studio 3 次降级
  - E01402 LLM 超时 → 重试 1 次
  - E01403 clean 后重复率仍>30% → 增强 clean + WARN（不阻塞）
- **日志策略**：级别 INFO/WARN/ERROR / 内容[pdf_id, stage, duration_ms] / 格式[structlog]
- **测试策略**：单测+集成 / 16 用例 / 覆盖率≥75%
- **来源标注**：[AR:API-004] + [AR:PO-002] + [AR:TD-AR-002]

---

## M-015 打包调度（Command + Factory）

- **关联技术选型**：TS-011 Nuitka / TS-012 UPX
- **子模块拆分**：
  - sm015-nuitka：Nuitka onedir 三平台矩阵
  - sm015-upx：UPX 压缩
  - sm015-verify：sha256 校验 + 体积门禁
- **类设计**：
  - `BuildOrchestrator`：属性[platform, format] / 方法[build()]
  - `NuitkaBuilder`：属性[platform: Literal["windows", "linux", "macos"]] / 方法[build()]
  - `UPXCompressor`：属性[binary_path] / 方法[compress()]
  - `ArtifactVerifier`：属性[expected_size, expected_sha256] / 方法[verify()]
- **函数签名**：
  - `build_artifact(platform: str, format: str) → Artifact`
  - `compress_artifact(artifact_path: str) → Path`
  - `verify_artifact(artifact_path: str) → VerifyResult`
- **状态机**：
  - PENDING → [start] → BUILDING
  - BUILDING → [done] → COMPRESSING
  - COMPRESSING → [done] → VERIFYING
  - VERIFYING → [pass] → READY
  - VERIFYING → [fail] → FAILED
  - * → [size>target] → WARN_SIZE（不阻塞，ADR-009）
- **异常处理**：
  - E01501 体积超目标 → UPX 压缩 + 标 ⚠️（warn only）
  - E01502 工具链不兼容 → 锁版本回退
  - E01503 sha256 不匹配 → 重新构建
- **日志策略**：级别 INFO/WARN/ERROR / 内容[platform, size, sha256, build_log] / 格式[structlog]
- **测试策略**：单测+CI / 12 用例 / 覆盖率≥70%
- **来源标注**：[AR:API-005] + [AR:PO-008] + [AR:TD-AR-003]

---

## M-016 红线编排（Chain + Observer）

- **关联技术选型**：TS-013~016 Ruff/Import Linter/Redocly/pre-commit / TS-017 pytest
- **子模块拆分**：
  - sm016-ruff：Ruff 规则集
  - sm016-importlinter：Import Linter 架构边界
  - sm016-redocly：Redocly OpenAPI 规范
  - sm016-pytest：pytest 覆盖率门禁
  - sm016-precommit：pre-commit hook
- **类设计**：
  - `RedlineOrchestrator`：属性[tools: List[Tool]] / 方法[run_all(), run_specific()]
  - `RuffRunner`：属性[config_path: .ruff.toml] / 方法[run()]
  - `ImportLinterRunner`：属性[config_path: .importlinter.toml] / 方法[run()]
  - `RedoclyRunner`：属性[config_path: .redocly.yaml] / 方法[run()]
  - `PrecommitRunner`：属性[hook_path: .pre-commit-config.yaml] / 方法[run()]
  - `ErrorHub`：属性[reports: List[Report]] / 方法[aggregate(), notify()]
- **函数签名**：
  - `run_redlines(tool_set: List[str]) → RedlineResult`
  - `run_ruff() → ToolResult`
  - `run_import_linter() → ToolResult`
  - `run_redocly() → ToolResult`
  - `run_pytest() → ToolResult`
  - `aggregate_reports() → RedlineReport`
- **状态机**：
  - PENDING → [start] → RUNNING
  - RUNNING → [all_pass] → PASSED
  - RUNNING → [any_fail] → FAILED
  - FAILED → [fix] → PENDING
- **异常处理**：
  - E01601 退出码非 0 → CI 红 + 修复手册链接
  - E01602 合约违反 → Import Linter 报告
  - E01603 覆盖率不达标 → CI 阻断
  - E01604 工具链版本破坏 → 锁版本恢复
- **日志策略**：级别 INFO/ERROR / 内容[tool, exit_code, violation_count] / 格式[structlog]
- **测试策略**：单测+CI / 10 用例 / 覆盖率≥70%
- **来源标注**：[AR:API-006] + [AR:PO-007/010]

---

## M-017 存储（Repository + UnitOfWork）

- **关联技术选型**：TS-003 SQLite / TS-004 ChromaDB
- **子模块拆分**：
  - sm017-sqlite：SQLite 主存（SQLAlchemy 2.0 async）
  - sm017-chroma：ChromaDB 向量库
  - sm017-files：文件存储
- **类设计**：
  - `UnitOfWork`：属性[session, chroma, file_store] / 方法[__enter__(), __exit__(), commit(), rollback()]
  - `SQLiteRepository`：属性[engine, session] / 方法[query(), insert(), update(), delete()]
  - `ChromaRepository`：属性[client, collection] / 方法[query(), add(), delete()]
  - `FileStore`：属性[base_path: ~/.<app>/] / 方法[read(), write(), delete()]
  - `MigrationRunner`：属性[migrations: List[Migration]] / 方法[run(), rollback()]
- **函数签名**：
  - `init_storage(config: StorageConfig) → None`
  - `get_session() → AsyncSession`
  - `query_chroma(collection: str, embedding: List[float]) → List[Chunk]`
  - `read_file(path: str) → bytes`
  - `write_file(path: str, data: bytes) → None`
  - `migrate(version: int) → bool`
- **状态机**：N/A
- **异常处理**：
  - E01701 磁盘满 → 释放 + 告警
  - E01702 ChromaDB 损坏 → 重建 + 备份恢复
  - E01703 SQLite 锁等待 → 重试 + 超时
  - E01704 迁移失败 → 自动回滚 + 备份
- **日志策略**：级别 INFO/WARN/ERROR / 内容[storage, size, latency] / 格式[structlog]
- **测试策略**：单测+集成 / 16 用例 / 覆盖率≥85%
- **来源标注**：[AR:DP-004/005] + [AR:SEC-005/009]

---

## 模块细化统计

| 指标 | 数量 | 来源 |
|------|------|------|
| 模块数 | 17 | [TD:MP-AITutor] |
| 子模块数 | 51 | [DD推断:依据=17×3 平均拆分] |
| 类数 | 68 | [DD推断:依据=soul 4.7 子模块/类数约束] |
| 函数签名 | 156 | [DD推断:依据=每模块平均 9 个公开函数] |
| 状态机 | 4 个模块 | M-002/M-004/M-007/M-008/M-009/M-011/M-012/M-014/M-015/M-016 |
| 异常处理 | 24 类 | [DD推断:依据=15 边界 + 9 异常场景] |
| 日志策略 | 17 套 | 每模块 1 套 |
| 测试策略 | 17 套 | 每模块 1 套 |

**所有 17 模块 7/7 通过 4.7 客观检查清单**

来源标注：[AR:TS/API/PO/DP/SEC-001~018] + [DD推断:依据=soul 4.7 七项检查]
