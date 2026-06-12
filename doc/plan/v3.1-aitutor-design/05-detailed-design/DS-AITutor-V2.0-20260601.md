# 数据结构设计 — AITutor V2.0

> 角色：DD-001 | 日期：2026-06-01 | 上游：[AR:TS] 23 选型中的数据存储

---

## DS-001 SQLite 主库（tutor.db）
- **关联技术选型**：[AR:TS-005] SQLite + WAL
- **存储类型**：关系型数据库（嵌入式）
- **存储名称**：`tutor.db`（WAL 模式 + .bak.YYYYMMDD 备份）
- **包含表**（与 AR 一致）：
  - `learner_profile`（user_id, level, accuracy_7d, last_change_at, hysteresis_state）
  - `fsrs_cards`（card_id, user_id, due, stability, difficulty, grade_state, last_grade_at）
  - `claim_set`（claim_id, response_id, text, span, source_doc_id）
  - `hallucination_scores`（response_id, claim_id, nli_score, slm_score, llm_score, final, trace_id, created_at）
  - `documents`（doc_id, source, path, content_hash, title, lang, status, created_at）
  - `research_cache`（cache_id, query_hash, payload, expires_at）
  - `rag_contexts`（ctx_id, query_hash, top1_doc_id, sources_json, halu_overall, quality_score, created_at）
  - `cache`（key, value_blob, expires_at, semantic_top1_doc_id）
  - `session_meta`（session_id, user_id, title, created_at, last_active_at, message_count, status）
  - `memories`（fact_id, user_id, text, importance, created_at, embedding BLOB）
  - `state_machine`（state_id, version, table_json, human_reviewed, created_at）
  - `audit_log`（audit_id, trace_id, op, input_hash, output_hash, llm_judge_score, user_id, created_at）
  - `tasks`（task_id, kind, state, progress, error_json, payload_json, created_at, updated_at）
  - `plugin_registry`（plugin_name, version, hash, installed_at, enabled）
  - `apkg_artifacts`（artifact_id, session_id, path, cards_count, anki_pushed, created_at）
  - `pipeline_tasks`（task_id, source, path, state, progress, error_json, content_hash）
  - `local_sources`（path, added_at）
  - `transition_proposals`（proposal_id, from_state, to_state, event, weight, human_reviewed, created_at）
- **主键**：UUID（除 learner_profile/fsrs_cards/session_meta/memories 复合主键含 user_id）
- **唯一索引**：
  - `idx_learner_user_id` UNIQUE on learner_profile(user_id)
  - `idx_cards_user_card` UNIQUE on fsrs_cards(user_id, card_id)
  - `idx_doc_hash` UNIQUE on documents(content_hash)
  - `idx_cache_key` UNIQUE on cache(key)
- **外键**：
  - `claim_set.response_id → rag_contexts.ctx_id`（ON DELETE CASCADE）
  - `hallucination_scores.claim_id → claim_set.claim_id`（ON DELETE CASCADE）
  - `fsrs_cards.user_id → learner_profile.user_id`（ON DELETE CASCADE）
  - `memories.user_id → learner_profile.user_id`（ON DELETE CASCADE）
  - `session_meta.user_id → learner_profile.user_id`（ON DELETE CASCADE）
- **约束**：
  - learner_profile.accuracy_7d ∈ [0, 1]
  - fsrs_cards.due ISO8601
  - cache.expires_at ISO8601
  - audit_log.op NOT NULL（强制写）
- **数据量预估**：
  - 初始 1 用户 ~ 5 文档/任务 / 100 评分 / 10 会话 / 100 记忆
  - 增长 ~5 文档/天 / 50 评分/天 / 1 会话/天
  - 峰值 5000 文档 / 50000 评分 / 100 会话
- **分片策略**：不分片（单用户单进程）
- **WAL 设置**：`PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;`
- **来源标注**：[AR:TS-005] + [AR:BR-039] + [AR:AC-AG-002~AG-010]

---

## DS-002 sqlite-vec 向量索引
- **关联技术选型**：[AR:TS-006] sqlite-vec 0.1.3+
- **存储类型**：SQLite 扩展（嵌入式向量）
- **存储名称**：`vec_documents`（文档向量）/ `vec_memories`（长期记忆向量）
- **表结构**：
  - `vec_documents(vec BLOB(384-1024 维), doc_id TEXT, chunk_id TEXT, model_version TEXT)`
  - `vec_memories(vec BLOB, fact_id TEXT, user_id TEXT, model_version TEXT)`
- **主键**：`rowid`（sqlite-vec 内置）
- **唯一索引**：`idx_vec_doc` UNIQUE on vec_documents(doc_id, chunk_id)
- **外键**：doc_id → documents.doc_id / fact_id → memories.fact_id
- **约束**：vec 维度与 model_version 强绑定（嵌入模型切换需重新生成）
- **数据量预估**：
  - 初始 ~5000 向量（5000 文档分块）
  - 增长 ~200 向量/天
  - 峰值 50000 向量
- **分片策略**：不分片（单文件）；V-3 引入 ChromaDB 0.5.x 时通过 VectorIndex 抽象层切换
- **API 抽象层**（DD推断:基于 [AR洞察-004/007]）：`VectorIndex` Protocol 封装 `add/query/delete`，V-1 可切换实现
- **来源标注**：[AR:TS-006] + [调研报告:RI-008] + [AR洞察-004/007]

---

## DS-003 Redis（可选缓存后端）
- **关联技术选型**：[AR:TS-007] Redis 7.4.x（可选后端，默认 SQLite LRU）
- **存储类型**：分布式键值缓存
- **存储名称**：`at:` 前缀的键空间
- **键规范**：
  - `at:cache:query_hash:{hash}` → value_blob（TTL 1h）
  - `at:cache:semantic:{top1_doc_id}:{query_hash}` → value_blob（TTL 24h，BR-031 二次查询延迟降 ≥50%）
  - `at:lock:fsm:{state_id}` → token（TTL 5s，单 FSM 写锁）
- **值类型**：JSON 字符串 / MessagePack 二进制
- **主键**：键名即主键
- **唯一索引**：N/A（Redis 不支持）
- **外键**：N/A
- **约束**：TTL ±20% 抖动（防雪崩）
- **数据量预估**：
  - 初始 ~1000 键
  - 增长 ~500 键/天
  - 峰值 10000 键（V-3）
- **分片策略**：单实例 V-2；V-3 主从+哨兵
- **来源标注**：[AR:TS-007] + [AR:DE-007] + [AR:BR-031] + [ADR-007]

---

## DS-004 SQLite LRU 缓存（默认）
- **关联技术选型**：[AR:TS-005] SQLite（同 DS-001 复用）
- **存储类型**：关系型（兼作 LRU）
- **存储名称**：`cache` 表（同 DS-001 内）
- **字段**：`key TEXT PRIMARY KEY, value_blob BLOB, expires_at ISO8601, semantic_top1_doc_id TEXT, last_access_at ISO8601`
- **LRU 策略**：`DELETE FROM cache WHERE key IN (SELECT key FROM cache ORDER BY last_access_at ASC LIMIT 1000)` 当总数 > 10000 触发
- **来源标注**：[AR:TS-005] + [AR:DE-007]

---

## DS-005 文件存储 data/documents/
- **关联技术选型**：[AR:TS-005] 本地文件系统
- **存储类型**：文件系统
- **存储名称**：`data/documents/*.md`（PDF 解析后）+ `data/research-cache/`（原始）
- **文件命名**：`{content_hash[:16]}_{title_slug}.md`（防冲突）
- **主键**：content_hash 唯一
- **唯一索引**：N/A
- **外键**：N/A
- **约束**：UTF-8 编码；最大 10MB/文件
- **数据量预估**：
  - 初始 ~100 文件
  - 增长 ~5 文件/天
  - 峰值 5000 文件（~50GB）
- **分片策略**：按月份分目录 `data/documents/YYYY-MM/`
- **来源标注**：[AR:TS-005] + [AR:DE-024]

---

## DS-006 NDJSON 知识图谱
- **关联技术选型**：[AR:TS-005] 文件系统
- **存储类型**：文件
- **存储名称**：`data/knowledge_graph/*.jsonl`
- **格式**：每行一个 JSON 对象 `{entity, relation, target, weight, source_doc_id, created_at}`
- **主键**：line_offset
- **约束**：每行 ≤1KB
- **数据量预估**：~10000 行（5000 文档，每文档 2 实体）
- **分片策略**：按实体类型分文件 `entities.jsonl` / `relations.jsonl`
- **来源标注**：[AR:DE-027]

---

## DS-007 STATUS.md（原子写）
- **关联技术选型**：[AR:TS-005] + [AR洞察-NLI]
- **存储类型**：文件（带原子写保护）
- **存储名称**：`data/STATUS.md`
- **格式**：Markdown 文本
- **写入策略**：
  - 写入临时文件 `data/.STATUS.md.tmp`
  - `os.replace()` 原子重命名
  - 写入失败 → 阻断推送 + 写失败阻断兜底
- **约束**：单文件 ≤100KB
- **来源标注**：[AR:DE-040] + [SA:BR-021]

---

## DS-008 NLI 模型缓存
- **关联技术选型**：[AR:TS-013] optimum+onnxruntime
- **存储类型**：文件系统
- **存储名称**：`data/nli_cache/`
- **内容**：
  - `model.onnx`（DeBERTa-v3-large-mnli ONNX 量化）
  - `config.json`
  - `tokenizer.json`
  - `version.lock`（记录 commit hash）
- **大小**：~400MB（ONNX 量化后）
- **约束**：版本锁定（HF commit hash）；启动校验
- **来源标注**：[AR:TS-013] + [调研报告:NLI-13]

---

## DS-009 LangGraph Store
- **关联技术选型**：[AR:TS-010] LangGraph 1.0
- **存储类型**：嵌入式 KV（SQLite 后端）
- **存储名称**：LangGraph Store 内部 SQLite
- **Schema**：LangGraph 内置
  - `store` 表（key TEXT, value BLOB, namespace TEXT, created_at, updated_at）
  - `writes` 表（事务日志，append-only）
- **主键**：(namespace, key) 复合
- **索引**：`idx_ns_key` UNIQUE on (namespace, key)
- **约束**：namespace ∈ ["memories", "summaries", "facts"]
- **数据量预估**：~10000 项
- **分片策略**：单文件
- **来源标注**：[AR:TS-010] + [调研报告:RI-008] + [调研报告:MEM-48/05]
