# 接口契约定义 — AITutor V3.1

> 8 个核心 IF 全有完整 IC 契约（入参/出参/错误码/时序/前置后置/幂等性），全部通过 4.12 验收。
> 来源：[AR:API-001~008] + [DD推断:依据]

---

## IC-001 服务启动（API-001 / IF-001）

- **接口名称**：服务启动
- **接口描述**：Uvicorn 启动 FastAPI 应用，加载 pyproject.toml + .env，依次装配 5 类中间件（Session/Cache/Monitor/Pipeline/RAG），启动期 validate 健康检查端点
- **入参定义**：
  - `config_path: str` 必填 默认 `./pyproject.toml` 规则 须存在且可读 配置文件路径
  - `host: str` 可选 默认 `127.0.0.1` 规则 IPv4 监听地址
  - `port: int` 可选 默认 `8000` 规则 [1024, 65535] 监听端口
  - `env_file: str` 可选 默认 `.env` 规则 须存在 环境变量文件
- **出参定义**：
  - `app: FastAPI` 必填 FastAPI 应用实例
  - `middleware_status: Dict[str, bool]` 必填 5MW 装配状态
  - `startup_duration_ms: int` 必填 启动耗时（毫秒）
- **错误码**：
  - E00101 含义: 依赖缺失 触发: 5MW 任一未注册 处理: 拒绝启动+详细日志
  - E00102 含义: 端口冲突 触发: 端口被占用 处理: 提示用户改端口
  - E00103 含义: 旧库不兼容 触发: schema 版本不匹配 处理: 自动迁移/失败备份
  - E00106 含义: MW 初始化失败 触发: 装配过程异常 处理: 退出码非 0
- **时序图**：
  - 调用方 → OS: 启动命令
  - OS → Uvicorn: 加载 pyproject.toml
  - Uvicorn → ConfigLoader: 加载 .env
  - ConfigLoader → AppLauncher: build_app()
  - AppLauncher → MiddlewareValidator: validate_mw()
  - MiddlewareValidator → AppLauncher: ok/fail
  - AppLauncher → Uvicorn: start
  - Uvicorn → 调用方: 监听 loopback:8000
- **前置条件**：pyproject.toml 存在、.env 存在、5MW 可注册
- **后置条件**：HTTP 监听就绪、/health 返回 200
- **并发安全**：N/A（启动期单次）
- **幂等性**：是 / 幂等键：启动命令路径 / 重复启动：先停旧进程
- **性能约束**：启动 ≤30s（含 5MW 装配）
- **来源标注**：[AR:API-001] + [AR:DP-001]

---

## IC-002 学习回合（API-002 / IF-002）

- **接口名称**：学习回合
- **接口描述**：单回合对话处理，触发 Pipeline 调度（preprocess→retrieve→rerank→llm→postprocess），返回答案 + 引用源
- **入参定义**：
  - `session_id: str` 必填 规则 UUIDv4 会话 ID
  - `user_id: str` 必填 规则 强校验（防 CE-003 串号） 用户 ID
  - `query: str` 必填 规则 长度 [1, 2000] 用户问题
  - `action: Literal["learn", "review", "rest"]` 必填 默认 learn 教学动作
  - `context_ids: List[str]` 可选 默认 [] 规则 ≤10 关联上下文（如 FSRS 卡片 ID）
  - `stream: bool` 可选 默认 false 是否走 WS 推送
- **出参定义**：
  - `answer: str` 必填 LLM 生成答案
  - `sources: List[SourceRef]` 必填 引用源（chunk_id, doc_id, score）
  - `route_decision: Literal["direct", "rag", "web"]` 必填 路由决策
  - `nli_score: float` 选填 NLI 评分
  - `trace_id: str` 必填 32hex 追踪 ID
  - `fsm_fallback: bool` 必填 是否走 LLM 兜底
- **错误码**：
  - E00901 含义: LLM 评分失败 触发: 评分异常 处理: 走 FSM 兜底 10%
  - E00902 含义: FSM 卡死 触发: 状态机无转换 处理: LLM 兜底 + audit_log
  - E00903 含义: FSRS 版本低 触发: schema 旧 处理: 升级提示
  - E00203 含义: Token 无效 触发: 鉴权失败 处理: 401 重定向
  - E00204 含义: 限流触发 触发: qps 超限 处理: 429 + Retry-After
  - E00704 含义: Pipeline 超时 触发: 5s 未完成 处理: 走兜底
  - E00401 含义: session 不存在 触发: 会话过期 处理: 404 + 新建提示
  - E00403 含义: DB 写失败 触发: 存储异常 处理: 5xx + 重试
- **时序图**：
  - 客户端 → API 网关: POST /api/v1/session/{id}/turn
  - 网关 → AG-001: Auth 校验
  - 网关 → AG-009 教学编排: 路由 action
  - AG-009 → AG-007 Pipeline: 调度 5 阶段
  - AG-007 → AG-008 RAG: retrieve
  - AG-007 → LLM Provider: llm call
  - AG-007 → AG-006 事件总线: trace + 日志
  - AG-007 → 网关: 返回 answer
  - 网关 → 客户端: 200 OK (或 WS 推送)
- **前置条件**：session 存在且 ACTIVE、user_id 强校验通过、Token 有效
- **后置条件**：session 状态更新、audit_log 记录、cache 写入（hit 后）
- **并发安全**：是（asyncio.Lock 保护 session 写、SQLite WAL）
- **幂等性**：是 / 幂等键：`request_id: UUIDv4` / 有效期 5min / 重复请求：返回首次结果
- **性能约束**：单回合 ≤5s（P95）、≤10s（P99）
- **来源标注**：[AR:API-002] + [AR:PO-005] + [AR:SEC-002/009]

---

## IC-003 RAG 检索（API-003 / IF-003）

- **接口名称**：RAG 检索
- **接口描述**：单次 RAG 检索，路由决策（直接答/RAG/web 搜索），NLI 评分，重检索 ≤3 轮，标"无法确认"切 web 搜索
- **入参定义**：
  - `query: str` 必填 规则 长度 [1, 2000] 检索 query
  - `query_features: Dict` 选填 规则 必含[keywords, intent] 预处理特征
  - `threshold: float` 选填 默认 0.7 规则 [0, 1] NLI 评分阈值
  - `top_k: int` 选填 默认 5 规则 [1, 20] 返回 chunk 数
  - `max_rounds: int` 选填 默认 3 规则 [1, 5] 最大重检索轮次
- **出参定义**：
  - `top_k_chunks: List[Chunk]` 必填 检索结果
  - `nli_score: float` 必填 NLI 评分
  - `sources: List[SourceRef]` 必填 引用源
  - `route_decision: Literal["direct", "rag", "web", "cannot_confirm"]` 必填 路由决策
  - `rounds: int` 必填 实际重检索轮次
  - `trace_id: str` 必填 32hex
- **错误码**：
  - E00801 含义: 重检索 3 轮仍<0.7 触发: NLI 不达标 处理: 标"无法确认"+切 web 搜索
  - E00802 含义: NLI 不可用 触发: 模型加载失败 处理: 降级 LLM 法官
  - E00803 含义: 重路由失败 触发: 1 次重试仍败 处理: 走兜底
  - E00705 含义: RAG 超时 触发: 10s 未完成 处理: 降级直接答
- **时序图**：
  - Pipeline → AG-008: retrieve()
  - AG-008 → AG-008.routing: route(query)
  - AG-008 → AG-008.indexing: query ChromaDB
  - AG-008 → AG-008.nli: score(chunks, query)
  - AG-008 → Pipeline: 返回结果
  - 若 score<0.7 → AG-008 → AG-008.indexing: 重新检索（≤3 轮）
- **前置条件**：ChromaDB 集合存在、query 非空
- **后置条件**：NLI 评分缓存写入（TTL 1h）
- **并发安全**：是（ChromaDB 单写者 + asyncio 协程）
- **幂等性**：是 / 幂等键：query_hash（SHA256） / 有效期 1h / 重复：返回缓存
- **性能约束**：单次 ≤10s（P95）、≤15s（P99）
- **来源标注**：[AR:API-003] + [AR:PO-004] + [AR:ADR-006]

---

## IC-004 数据入库（API-004 / IF-004）

- **接口名称**：数据入库
- **接口描述**：PDF 翻译入库，pdf2zh→pdfplumber→LM Studio 3 次降级，clean + chunk + 入 ChromaDB + SQLite
- **入参定义**：
  - `file: UploadFile` 必填 规则 PDF≤100MB、类型白名单 上传文件
  - `user_id: str` 必填 规则 强校验 用户 ID
  - `clean_dedup: bool` 选填 默认 true 启用文本去重
  - `chunk_size: int` 选填 默认 2000 规则 [500, 4000] 分块 token 数
  - `overlap: int` 选填 默认 200 规则 [0, 500] overlap token 数
- **出参定义**：
  - `doc_id: str` 必填 UUIDv4 文档 ID
  - `status: Literal["READY", "FAILED", "PARTIAL"]` 必填 状态
  - `chunk_count: int` 必填 chunk 数
  - `translation_backend: Literal["pdf2zh", "pdfplumber", "lmstudio"]` 必填 使用的翻译后端
  - `duration_ms: int` 必填 处理耗时
  - `trace_id: str` 必填 32hex
- **错误码**：
  - E01401 含义: pdf2zh 失败 触发: PDF 解析异常 处理: pdfplumber→LM Studio 3 次降级
  - E01402 含义: LLM 超时 触发: 30s 未响应 处理: 重试 1 次
  - E01403 含义: clean 后重复率>30% 触发: 去重不足 处理: 增强 clean + WARN（不阻塞）
  - E01404 含义: 文件超大 触发: >100MB 处理: 413 拒绝
  - E01405 含义: 文件类型非法 触发: 非 PDF 处理: 415 拒绝
- **时序图**：
  - 客户端 → API 网关: POST /api/v1/ingest (multipart)
  - 网关 → AG-014: 调度
  - AG-014 → AG-014.translate: pdf2zh / pdfplumber / lmstudio
  - AG-014 → AG-014.clean: 去重 + 清洗
  - AG-014 → AG-014.chunk: 分块
  - AG-014 → AG-017: ingest ChromaDB + SQLite
  - AG-014 → 网关: 返回 doc_id
- **前置条件**：文件类型白名单、大小限制、user_id 强校验
- **后置条件**：chroma 集合更新、sqlite documents 表写入
- **并发安全**：是（每文档独立任务 + asyncio.Semaphore(2)）
- **幂等性**：否（每次入库生成新 doc_id；客户端可去重）
- **性能约束**：10 页 PDF ≤60s（P95）、100 页 ≤300s（P95）
- **来源标注**：[AR:API-004] + [AR:PO-002] + [AR:SEC-005]

---

## IC-005 打包构建（API-005 / IF-005）

- **接口名称**：打包构建
- **接口描述**：CI 触发，Nuitka onedir 三平台矩阵构建 + UPX 压缩 + sha256 校验
- **入参定义**：
  - `platform: Literal["windows", "linux", "macos"]` 必填 目标平台
  - `format: Literal["cli", "gui"]` 选填 默认 cli 形态（gui V3.5）
  - `tag: str` 必填 规则 semver 版本标签
  - `push: bool` 选填 默认 false 是否推送 artifact
- **出参定义**：
  - `artifact_path: str` 必填 产物路径
  - `size_bytes: int` 必填 体积（字节）
  - `sha256: str` 必填 64hex 校验和
  - `build_log: str` 必填 构建日志
  - `duration_ms: int` 必填 构建耗时
- **错误码**：
  - E01501 含义: 体积超目标 触发: CLI>50MB / GUI>200MB 处理: UPX 压缩+⚠️（warn only）
  - E01502 含义: 工具链不兼容 触发: 锁版本破坏 处理: 锁版本回退
  - E01503 含义: sha256 不匹配 触发: 校验失败 处理: 重新构建
  - E01504 含义: CI 超时 触发: >10min 处理: 拆分任务
- **时序图**：
  - GitHub Actions → AG-015: workflow_dispatch
  - AG-015 → AG-015.nuitka: onedir build
  - AG-015 → AG-015.upx: compress
  - AG-015 → AG-015.verify: sha256 + size
  - AG-015 → GitHub Actions: upload artifact
- **前置条件**：CI runner 就绪、GitHub Secrets 配置
- **后置条件**：artifact 上传、metadata 写入 SQLite
- **并发安全**：是（CI 矩阵并行 3 平台）
- **幂等性**：是 / 幂等键：`platform + tag + sha` / 重复：跳过
- **性能约束**：单平台 ≤10min
- **来源标注**：[AR:API-005] + [AR:PO-008] + [AR:ADR-009]

---

## IC-006 红线检测（API-006 / IF-006）

- **接口名称**：红线检测
- **接口描述**：CI 进程 / pre-commit hook 调用，4 工具链（Ruff/Import Linter/Redocly/pre-commit）并行执行，CI 阻断
- **入参定义**：
  - `tool_set: List[Literal["ruff", "import_linter", "redocly", "pre_commit", "pytest"]]` 必填 默认全量 工具集
  - `changed_files: List[str]` 选填 默认全量 变更文件（增量）
  - `fail_fast: bool` 选填 默认 false 任一失败即停
- **出参定义**：
  - `exit_code: int` 必填 [0, 1] 退出码
  - `violation_count: int` 必填 违规计数
  - `raw_output: Dict[str, str]` 必填 各工具原始输出
  - `fix_url: str` 必填 修复手册链接
  - `duration_ms: int` 必填 总耗时
- **错误码**：
  - E01601 含义: 退出码非 0 触发: 任一工具失败 处理: CI 红+修复手册
  - E01602 含义: 合约违反 触发: Import Linter 报告 处理: 显示违规路径
  - E01603 含义: 覆盖率<80% 触发: pytest-cov 阻断 处理: 补测试用例
  - E01604 含义: 工具链版本破坏 触发: 锁版本不匹配 处理: 锁版本恢复
- **时序图**：
  - GitHub Actions → AG-016: 4 工具并行
  - AG-016 → Ruff / Import Linter / Redocly / pytest: 并行执行
  - 各工具 → AG-016: 返回 exit_code + raw_output
  - AG-016 → AG-016.aggregate: 汇总报告
  - AG-016 → GitHub Actions: exit_code + fix_url
- **前置条件**：工具链锁版本、4 工具配置文件存在
- **后置条件**：DE-046 redline_report 写入、CI 阻断（branch protection）
- **并发安全**：是（4 工具并行子进程）
- **幂等性**：是 / 幂等键：`commit_sha + tool_set` / 重复：返回缓存
- **性能约束**：4 工具并行 ≤5min
- **来源标注**：[AR:API-006] + [AR:PO-007/010] + [AR:ADR-010]

---

## IC-007 长期记忆（API-007 / IF-007）

- **接口名称**：长期记忆
- **接口描述**：进程内 async 协程 + SQLite 事务，LLM 提取事实 + LRU 淘汰最旧 10%
- **入参定义**：
  - `user_id: str` 必填 规则 强校验（防 CE-003 串号）用户 ID
  - `action: Literal["save", "query", "evict"]` 必填 操作类型
  - `content: str` 可选 规则 长度 [1, 1000] save 时必填 事实内容
  - `query: str` 可选 query 时必填 检索 query
  - `importance: int` 可选 默认 1 规则 [1, 5] V4.5 重要性
- **出参定义**：
  - `memories: List[Memory]` 必填 query 时返回记忆列表
  - `saved_id: str` 必填 save 时返回记忆 ID
  - `evicted_count: int` 必填 evict 时返回淘汰数
  - `trace_id: str` 必填 32hex
- **错误码**：
  - E01301 含义: LLM 提取失败 触发: 提取异常 处理: 重试 1 次/失败丢弃
  - E01302 含义: LRU 淘汰触发 触发: 容量超限 处理: 淘汰最旧 10%
  - E01303 含义: 数据量超限 触发: 100k 记忆 处理: 强制 LRU
  - E00403 含义: DB 写失败 触发: 存储异常 处理: 5xx 重试
- **时序图**：
  - AG-009 → AG-013: save/query/evict
  - AG-013 → AG-013.extract: LLM 提取（save 时）
  - AG-013 → SQLite: write/read
  - AG-013 → AG-013.lru: 检查容量 + 淘汰
  - AG-013 → AG-009: 返回结果
- **前置条件**：user_id 强校验、SQLite 连接正常
- **后置条件**：记忆持久化、audit_log 记录
- **并发安全**：是（SQLite WAL + 事务）
- **幂等性**：是 / 幂等键：`content_hash`（save） / 重复 save：去重
- **性能约束**：单写 ≤100ms、单查 ≤200ms
- **来源标注**：[AR:API-007] + [AR:TD-AR-006]

---

## IC-008 WS 推送（API-008 / IF-008）

- **接口名称**：WS 推送
- **接口描述**：WebSocket 推送（starlette.websockets），subprotocol `aitutor.v1`，连接时 Token 校验，最大 1000 连接，事件总线广播
- **入参定义**：
  - `token: str` 必填 连接时 Token 校验
  - `subprotocol: Literal["aitutor.v1"]` 必填 默认 aitutor.v1
  - `session_id: str` 可选 关联 session
- **出参定义（事件）**：
  - `event_type: str` 必填 [pipeline_stage, llm_chunk, fsrs_update, rest_prompt, error]
  - `payload: Dict` 必填 事件负载
  - `ts: int` 必填 时间戳（毫秒）
  - `trace_id: str` 必填 32hex
- **错误码**：
  - E00201 含义: 连接断开 触发: 网络中断 处理: 指数退避 ≤30s + 状态补发
  - E00202 含义: 超限拒绝 触发: >1000 连接 处理: 客户端降级轮询
  - E00203 含义: Token 无效 触发: 鉴权失败 处理: 关闭连接 + 401
  - E00205 含义: 序列化失败 触发: payload 非法 处理: 跳过事件 + WARN
- **时序图**：
  - 客户端 → API 网关: WS upgrade（Sec-WebSocket-Protocol: aitutor.v1）
  - 网关 → AG-002: Token 校验
  - AG-002 → AG-002.connections: 注册
  - 业务模块 → AG-006: publish_event
  - AG-006 → AG-002: broadcast
  - AG-002 → 客户端: WS frame
  - 客户端 → AG-002: close
  - AG-002 → AG-002.connections: 注销
- **前置条件**：Token 有效、连接数 <1000、subprotocol 匹配
- **后置条件**：连接表更新、事件推送
- **并发安全**：是（asyncio Lock 保护连接表）
- **幂等性**：N/A（事件流）
- **性能约束**：端到端 ≤1s（P95）
- **来源标注**：[AR:API-008] + [AR:PO-001] + [AR:SEC-007]

---

## 接口契约验收汇总（4.12）

| 契约编号 | 入参完整 | 出参完整 | 错误码覆盖 | 时序明确 | 前置后置 | 幂等性 | 验收 |
|---------|---------|---------|-----------|---------|---------|--------|------|
| IC-001 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| IC-002 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| IC-003 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| IC-004 | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | 通过 |
| IC-005 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| IC-006 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| IC-007 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| IC-008 | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | 通过 |

**8/8 全部通过 4.12 验收标准**

来源标注：[AR:API-001~008] + [DD推断:依据=soul 4.12 验收清单]
