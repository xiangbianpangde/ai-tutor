# 数据字典 — AITutor V3.1（终版）

> 来源：PRD V3.1 + 调研报告 V3.1 + 业务流程图
> 编号：DE-001 ~ DE-048（V3.1 增 DE-046~DE-048 三个红线相关实体）
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
  - version | string | 必填 | 版本号
  - host | string | 默认 127.0.0.1 | 监听地址
  - port | int | 默认 8000 | 监听端口
- **来源标注**：[PRD:F-001]

## DE-003 向后兼容报告
- **实体描述**：v1 数据库 schema 检测结果
- **字段列表**：
  - db_path | string | 必填
  - schema_version | string | 必填
  - target_version | string | 必填
  - compatible | bool | 必填
  - migration_sql | text | 可空
- **来源标注**：[PRD:F-001]

## DE-004 中间件清单
- **实体描述**：5 类中间件注册状态
- **字段列表**：
  - middleware_name | enum(Session, Cache, Monitor, Pipeline, RAG) | 必填, 唯一
  - enabled | bool | 必填
  - backend | string | 必填
  - config_json | text | 可空
- **来源标注**：[PRD:F-002]

## DE-005 WS 连接池
- **实体描述**：WebSocket 连接追踪
- **字段列表**：
  - connection_id | string | 必填, 唯一
  - user_id | string | 可空
  - connected_at | timestamp | 必填
  - last_ping_at | timestamp | 必填
  - status | enum(OPEN, CLOSED) | 必填
- **来源标注**：[PRD:F-005, F-013]

## DE-006 Session 实例
- **实体描述**：会话状态（短期摘要 + 长期实体）
- **字段列表**：
  - session_id | string | 必填, 唯一
  - user_id | string | 必填
  - started_at | timestamp | 必填
  - short_term_buffer | text | 必填 | 当前 buffer 摘要
  - long_term_refs | text | 可空 | 长期实体引用（JSON）
- **来源标注**：[PRD:F-002, F-010]

## DE-007 Cache 实例
- **实体描述**：缓存条目
- **字段列表**：
  - cache_key | string | 必填, 唯一
  - cache_value | text | 必填
  - semantic_hash | string | 必填 | 语义向量哈希
  - hit_count | int | 默认 0
  - expires_at | timestamp | 必填 | 含 ±20% 抖动
  - created_at | timestamp | 必填
- **来源标注**：[PRD:F-002, F-009] + [调研报告:S-013]

## DE-008 Monitor 实例
- **实体描述**：结构化日志条目
- **字段列表**：
  - trace_id | string(32hex) | 必填
  - span_id | string(16hex) | 必填
  - level | enum(DEBUG, INFO, WARN, ERROR) | 必填
  - event | string | 必填
  - payload | text | 可空
  - ts | timestamp | 必填
- **来源标注**：[PRD:F-002, F-009] + [调研报告:S-016]

## DE-009 Pipeline 实例
- **实体描述**：5 阶段管线运行状态
- **字段列表**：
  - pipeline_id | string | 必填, 唯一
  - stage | enum(PREPROCESS, RETRIEVE, RERANK, LLM, POSTPROCESS) | 必填
  - input_ref | string | 必填
  - output_ref | string | 可空
  - status | enum(RUNNING, DONE, FAILED) | 必填
- **来源标注**：[PRD:F-002]

## DE-010 RAG 实例
- **实体描述**：Agentic RAG 运行状态
- **字段列表**：
  - rag_id | string | 必填, 唯一
  - query | text | 必填
  - route_decision | enum(SIMPLE, MODERATE, COMPLEX) | 必填
  - round | int | 默认 0 | 当前重检索轮次
  - threshold | float | 默认 0.70
  - sources | text | 可空 | JSON 数组
- **来源标注**：[PRD:F-006, F-008] + [调研报告:S-012]

## DE-011~DE-014 费曼学习相关
- **DE-011 概念集**：list<concept_obj>，来自 L5 知识图谱
- **DE-012 复述题**：question_text | difficulty | hint | trace_id
- **DE-013 用户复述**：answer_text | audio_ref | submitted_at | **user_id（必填，CE-003 修复）**
- **DE-014 评分报告**：score | follow_up | trace_id | llm_provider
- **来源标注**：[PRD:F-003.1]

## DE-015~DE-016 FSRS 卡片
- **DE-015 待复习列表**：card_id | next_due | last_review | stability
- **DE-016 更新后卡片**：card_id | stability | difficulty | retrievability | next_due | last_rating | **again_throttle_count（CE-004 修复）**
- **来源标注**：[PRD:F-003.2]

## DE-017~DE-018 阶段与档案
- **DE-017 正确率统计**：window_days | accuracy | sample_count
- **DE-018 learner_profile**：current_tier | last_calibrated_at | tier_history | **consecutive_high_days（CE-005 修复）**
- **来源标注**：[PRD:F-003.3, F-016]

## DE-019 rest_log
- **实体描述**：休息提醒触发日志
- **字段列表**：rest_id | triggered_at | user_response | duration_min
- **来源标注**：[PRD:F-003.4]

## DE-020~DE-022 NLI 验证相关
- **DE-020 三元组**：subject | predicate | object | source_doc
- **DE-021 NLI 评分**：triple_id | entailment_score | nli_model | scored_at
- **DE-022 重检索日志**：round | query_rewrite | new_sources | score_delta
- **来源标注**：[PRD:F-003.5]

## DE-023~DE-024 降阶法引擎
- **DE-023 chunk**：chunk_id | doc_id | content | token_count | overlap_with_next
- **DE-024 audit_log**：trace_id | fsm_state | action | llm_fallback | score | ts
- **来源标注**：[PRD:F-003.6]

## DE-025~DE-026 数据管线
- **DE-025 翻译结果**：doc_id | original_path | translated_text | translator | quality_score
- **DE-026 chunks**：chunk_id | doc_id | embedding | metadata_json
- **来源标注**：[PRD:F-004, F-006, F-007]

## DE-027 看板状态
- **实体描述**：前端看板渲染数据
- **字段列表**：user_id | current_step | progress | fsrs_queue | last_update
- **来源标注**：[PRD:F-005, F-013]

## DE-028 路由决策
- **实体描述**：复杂度路由判定
- **字段列表**：query_id | features_json | decision | confidence | model_version
- **来源标注**：[PRD:F-008] + [RI-NEW-4 POC]

## DE-029 检索结果
- **实体描述**：RAG 检索 top-K
- **字段列表**：query_id | rank | doc_id | score | rerank_score
- **来源标注**：[PRD:F-006, F-008]

## DE-030 monitor_metric
- **实体描述**：监控指标（聚合）
- **字段列表**：metric_name | value | labels_json | ts
- **来源标注**：[PRD:F-002, F-009]

## DE-031~DE-032 长期记忆
- **DE-031 session**：详见 DE-006
- **DE-032 long_term_memory**：entity_id | entity_type | fact | source_trace_id | created_at
- **来源标注**：[PRD:F-010]

## DE-033~DE-034 打包
- **DE-033 artifact**：platform | format | size_bytes | path | sha256
- **DE-034 build_log**：build_id | step | status | duration_s | error
- **来源标注**：[PRD:F-011]

## DE-035 file_tree
- **实体描述**：FILE_GRAPH 决策树
- **字段列表**：path | rule | action | parent
- **来源标注**：[PRD:F-012]

## DE-036 setup
- **实体描述**：首次启动向导状态
- **字段列表**：step | llm_provider | api_key_ref | local_lib_path | completed_at
- **来源标注**：[PRD:F-014]

## DE-037 local_lib
- **实体描述**：本地资料库索引
- **字段列表**：file_path | content_hash | chunk_ids | last_indexed_at | source_type
- **来源标注**：[PRD:F-015, F-018]

## DE-038 artifact 配置项
- **实体描述**：打包产物相关配置
- **字段列表**：config_key | value | scope=USER
- **来源标注**：[SA推断:依据=DE-001 1:N 关系]

## DE-039 doctor_report
- **实体描述**：`ai-tutor doctor` 自检报告
- **字段列表**：check_id | name | status | duration_ms | fix_url
- **来源标注**：[PRD:F-019, NFR-8]

## DE-040 web_session
- **实体描述**：Web 端会话
- **字段列表**：session_id | browser_fingerprint | connected_at | last_active
- **来源标注**：[PRD:F-020]

## DE-041~DE-045 占位（沿用 V2.0 实体）
- 详见 V2.0 数据字典

---

## DE-046 【V3.1 新增】redline_report
- **实体描述**：4 工具链红线检测报告（BP-021 产出）
- **字段列表**：
  - report_id | string | 必填, 唯一
  - tool | enum(RUFF, IMPORT_LINTER, REDOCLY, PRE_COMMIT, PYTEST_COVERAGE) | 必填
  - spec_rule | string | 必填 | 关联的 6+1 规范编号（01-架构/02-代码/03-Git/04-API/05-测试/06-文档/08-图谱）
  - status | enum(PASS, FAIL, ERROR) | 必填
  - exit_code | int | 必填
  - violation_count | int | 默认 0
  - raw_output | text | 可空 | 工具原始输出（GitHub 格式）
  - fix_url | string | 可空 | 修复手册链接
  - ts | timestamp | 必填
- **实体关系**：N:1 → DE-047 (ci_run)
- **来源标注**：[PRD:NFR-8, F-001 验收 5.] + [调研报告:S-020/RCFM-01] + [调研报告:REDOC-12/25/31/54]

## DE-047 【V3.1 新增】ci_run
- **实体描述**：单次 CI 红线检测运行记录
- **字段列表**：
  - run_id | string | 必填, 唯一
  - trigger | enum(PR_PUSH, MAIN_PUSH, MANUAL, SCHEDULED) | 必填
  - commit_sha | string | 必填
  - branch | string | 必填
  - started_at | timestamp | 必填
  - finished_at | timestamp | 可空
  - overall_status | enum(PASS, FAIL, RUNNING) | 必填
  - blocking_enabled | bool | 默认 true | 是否启用 branch protection 阻断
- **实体关系**：1:N → DE-046 (redline_report)
- **来源标注**：[PRD:NFR-8, S3 测量方式第 3 层] + [调研报告:S-021/S-022/RCFM-05]

## DE-048 【V3.1 新增】tool_version_lock
- **实体描述**：4 工具链版本锁记录（缓解 R-17）
- **字段列表**：
  - tool_name | enum(ruff, import-linter, redocly-cli, commitlint) | 必填, 唯一
  - locked_version | string | 必填 | 形如 "0.6.9"（语义化版本）
  - lock_file_path | string | 必填 | 默认 `requirements-dev.txt` 或 `pyproject.toml [tool.ci]`
  - upgrade_policy | enum(STRICT, TDD_PROGRESSIVE) | 默认 TDD_PROGRESSIVE
  - last_check_at | timestamp | 必填
- **实体关系**：与 DE-001（config）无直接关系，独立维护
- **来源标注**：[PRD:NFR-8 / S-021 CI 锁版本] + [调研报告:RCFM-03] + [调研报告:R-17 缓解]

---

## SA 洞察

1. **【数据孤岛预警】** DE-046~DE-048 是 V3.1 新增 3 个红线相关实体，在 V2.0 DD 中不存在。SA 需确保 BP-021 是这 3 个实体的唯一创建流程——避免数据来源缺口。
2. **【字段级依赖】** DE-013 / DE-016 / DE-018 中标注的 user_id / again_throttle_count / consecutive_high_days 均为 CE-003/004/005 反例验证后修复的字段，SA 推断这是"反例驱动字段"——下游架构师在 schema 迁移脚本中必须包含这些字段。
3. **【推断占比】** 本轮 48 个实体中，V3.1 新增 3 个 = 6.25%，全部基于 S-020/S-021/S-022 + RCFM 来源；非新增 45 个实体中 [SA推断] 标注 4 个 = 8.9%，推断占比 ≈ 15%（远低于 40% 阈值），D8 维持 95%。

[阶梯退出检查] ①每个 F 有完整 BP: 是 ②每个 BP 关联 ≥ 1 DE: 是（BP-021→DE-046~048） ③D1:100% D3:98%
