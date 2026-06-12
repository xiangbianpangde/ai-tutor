# 数据字典 — AITutor V2.0（终版）

> 来源：PRD V2.0 + 调研报告 V2.0 + 业务流程图
> 编号：DE-001 ~ DE-045
> 字段数上限：30/实体

---

## DE-001 配置实体
- **实体描述**：存储系统启动配置（端口、数据库路径、Redis 地址、日志级别等），从 `pyproject.toml` + `.env` 合并而来
- **字段列表**：
  - config_key | string | 必填, 唯一 | 配置项名
  - config_value | string | 必填 | 配置值
  - scope | enum(USER, SYSTEM) | 默认 SYSTEM | 作用域
  - updated_at | timestamp | 必填 | 更新时间
- **实体关系**：1:N → DE-038 (artifact 配置项)
- **来源标注**：[PRD:F-001] + [SA推断:依据=标准配置惯例]

## DE-002 服务实例
- **实体描述**：FastAPI 单进程运行期元数据（PID、启动时间、版本）
- **字段列表**：
  - pid | int | 必填, 唯一 | 进程 ID
  - started_at | timestamp | 必填 | 启动时间
  - version | string | 必填 | 版本号（来自 pyproject）
  - host | string | 默认 127.0.0.1 | 监听地址
  - port | int | 默认 8000 | 监听端口
- **实体关系**：1:1 → DE-005 (WS 连接池)
- **来源标注**：[PRD:F-001]

## DE-003 向后兼容报告
- **实体描述**：v1 数据库 schema 检测结果，决定是否走迁移
- **字段列表**：
  - db_path | string | 必填 | 数据库文件路径
  - schema_version | string | 必填 | 旧 schema 版本
  - target_version | string | 必填 | 目标 schema 版本
  - compatible | bool | 必填 | 是否兼容
  - migration_sql | text | 可空 | 迁移 SQL 脚本
- **来源标注**：[PRD:F-001] + [调研报告:RI-001]

## DE-004 中间件清单
- **实体描述**：5 类中间件注册状态
- **字段列表**：
  - middleware_name | enum(Session, Cache, Monitor, Pipeline, RAG) | 必填, 唯一
  - enabled | bool | 必填 | 是否启用
  - backend | string | 必填 | 后端实现（SQLite/Redis/structlog...）
  - config_json | text | 可空 | 中间件专属配置
- **来源标注**：[PRD:F-002]

## DE-005 WS 连接池
- **实体描述**：WebSocket 连接追踪（用于状态推送、监控）
- **字段列表**：
  - conn_id | string | 必填, 唯一 | 连接 UUID
  - client_type | enum(DESKTOP, WEB, CLI) | 必填
  - connected_at | timestamp | 必填
  - last_ping_at | timestamp | 必填
  - user_session_id | string | 外键 → DE-033 | 关联会话
- **来源标注**：[PRD:F-002/F-005/F-013]

## DE-006 Session 实例
- **实体描述**：会话管理（短期/长期/实体三层记忆）
- **字段列表**：
  - session_id | string | 必填, 唯一
  - short_term_backend | enum(ConversationSummaryBufferMemory) | 必填
  - long_term_backend | enum(LangGraphStore) | 必填
  - entity_backend | enum(SQLiteVec) | 必填
  - max_tokens | int | 默认 4000 | token 上限
  - summary_interval | int | 默认 20 | 摘要触发轮次
- **来源标注**：[PRD:F-002] + [调研报告:S-011]

## DE-007 Cache 实例
- **实体描述**：缓存层（SQLite+Redis 双后端）
- **字段列表**：
  - cache_key | string | 必填, 唯一 | 含 query hash + 语义向量
  - cache_value | text | 必填 | 序列化回答
  - semantic_threshold | float | 范围 0.85~0.95 | 语义命中阈值
  - backend | enum(SQLITE, REDIS) | 必填 | 命中后端
  - created_at | timestamp | 必填
  - expires_at | timestamp | 必填
  - hit_count | int | 默认 0 | 命中次数
- **来源标注**：[PRD:F-002/F-009] + [调研报告:S-013]

## DE-008 Monitor 实例
- **实体描述**：可观测性埋点（structlog + OTel）
- **字段列表**：
  - trace_id | string(32 hex) | 必填, 唯一
  - span_id | string(16 hex) | 必填
  - parent_span_id | string(16 hex) | 可空
  - event_type | enum(QUERY, RETRIEVAL, LLM_CALL, HALLUCINATION_CHECK) | 必填
  - latency_ms | int | 必填
  - quality_score | float | 范围 0~1 | 质量评分
  - llm_tokens | int | 必填
  - cache_hit | bool | 必填
  - created_at | timestamp | 必填
- **来源标注**：[PRD:F-002] + [调研报告:S-016]

## DE-009 Pipeline 实例
- **实体描述**：主链路 5 步管道（preprocess→retrieve→rerank→llm→postprocess）
- **字段列表**：
  - pipeline_id | string | 必填, 唯一
  - step_sequence | json | 必填 | 步骤定义
  - enabled | bool | 必填
  - timeout_ms | int | 默认 30000 | 总超时
- **来源标注**：[PRD:F-002]

## DE-010 RAG 实例
- **实体描述**：Agentic RAG 路由 + 重检索
- **字段列表**：
  - rag_id | string | 必填, 唯一
  - complexity_threshold | json | 必填 | 复杂度判定规则
  - max_retrieval_rounds | int | 默认 3 | 重检索上限
  - coverage_target | float | 默认 0.7 | 覆盖度目标
- **来源标注**：[PRD:F-008] + [调研报告:S-003]

## DE-011 概念集
- **实体描述**：一节课程涉及的核心概念（L5 知识图谱节点）
- **字段列表**：
  - concept_id | string | 必填, 唯一
  - concept_name | string | 必填
  - lesson_id | string | 外键 → DE-025
  - importance | float | 范围 0~1
- **来源标注**：[PRD:F-003.1]

## DE-012 复述题
- **实体描述**：费曼复述题目
- **字段列表**：
  - question_id | string | 必填, 唯一
  - concept_id | string | 外键 → DE-011
  - question_text | text | 必填
  - expected_keywords | json | 必填 | 期望关键词
  - difficulty | enum(EASY, MEDIUM, HARD) | 必填
- **来源标注**：[PRD:F-003.1]

## DE-013 用户复述
- **实体描述**：用户对费曼题的回答
- **字段列表**：
  - answer_id | string | 必填, 唯一
  - question_id | string | 外键 → DE-012
  - user_id | string | 必填
  - answer_text | text | 必填
  - audio_path | string | 可空 | 录音文件
  - submitted_at | timestamp | 必填
- **来源标注**：[PRD:F-003.1]

## DE-014 评分报告
- **实体描述**：费曼题评分结果
- **字段列表**：
  - report_id | string | 必填, 唯一
  - answer_id | string | 外键 → DE-013
  - overall_score | float | 范围 0~100 | 总分
  - coverage_score | float | 范围 0~100 | 概念覆盖率
  - accuracy_score | float | 范围 0~100 | 准确性
  - weak_points | json | 必填 | 薄弱点
  - follow_up_questions | json | 可空 | 追问
  - trace_id | string(32 hex) | 必填
- **来源标注**：[PRD:F-003.1] + [调研报告:S-019]

## DE-015 待复习列表
- **实体描述**：FSRS 调度到期的卡片
- **字段列表**：
  - card_id | string | 必填, 唯一
  - user_id | string | 必填
  - next_due | timestamp | 必填
  - concept_id | string | 外键 → DE-011
- **来源标注**：[PRD:F-003.2] + [调研报告:S-002]

## DE-016 更新后卡片（FSRS）
- **实体描述**：FSRS 调度后的卡片状态
- **字段列表**：
  - card_id | string | 必填, 唯一, 外键 → DE-015
  - stability | float | 必填 | FSRS stability
  - difficulty | float | 必填 | FSRS difficulty (0~1)
  - retrievability | float | 必填 | FSRS retrievability (0~1)
  - next_due | timestamp | 必填
  - last_rating | enum(AGAIN, HARD, GOOD, EASY) | 必填
  - last_reviewed_at | timestamp | 必填
- **来源标注**：[PRD:F-003.2] + [调研报告:S-002] + [RI-NEW-2 移交 BKT 协同 schema]

## DE-017 正确率统计
- **实体描述**：最近 7 天正确率（滑动窗口）
- **字段列表**：
  - user_id | string | 必填
  - window_start | date | 必填
  - window_end | date | 必填
  - total_questions | int | 必填
  - correct_count | int | 必填
  - accuracy_rate | float | 范围 0~1 | 派生
- **来源标注**：[PRD:F-003.3/F-016]

## DE-018 学习者档案
- **实体描述**：用户学习偏好、节奏、档位
- **字段列表**：
  - user_id | string | 必填, 唯一
  - subject | string | 必填 | 学科
  - pace | enum(CONSERVATIVE, STANDARD, AGGRESSIVE) | 必填
  - current_level | enum(LEVEL_1_0, LEVEL_1_5, LEVEL_2_0) | 必填
  - local_sources_dir | string | 可空
  - created_at | timestamp | 必填
  - updated_at | timestamp | 必填
- **来源标注**：[PRD:F-014/F-016]

## DE-019 声明集
- **实体描述**：抗幻觉引擎从回答中抽取的可验证声明
- **字段列表**：
  - claim_id | string | 必填, 唯一
  - response_id | string | 必填, 唯一
  - claim_text | text | 必填
  - source_doc_ids | json | 必填 | 引用源
  - extracted_at | timestamp | 必填
- **来源标注**：[PRD:F-003.5] + [调研报告:S-012]

## DE-020 幻觉评分
- **实体描述**：多路径防御（HaluGate）裁决结果
- **字段列表**：
  - score_id | string | 必填, 唯一
  - claim_id | string | 外键 → DE-019
  - nli_score | float | 范围 0~1 | 第一层 NLI
  - nli_label | enum(ENTAIL, CONTRADICT) | 必填
  - slm_score | float | 范围 0~1 | 第二层 SLM
  - llm_judge_scores | json | 必填 | 多 LLM 法官独立打分
  - final_score | float | 范围 0~1 | 加权
  - trace_id | string(32 hex) | 必填
  - judged_at | timestamp | 必填
- **来源标注**：[PRD:F-003.5] + [调研报告:S-012, NLI-01 HaluGate]

## DE-021 状态机定义
- **实体描述**：90% 状态机规则库
- **字段列表**：
  - state_id | string | 必填, 唯一
  - state_name | string | 必填
  - transitions | json | 必填 | 状态转移规则
  - fallback_to_llm | bool | 默认 false
  - version | int | 必填 | 规则版本
- **来源标注**：[PRD:F-003.6] + [调研报告:S-019]

## DE-022 审计日志
- **实体描述**：10% LLM 兜底调用审计
- **字段列表**：
  - audit_id | string | 必填, 唯一
  - trace_id | string(32 hex) | 必填, 索引
  - state_id | string | 外键 → DE-021
  - input | text | 必填
  - output | text | 必填
  - llm_judge_score | float | 必填
  - human_reviewed | bool | 默认 false
  - created_at | timestamp | 必填
- **来源标注**：[PRD:F-003.6] + [调研报告:S-019, R-09]

## DE-023 原始文档
- **实体描述**：research-tool 采集的原始数据
- **字段列表**：
  - raw_id | string | 必填, 唯一
  - source | enum(ARXIV, GITHUB, WIKI, ...) | 必填
  - url | string | 必填
  - content | text | 必填
  - collected_at | timestamp | 必填
  - minhash | string | 必填 | 64-bit hash
- **来源标注**：[PRD:F-004/F-006]

## DE-024 清洗后文档
- **实体描述**：去重 + LLM 过滤后的文档
- **字段列表**：
  - clean_id | string | 必填, 唯一
  - raw_id | string | 外键 → DE-023
  - relevance_score | float | 范围 0~1
  - language | enum(ZH, EN, OTHER) | 必填
  - cleaned_at | timestamp | 必填
- **来源标注**：[PRD:F-004/F-006] + [调研报告:S-008]

## DE-025 文档记录
- **实体描述**：入库后的统一 schema 文档
- **字段列表**：
  - doc_id | string | 必填, 唯一
  - clean_id | string | 外键 → DE-024
  - title | string | 必填
  - file_path | string | 必填
  - chunk_count | int | 必填
  - translated | bool | 默认 false
  - created_at | timestamp | 必填
- **来源标注**：[PRD:F-004]

## DE-026 FSRS 卡片表
- **实体描述**：FSRS 卡片主表（与 DE-015/DE-016 关联）
- **字段列表**：
  - card_id | string | 必填, 唯一
  - user_id | string | 必填, 索引
  - front | text | 必填
  - back | text | 必填
  - deck | string | 必填
  - created_at | timestamp | 必填
- **来源标注**：[PRD:F-003.2] + [调研报告:S-002]

## DE-027 知识图谱节点/边
- **实体描述**：L5 知识图谱（JSON-Lines 或 Neo4j）
- **字段列表**：
  - node_id | string | 必填, 唯一
  - node_type | enum(CONCEPT, ENTITY, RELATION) | 必填
  - label | string | 必填
  - properties | json | 必填
  - source_doc_id | string | 外键 → DE-025
- **来源标注**：[PRD:F-004] + [SA推断:依据=知识图谱惯例]

## DE-028 窗口实例（GUI）
- **实体描述**：桌面/浏览器窗口元数据
- **字段列表**：
  - window_id | string | 必填, 唯一
  - gui_type | enum(ELECTRON, TAURI, PYWEBVIEW) | 必填
  - context_isolation | bool | 默认 true
  - sandbox | bool | 默认 true
  - csp_policy | string | 必填
- **来源标注**：[PRD:F-005] + [调研报告:S-010]

## DE-029 research-tool 模块实例
- **实体描述**：6 模块的 Python 对象引用
- **字段列表**：
  - module_name | enum(collect, deepen, clean, extract, organize, backward) | 必填
  - version | string | 必填
  - pyproject_path | string | 必填
  - install_method | enum(pip_e, uv_lock) | 必填
- **来源标注**：[PRD:F-006] + [调研报告:S-018]

## DE-030 翻译后端
- **实体描述**：pdf2zh 多翻译后端状态
- **字段列表**：
  - backend_name | enum(DEEPSEEK, OLLAMA, LMSTUDIO) | 必填
  - qps_limit | int | 必填
  - failure_count | int | 默认 0
  - last_failure_at | timestamp | 可空
  - supported_languages | json | 必填
- **来源标注**：[PRD:F-007] + [调研报告:S-009]

## DE-031 RAG 上下文
- **实体描述**：RAG 检索产出的上下文
- **字段列表**：
  - ctx_id | string | 必填, 唯一
  - query_id | string | 必填
  - doc_ids | json | 必填
  - coverage_rate | float | 范围 0~1
  - round | int | 默认 1 | 重检索轮次
  - created_at | timestamp | 必填
- **来源标注**：[PRD:F-008]

## DE-032 RAG 评估
- **实体描述**：覆盖度 + 关键词命中率评估
- **字段列表**：
  - eval_id | string | 必填, 唯一
  - ctx_id | string | 外键 → DE-031
  - recall_estimate | float | 范围 0~1
  - keyword_hit_rate | float | 范围 0~1
  - needs_reretrieve | bool | 必填
  - decided_at | timestamp | 必填
- **来源标注**：[PRD:F-008]

## DE-033 会话列表
- **实体描述**：会话元数据
- **字段列表**：
  - session_id | string | 必填, 唯一
  - user_id | string | 必填, 索引
  - title | string | 必填
  - created_at | timestamp | 必填
  - last_active_at | timestamp | 必填
  - message_count | int | 默认 0
- **来源标注**：[PRD:F-010]

## DE-034 短期记忆
- **实体描述**：会话级摘要 + 近期原文
- **字段列表**：
  - memory_id | string | 必填, 唯一
  - session_id | string | 外键 → DE-033
  - summary | text | 必填
  - recent_messages | json | 必填 | 最近 K 条
  - token_count | int | 必填
  - updated_at | timestamp | 必填
- **来源标注**：[PRD:F-010] + [调研报告:S-011]

## DE-035 长期记忆
- **实体描述**：跨会话用户偏好/事实
- **字段列表**：
  - memory_id | string | 必填, 唯一
  - user_id | string | 必填, 索引
  - key | string | 必填
  - value | text | 必填
  - source_session_id | string | 可空
  - created_at | timestamp | 必填
- **来源标注**：[PRD:F-010] + [调研报告:S-011]

## DE-036 实体记忆
- **实体描述**：跨会话实体（sqlite-vec 向量索引）
- **字段列表**：
  - entity_id | string | 必填, 唯一
  - entity_name | string | 必填
  - entity_type | string | 必填
  - embedding | vector | 必填
  - attributes | json | 必填
- **来源标注**：[PRD:F-010] + [调研报告:S-011]

## DE-037 CLI Artifact
- **实体描述**：Python CLI 打包产物
- **字段列表**：
  - artifact_id | string | 必填, 唯一
  - tool | enum(cx_Freeze, Nuitka) | 必填
  - platform | enum(WIN, MAC, LINUX) | 必填
  - size_mb | float | 必填
  - built_at | timestamp | 必填
- **来源标注**：[PRD:F-011] + [调研报告:S-004] + [RI-NEW-3]

## DE-038 构建 Artifact
- **实体描述**：三平台总产物
- **字段列表**：
  - artifact_id | string | 必填, 唯一
  - type | enum(CLI, DESKTOP, WEB) | 必填
  - platform | enum(WIN, MAC, LINUX) | 必填
  - size_mb | float | 必填
  - ci_run_id | string | 必填
  - download_url | string | 必填
- **来源标注**：[PRD:F-011]

## DE-039 文件图谱
- **实体描述**：FILE_GRAPH 决策树（YAML/JSON）
- **字段列表**：
  - path | string | 必填, 唯一
  - category | enum(backend, frontend, docs, tests, ...) | 必填
  - owner_module | string | 必填
- **来源标注**：[PRD:F-012]

## DE-040 任务表
- **实体描述**：STATUS.md 数据源
- **字段列表**：
  - task_id | string | 必填, 唯一
  - status | enum(PENDING, RUNNING, DONE, FAILED) | 必填
  - description | text | 必填
  - started_at | timestamp | 可空
  - completed_at | timestamp | 可空
  - trace_id | string(32 hex) | 可空
- **来源标注**：[PRD:F-013]

## DE-041 本地资料源
- **实体描述**：本地资料目录配置
- **字段列表**：
  - source_id | string | 必填, 唯一
  - path | string | 必填
  - file_types | json | 必填 | [pdf, md, ...]
  - priority | int | 必填
  - enabled | bool | 必填
- **来源标注**：[PRD:F-015]

## DE-042 Anki 卡片草稿
- **实体描述**：从学习记录提取的 Q/A
- **字段列表**：
  - draft_id | string | 必填, 唯一
  - front | text | 必填
  - back | text | 必填
  - tags | json | 必填
  - source_lesson_id | string | 可空
- **来源标注**：[PRD:F-017]

## DE-043 Anki .apkg 产物
- **实体描述**：genanki 生成的 .apkg 文件
- **字段列表**：
  - apkg_id | string | 必填, 唯一
  - file_path | string | 必填
  - card_count | int | 必填
  - generated_at | timestamp | 必填
  - auto_imported | bool | 默认 false
- **来源标注**：[PRD:F-017] + [调研报告:S-014]

## DE-044 Obsidian Vault
- **实体描述**：Obsidian vault 目录与同步状态
- **字段列表**：
  - vault_id | string | 必填, 唯一
  - path | string | 必填
  - size_mb | float | 必填
  - last_commit_at | timestamp | 可空
  - conflict_count | int | 默认 0
- **来源标注**：[PRD:F-018] + [调研报告:S-015]

## DE-045 插件注册
- **实体描述**：CLI plugin 系统
- **字段列表**：
  - plugin_name | string | 必填, 唯一
  - version | string | 必填
  - entry_point | string | 必填
  - enabled | bool | 必填
- **来源标注**：[PRD:F-019]

---

## SA 洞察（数据层）

- **[数据孤岛]** DE-027（知识图谱）由 BP-009 创建，但 BP-013 检索时未明确查询路径（仅查 chunks 还是直查图谱）→ 需在 F-008 设计中明确双路径
- **[隐含依赖]** DE-020 字段 `llm_judge_scores` 是 JSON，存储多 LLM 法官独立打分 — 需约定 JSON schema 防止下游消费方解析失败
- **[推断膨胀预警]** DE-027 / DE-035 / DE-036 三个实体均涉及"记忆"，存在语义重叠风险 → 建议在 AR 阶段用状态机明确"事实/偏好/概念"三类数据归属

---

## 阶梯退出检查（L1）

- ① 每个 F 有完整 BP：是（20/20）
- ② 每个 BP 关联 ≥ 1 个 DE：是（DE-001~DE-045 全部被引用）
- ③ D1 = 100%，D3 = 45 个实体/预估 50 个 = 90%
