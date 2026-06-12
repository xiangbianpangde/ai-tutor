# 系统架构图-数据视图 — AITutor V3.1

> 视角：DBA / 数据工程师
> 数据载体：SQLite + ChromaDB + 文件 + 内存

---

## 一、存储拓扑

```
┌── 关系数据 (SQLite: data/tutor.db) ─────────────────────┐
│  表：                                                    │
│   ├─ config               (DE-001)                      │
│   ├─ service_instance     (DE-002)                      │
│   ├─ migration_log        (DE-003)                      │
│   ├─ middleware_status    (DE-004)                      │
│   ├─ session              (DE-006)                      │
│   ├─ cache_entry          (DE-007) [可选: Redis 镜像]   │
│   ├─ monitor_log          (DE-008)                      │
│   ├─ pipeline_state       (DE-009)                      │
│   ├─ rag_state            (DE-010)                      │
│   ├─ feynman 集合         (DE-011~014)                  │
│   ├─ fsrs_cards           (DE-015~016)                  │
│   ├─ learner_profile      (DE-017~018)                  │
│   ├─ rest_log             (DE-019)                      │
│   ├─ nli_triple/nli_score (DE-020~021)                  │
│   ├─ chunk_audit          (DE-023~024)                  │
│   ├─ documents/chunks     (DE-025~026) [meta 元数据]    │
│   ├─ long_term_memory     (DE-032)                      │
│   ├─ artifact / build_log (DE-033~034)                  │
│   ├─ file_tree            (DE-035)                      │
│   ├─ setup                (DE-036)                      │
│   ├─ local_lib_index      (DE-037)                      │
│   ├─ artifact_config      (DE-038)                      │
│   ├─ doctor_report        (DE-039)                      │
│   ├─ web_session          (DE-040)                      │
│   ├─ redline_report  ⭐V3.1  (DE-046)                  │
│   ├─ ci_run           ⭐V3.1  (DE-047)                  │
│   └─ tool_version_lock ⭐V3.1  (DE-048)                 │
└──────────────────────────────────────────────────────────┘

┌── 向量数据 (ChromaDB: data/chroma/) ────────────────────┐
│  Collection:                                              │
│   ├─ pdf_chunks       (DE-026 embedding)                │
│   ├─ local_lib_chunks (DE-037 embedding)                │
│   └─ web_chunks       (重检索兜底)                       │
└──────────────────────────────────────────────────────────┘

┌── 文件 ─────────────────────────────────────────────────┐
│  data/inbox/*.pdf         (DE-025 翻译前)                │
│  data/artifacts/*.{exe,dmg,AppImage,whl} (DE-033)        │
│  data/obsidian-vault/     (DE-037 双向同步源)            │
│  meta/FILE_GRAPH.md       (DE-035)                       │
│  api/openapi.yaml         (Redocly 输入)                 │
│  doc/runbooks/redlines-fix.md (修复手册)                 │
└──────────────────────────────────────────────────────────┘

┌── 内存 / 短期 ──────────────────────────────────────────┐
│  WebSocket pool  (DE-005)                                │
│  Pipeline state (DE-009 status=RUNNING)                  │
│  RAG state      (DE-010 round≤3)                         │
│  EventBus queue (状态机/兜底审计)                         │
└──────────────────────────────────────────────────────────┘
```

来源标注：[SA:DE-001~DE-048] + [SA:BR-006/008/016/029/032]

---

## 二、数据一致性策略

| 数据对 | 关系 | 一致性 | 处理 |
|--------|------|--------|------|
| session ↔ long_term_memory | 1:N | 最终一致 | 关键事实异步提取 |
| cache_entry ↔ pipeline_state | 1:N | 强一致(写后读) | 事务封装 |
| rag_state ↔ nli_score | 1:N | 强一致 | 同步写 |
| ci_run ↔ redline_report | 1:N | 强一致 | 事务封装 |
| file_tree ↔ 实际文件 | 1:1 | 弱校验 | 扫描 + warn only |
| documents ↔ chroma chunks | 1:N | 最终一致 | 写后异步 embed |
| web_session ↔ session | N:1 | 共享 | 同一 user_id |

来源标注：[TD推断:依据=本地单体 + 异步/同步混合] + [SA:BR-027 抖动防雪崩]

---

## 三、数据生命周期

| 数据 | 写入 | 读取 | TTL | 淘汰 |
|------|------|------|-----|------|
| monitor_log | 实时 | 即席 | 30d(滚动) | 定期清理 |
| cache_entry | 写入时 | 命中 | expires_at ±20% | 自动 |
| rag_state | 检索时 | 重检索 | round=3 即结束 | 立即 |
| pipeline_state | 编排时 | 步骤间 | 步骤完成即归档 | 立即 |
| long_term_memory | 关键事实 | 会话引用 | 无 | LRU 10% |
| ci_run / redline_report | CI 触发 | PR review | 90d | 滚动 |
| build_log | 打包时 | 失败分析 | 永久(只读) | 归档 |
| doctor_report | 手动 | 即席 | 最近 10 次 | FIFO |

来源标注：[TD推断:依据=DE-008 字段 ts + 反例 CE-007 数据孤岛] + [SA:BR-029 LRU]

---

## 四、备份与迁移

| 数据 | 备份 | 迁移 |
|------|------|------|
| SQLite | 启动前快照 + 用户手动 | `migrate_v1_to_v2()` 自动 |
| ChromaDB | 与 SQLite 同步备份 | 重新 embed (耗时) |
| 文件 | 用户手动 | git sync / 文件复制 |
| 配置 | dotenv 模板 | .env 重新填写 |

来源标注：[SA:BP-001 步骤 3 向后兼容] + [SA:EX-001]
