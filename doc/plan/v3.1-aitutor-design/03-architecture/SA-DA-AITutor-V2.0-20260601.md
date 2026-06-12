# 系统架构图 - 数据视图 — AITutor V2.0

> 数据存储介质、生命周期、一致性

## 1. 存储介质总览

```
┌─────────────── 内存层 (in-process) ─────────────────┐
│  ├─ Cache (SQLite/Redis, semantic 0.85~0.95)        │
│  ├─ Session.short_term (ConversationSummaryBuffer)   │
│  ├─ Pipeline 状态 (DE-009 step_sequence)            │
│  └─ WebSocket 连接池 (DE-005)                        │
├──────────────────────────────────────────────────────┤
│  ↓ 持久化
┌─────────────── SQLite (data/tutor.db, WAL 模式) ────┐
│  业务表:                                              │
│  ├─ config (DE-001)                                  │
│  ├─ services (DE-002)                                │
│  ├─ middleware_registry (DE-004)                     │
│  ├─ ws_connections (DE-005)                          │
│  ├─ session_meta (DE-006/DE-033)                     │
│  ├─ cache_entries (DE-007)                           │
│  ├─ monitor_events (DE-008)                          │
│  ├─ pipeline_configs (DE-009)                        │
│  ├─ rag_configs (DE-010)                             │
│  ├─ concepts (DE-011)                                │
│  ├─ feynman_questions (DE-012)                        │
│  ├─ user_answers (DE-013)                            │
│  ├─ grading_reports (DE-014)                         │
│  ├─ fsrs_cards (DE-015/DE-026)                       │
│  ├─ fsrs_schedules (DE-016)                          │
│  ├─ accuracy_window (DE-017)                         │
│  ├─ learner_profile (DE-018)                         │
│  ├─ claim_set (DE-019)                               │
│  ├─ hallucination_scores (DE-020)                    │
│  ├─ state_machine (DE-021)                           │
│  ├─ audit_log (DE-022)                               │
│  ├─ documents (DE-023/DE-024/DE-025)                 │
│  ├─ translation_backends (DE-030)                    │
│  ├─ rag_contexts (DE-031/DE-032)                     │
│  ├─ short_term_memories (DE-034)                     │
│  ├─ long_term_memories (DE-035)                      │
│  ├─ entity_memories (DE-036)                         │
│  ├─ tasks (DE-040)                                   │
│  ├─ local_sources (DE-041)                           │
│  ├─ anki_drafts (DE-042) / apkg_artifacts (DE-043)   │
│  └─ plugin_registry (DE-045)                         │
│                                                       │
│  扩展:                                                │
│  └─ sqlite-vec (实体向量索引, DE-036)                 │
├──────────────────────────────────────────────────────┤
│  ↓ 文本导出
┌─────────────── 文件系统 ─────────────────────────────┐
│  ├─ documents/*.md (PDF 解析后)                      │
│  ├─ logs/YYYY-MM-DD/structlog.jsonl                  │
│  ├─ obsidian-vault/ (DE-044)                         │
│  ├─ research-cache/ (DE-023 原始)                    │
│  └─ STATUS.md (DE-040 渲染)                          │
├──────────────────────────────────────────────────────┤
│  ↓ 知识图谱存储
┌─────────────── L5 知识图谱 (JSON-Lines / Neo4j) ────┐
│  └─ knowledge_graph/*.jsonl (DE-027)                 │
│     (节点 = CONCEPT/ENTITY/RELATION, 含 source 链)  │
└──────────────────────────────────────────────────────┘
```

## 2. 一致性策略

| 实体 | 一致性 | 备份 | 来源 |
|------|--------|------|------|
| tutor.db 业务表 | 强一致 (WAL + 事务) | 启动前 .bak | [SA:BR-039] |
| audit_log | 强一致 (写失败阻断兜底) | 不清理 | [SA:BR-021] |
| Cache | 最终一致 (异步写回) | 失效不阻塞 | [SA:EX-033] |
| 知识图谱 (L5) | 最终一致 (异步抽取) | 用户导出 | [SA:EX-023] |
| STATUS.md | 强一致 (原子 rename) | 单文件覆写 | [SA:BP-018] |
| 长期记忆 (DE-035) | 强一致 (JSON 持久化) | 实时 | [SA:BR-010] |
| fsrs_cards | 强一致 (WAL + 乐观锁) | db 内 | [SA:EX-012] |

## 3. 关键索引

| 索引 | 表 | 列 | 用途 | 来源 |
|------|------|------|------|------|
| idx_trace_id | monitor_events / audit_log / hallucination_scores | trace_id (32 hex) | 全链路追踪 | [SA:BR-004] |
| idx_user_id | user_answers / fsrs_cards / long_term_memories | user_id | 用户隔离 (CE-012) | [SA:CE-012] |
| idx_next_due | fsrs_schedules | next_due | FSRS 调度扫描 | [SA:BP-004] |
| vec_idx | entity_memories (sqlite-vec) | embedding | 实体检索 | [SA:DE-036] |
| content_hash | documents | sha256 | 并发入库 UPSERT (CE-008) | [SA:CE-008] |

## 4. 数据生命周期

```
采集 (raw, 30天) → 清洗 (clean, 永久) → 入库 (doc, 永久) → 抽取 (kg, 永久) → 检索消费
       ↓
  失败 / 低相关 → 删除 (1 天后清理)

cache 写回 → 24h TTL + ±20% 抖动 (CE-002) → 自动失效

audit_log → 不清理 (合规 R-09)

FSRS 卡片 → 90 天未复习 → 归档到 fsrs_archive 表 (TD推断)
```
