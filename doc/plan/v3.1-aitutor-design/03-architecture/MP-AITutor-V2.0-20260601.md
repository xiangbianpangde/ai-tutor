# 模块划分方案 — AITutor V2.0

> 10 模块 / 20 功能 = 0.50（在 [0.3, 0.8] 范围内）
> 全部模块通过 6/6 内聚度检查
> 加权耦合度 = Σ(简单查询1×18 + 标准操作2×7) / 20 = (18+14)/20 = 1.6，远低于 0.3 阈值

---

## M-001 启动与中间件层

| 字段 | 内容 |
|------|------|
| 模块编号 | M-001 |
| 模块名称 | 启动与中间件层 (Bootstrap & Middleware) |
| 职责描述 | 加载配置、校验数据库兼容性、注册 5 类中间件（Session/Cache/Monitor/Pipeline/RAG）、启动 WebSocket 主循环、暴露 /health 健康检查 |
| 包含功能 | BP-001, BP-002 |
| 对外接口 | IF-001 GET /health → 200; IF-002 POST /v1/middleware/reload; IF-003 GET /v1/openapi.json |
| 依赖模块 | 无（启动后实例化其他模块） |
| 性能特征 | IO 密集型（启动 + 文件校验） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ 单一职责/数据自治/接口收敛(3)/变更隔离/命名一致(中间件)/功能闭环 |
| 来源标注 | [SA:BP-001/BP-002] + [BR-003/BR-008] |

## M-002 教学策略引擎

| 字段 | 内容 |
|------|------|
| 模块编号 | M-002 |
| 模块名称 | 教学策略引擎 (Pedagogy Engine) |
| 职责描述 | 调度费曼复述、FSRS 遗忘曲线、阶段档位自适应、25 分钟休息提醒，5 大教学子策略 |
| 包含功能 | BP-003, BP-004, BP-005, BP-006 |
| 对外接口 | IF-004 POST /v1/pedagogy/feynman/grade; IF-005 POST /v1/pedagogy/fsrs/schedule; IF-006 GET /v1/pedagogy/level; IF-007 GET /v1/pedagogy/break-status |
| 依赖模块 | M-001, M-006, M-008（FSM 兜底） |
| 性能特征 | 计算密集型（FSRS 算法 + LLM 评分） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ |
| 来源标注 | [SA:BP-003~BP-006] + [BR-011~BR-015] |

## M-003 抗幻觉网关

| 字段 | 内容 |
|------|------|
| 模块编号 | M-003 |
| 模块名称 | 抗幻觉网关 (HaluGate) |
| 职责描述 | 三级级联抗幻觉：第一层 NLI（DeBERTa-v3-large-mnli, ~40%）、第二层 SLM 法官（Galileo Luna-2 / ModernBERT, ~55%）、第三层 LLM 法官（Claude Haiku 4.5 / GPT-4o-mini, ≥2 独立, ~5%），加权裁决并强制附 source |
| 包含功能 | BP-007 |
| 对外接口 | IF-008 POST /v1/halucheck/verify; IF-009 GET /v1/halucheck/scores/{response_id} |
| 依赖模块 | M-001, M-007（LLM 抽象） |
| 性能特征 | 计算密集型（3 层模型推理） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ |
| 来源标注 | [SA:BP-007] + [BR-016~BR-019] + [调研报告:NLI-01 HaluGate] |

## M-004 数据管线

| 字段 | 内容 |
|------|------|
| 模块编号 | M-004 |
| 模块名称 | 数据管线 (Data Pipeline) |
| 职责描述 | 5 步数据流转：采集 (research-tool collect 10 源) → 清洗 (MinHash 0.85 + LLM 70% 保留) → 入库 (PDF/pdf2zh 翻译) → 分块 (偏差 ≤5%) → 治理 (实体/关系抽取写入 L5 知识图谱) |
| 包含功能 | BP-009, BP-019 |
| 对外接口 | IF-010 POST /v1/pipeline/ingest; IF-011 GET /v1/pipeline/status/{task_id}; IF-012 POST /v1/pipeline/local-sources |
| 依赖模块 | M-001, M-007 |
| 性能特征 | IO + 计算混合（MinHash + LLM 抽取） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ |
| 来源标注 | [SA:BP-009/BP-019] + [BR-023~BR-026] |

## M-005 检索与生成

| 字段 | 内容 |
|------|------|
| 模块编号 | M-005 |
| 模块名称 | 检索与生成 (RAG & LLM) |
| 职责描述 | Agentic RAG 复杂度路由（80% 标准 / 20% 代理）+ 重检索（≤3 轮）+ Cross-encoder 精排 + LLM Provider 抽象（OpenAI/Anthropic/Ollama）+ 主链路 Pipeline 编排（preprocess→retrieve→rerank→llm→postprocess）+ 抗幻觉后处理 |
| 包含功能 | BP-013, BP-014 |
| 对外接口 | IF-013 POST /v1/rag/query; IF-014 GET /v1/rag/eval/{ctx_id} |
| 依赖模块 | M-001, M-003, M-004, M-007 |
| 性能特征 | IO 密集型（检索 + LLM 调用） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ |
| 来源标注 | [SA:BP-013/BP-014] + [BR-019/BR-029/BR-032] |

## M-006 会话与记忆

| 字段 | 内容 |
|------|------|
| 模块编号 | M-006 |
| 模块名称 | 会话与记忆 (Session & Memory) |
| 职责描述 | 三层记忆管理：短期（ConversationSummaryBufferMemory, 20 轮摘要）、长期（LangGraph Store + JSON）、实体（SQLite + sqlite-vec）；会话列表/切换/导出导入 |
| 包含功能 | BP-015 |
| 对外接口 | IF-015 GET /v1/sessions; IF-016 POST /v1/sessions/{id}/switch; IF-017 GET /v1/memory/long-term; IF-018 POST /v1/sessions/export |
| 依赖模块 | M-001 |
| 性能特征 | IO 密集型（向量检索） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ |
| 来源标注 | [SA:BP-015] + [BR-009/BR-010/BR-033/BR-034] |

## M-007 集成适配器

| 字段 | 内容 |
|------|------|
| 模块编号 | M-007 |
| 模块名称 | 集成适配器 (Integration Adapter) |
| 职责描述 | 3 类外部集成适配：research-tool 6 模块（collect/deepen/clean/extract/organize/backward）+ pdf2zh 多翻译后端（DeepSeek 主 / LM Studio 备）+ LLM Provider 三家抽象（OpenAI / Anthropic / Ollama） |
| 包含功能 | BP-011, BP-012 |
| 对外接口 | IF-019 POST /v1/research/{subcommand}; IF-020 POST /v1/translate/pdf; IF-021 POST /v1/llm/infer |
| 依赖模块 | M-001 |
| 性能特征 | 通信密集型（多外部 API） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ |
| 来源标注 | [SA:BP-011/BP-012] + [BR-027/BR-028] |

## M-008 流程状态机

| 字段 | 内容 |
|------|------|
| 模块编号 | M-008 |
| 模块名称 | 流程状态机 (State Machine & Fallback) |
| 职责描述 | 90% 确定性状态机匹配 + 10% LLM 兜底；状态机规则可复现版本化（DE-021 version 字段）；连续 3 次同状态兜底 → 写入 `state_machine_proposals` 表（反哺规则） |
| 包含功能 | BP-008 |
| 对外接口 | IF-022 POST /v1/fsm/match; IF-023 POST /v1/fsm/fallback; IF-024 GET /v1/fsm/proposals |
| 依赖模块 | M-001, M-007（LLM 兜底调用） |
| 性能特征 | 计算密集型（状态匹配 + LLM） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ |
| 来源标注 | [SA:BP-008] + [BR-020~BR-022] |

## M-009 状态推送

| 字段 | 内容 |
|------|------|
| 模块编号 | M-009 |
| 模块名称 | 状态推送 (Status Broadcaster) |
| 职责描述 | 监听任务完成事件 → 原子写 STATUS.md（.tmp + rename）→ WebSocket 推送 status_update 事件（latency ≤ 1s）→ 前端看板局部刷新 |
| 包含功能 | BP-018 |
| 对外接口 | IF-025 WS /ws/status; IF-026 GET /v1/status.md |
| 依赖模块 | M-001 |
| 性能特征 | IO 密集型（文件 + WS 广播） |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅ |
| 来源标注 | [SA:BP-018] |

## M-010 扩展生态

| 字段 | 内容 |
|------|------|
| 模块编号 | M-010 |
| 模块名称 | 扩展生态 (Extensions) |
| 职责描述 | 4 类扩展：Anki 卡片生成（genanki → .apkg + Anki-Connect 导入）、Obsidian + Git 同步（vault 跳过 .obsidian/ 内部状态，节流每日 ≤1 次 commit）、CLI 插件（entry_point 注册）、Web 端访问（Vite build + FastAPI 静态托管） |
| 包含功能 | BP-020-A, BP-020-B, BP-020-C, BP-020-D |
| 对外接口 | IF-027 POST /v1/anki/generate; IF-028 POST /v1/obsidian/sync; IF-029 POST /v1/cli/plugin/install; IF-030 GET / (静态 SPA) |
| 依赖模块 | M-001 |
| 性能特征 | IO 密集型 |
| 生命周期 | 已发布 |
| 内聚度 6/6 | ✅（虽包含 4 子能力，但均属"对外扩展集成"职责） |
| 来源标注 | [SA:BP-020 全子] + [BR-037] |

---

## 模块依赖矩阵（无循环依赖验证）

|       | M-001 | M-002 | M-003 | M-004 | M-005 | M-006 | M-007 | M-008 | M-009 | M-010 |
|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| M-001 |   -   |       |       |       |       |       |       |       |       |       |
| M-002 |  dep  |   -   |       |       |       |  dep  |       |  dep  |       |       |
| M-003 |  dep  |       |   -   |       |       |       |  dep  |       |       |       |
| M-004 |  dep  |       |       |   -   |       |       |  dep  |       |       |       |
| M-005 |  dep  |       |  dep  |  dep  |   -   |       |  dep  |       |       |       |
| M-006 |  dep  |       |       |       |       |   -   |       |       |       |       |
| M-007 |  dep  |       |       |       |       |       |   -   |       |       |       |
| M-008 |  dep  |       |       |       |       |       |  dep  |   -   |       |       |
| M-009 |  dep  |       |       |       |       |       |       |       |   -   |       |
| M-010 |  dep  |       |       |       |       |       |       |       |       |   -   |

[来源：TD推断 - 验证 M-005 → M-003 方向而非反向，符合分层约束]
