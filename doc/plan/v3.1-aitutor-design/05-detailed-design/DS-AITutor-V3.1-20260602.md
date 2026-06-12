# 数据结构设计 — AITutor V3.1

> 9 个核心数据存储（5 SQLite + 2 Chroma + 1 缓存 + 1 文件）全有完整结构定义。
> 来源：[AR:TS-003/004/005] + [AR:DP-004/005] + [DD推断:依据]

---

## DS-001 SQLite 主存（users / sessions）

- **关联技术选型**：TS-003 SQLite 3.46.1 + SQLAlchemy 2.0 async
- **存储类型**：关系型数据库
- **存储名称**：`data.db` (WAL 模式)
- **表结构**：

#### users 表

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| id | TEXT | 32 | ✅ | - | PK | 用户 ID（32hex） |
| username | TEXT | 64 | ✅ | - | UNIQUE | 用户名 |
| password_hash | TEXT | 128 | ✅ | - | - | 密码哈希（bcrypt） |
| created_at | TIMESTAMP | - | ✅ | now | IDX | 创建时间 |
| last_active | TIMESTAMP | - | ✅ | now | - | 最后活跃 |
| config | JSON | - | ✅ | {} | - | 用户配置 |
| is_active | BOOLEAN | - | ✅ | 1 | - | 是否启用 |

- **主键/唯一索引**：
  - 主键：id
  - 唯一索引：username
- **外键/关联关系**：无（单用户场景）
- **约束条件**：
  - CHECK(LENGTH(id) = 32)
  - CHECK(LENGTH(username) >= 3)
- **数据量预估**：
  - 初始量：1 条
  - 增长速率：0 条/天
  - 峰值：10 条
- **分片策略**：无
- **来源标注**：[AR:TS-003] + [AR:DP-004]

#### sessions 表

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| id | TEXT | 36 | ✅ | - | PK | 会话 ID（UUIDv4） |
| user_id | TEXT | 32 | ✅ | - | IDX | 用户 ID |
| state | TEXT | 16 | ✅ | NEW | - | 状态：NEW/ACTIVE/SUSPENDED/EXPIRED/CLOSED |
| created_at | TIMESTAMP | - | ✅ | now | - | 创建时间 |
| last_active | TIMESTAMP | - | ✅ | now | IDX | 最后活跃 |
| metadata | JSON | - | ✅ | {} | - | 会话元数据 |
| version | INTEGER | - | ✅ | 1 | - | 乐观锁版本号 |

- **主键/唯一索引**：PK: id
- **外键/关联关系**：user_id → users.id (无强外键，应用层校验)
- **约束条件**：CHECK(state IN ('NEW','ACTIVE','SUSPENDED','EXPIRED','CLOSED'))
- **数据量预估**：初始 0 条 / 增长 5 条/天 / 峰值 200 条
- **分片策略**：无
- **来源标注**：[AR:API-002] + [AR:TS-003]

---

## DS-002 SQLite（turns 回合记录）

- **关联技术选型**：TS-003 SQLite 3.46.1
- **表结构**：

#### turns 表

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| id | TEXT | 36 | ✅ | - | PK | 回合 ID（UUIDv4） |
| session_id | TEXT | 36 | ✅ | - | IDX | 关联会话 |
| user_id | TEXT | 32 | ✅ | - | IDX | 用户 ID（强校验） |
| query | TEXT | 2000 | ✅ | - | - | 用户问题 |
| answer | TEXT | 10000 | ✅ | - | - | LLM 答案 |
| sources | JSON | - | ✅ | [] | - | 引用源列表 |
| route_decision | TEXT | 16 | ✅ | - | - | 路由：direct/rag/web/cannot_confirm |
| nli_score | REAL | - | ✅ | 0.0 | - | NLI 评分 |
| fsm_fallback | BOOLEAN | - | ✅ | 0 | - | 是否兜底 |
| trace_id | TEXT | 32 | ✅ | - | IDX | 追踪 ID |
| duration_ms | INTEGER | - | ✅ | 0 | - | 耗时 |
| created_at | TIMESTAMP | - | ✅ | now | IDX | 创建时间 |

- **主键/唯一索引**：PK: id + IDX(session_id, created_at)
- **外键/关联关系**：session_id → sessions.id
- **约束条件**：CHECK(route_decision IN ('direct','rag','web','cannot_confirm'))、CHECK(nli_score BETWEEN 0 AND 1)
- **数据量预估**：初始 0 / 增长 50/天 / 峰值 15000
- **分片策略**：按 created_at 月分区（V4.0）
- **来源标注**：[AR:API-002] + [DD推断:依据=回合记录结构]

---

## DS-003 SQLite（audit_log 审计日志）

- **关联技术选型**：TS-003 SQLite 3.46.1
- **表结构**：

#### audit_log 表

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| id | INTEGER | - | ✅ | AUTO | PK | 自增主键 |
| ts | TIMESTAMP | - | ✅ | now | IDX | 时间戳 |
| actor | TEXT | 64 | ✅ | - | IDX | 操作者（user_id / agent_id） |
| action | TEXT | 32 | ✅ | - | - | 操作类型 |
| target | TEXT | 64 | ✅ | - | - | 操作目标 |
| payload | JSON | - | ✅ | {} | - | 操作负载 |
| trace_id | TEXT | 32 | ✅ | - | IDX | 追踪 ID（BR-009/010 必传） |
| result | TEXT | 16 | ✅ | SUCCESS | - | SUCCESS/FAILURE/PARTIAL |
| error_code | TEXT | 16 | ✅ | - | - | 错误码 |

- **主键/唯一索引**：PK: id + IDX(ts, actor)
- **外键/关联关系**：无（审计日志独立保留）
- **约束条件**：全字段 NOT NULL（[TD:DE-023/024]）、CHECK(actor != '')、CHECK(trace_id != '')
- **数据量预估**：初始 0 / 增长 200/天 / 峰值 100k
- **分片策略**：按 ts 月分区 + 冷热分离（V4.0）
- **来源标注**：[AR:BR-009/010] + [AR:SR-011] + [TD:DE-023/024]

---

## DS-004 SQLite（fsrs_cards 间隔重复卡）

- **关联技术选型**：TS-003 SQLite 3.46.1 + TS-007 py-fsrs
- **表结构**：

#### fsrs_cards 表

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| id | TEXT | 36 | ✅ | - | PK | 卡片 ID（UUIDv4） |
| user_id | TEXT | 32 | ✅ | - | IDX | 用户 ID |
| front | TEXT | 500 | ✅ | - | - | 卡片正面 |
| back | TEXT | 2000 | ✅ | - | - | 卡片背面 |
| stability | REAL | - | ✅ | 0.0 | - | FSRS stability |
| difficulty | REAL | - | ✅ | 0.0 | - | FSRS difficulty |
| elapsed_days | INTEGER | - | ✅ | 0 | - | 距上次复习天数 |
| scheduled_days | INTEGER | - | ✅ | 0 | - | 计划间隔天数 |
| reps | INTEGER | - | ✅ | 0 | - | 复习次数 |
| lapses | INTEGER | - | ✅ | 0 | - | 遗忘次数 |
| state | TEXT | 16 | ✅ | NEW | - | NEW/LEARNING/REVIEW/RELEARNING |
| due | TIMESTAMP | - | ✅ | now | IDX | 下次到期时间 |
| last_review | TIMESTAMP | - | ✅ | - | - | 上次复习时间 |
| again_count | INTEGER | - | ✅ | 0 | - | Again 计数（节流 5min） |
| again_throttle_at | TIMESTAMP | - | ✅ | - | - | 节流截止时间 |
| created_at | TIMESTAMP | - | ✅ | now | - | 创建时间 |

- **主键/唯一索引**：PK: id + IDX(user_id, due)
- **外键/关联关系**：user_id → users.id
- **约束条件**：CHECK(state IN ('NEW','LEARNING','REVIEW','RELEARNING'))、CHECK(reps >= 0)
- **数据量预估**：初始 0 / 增长 20/天 / 峰值 5000
- **分片策略**：无
- **来源标注**：[AR:TS-007] + [AR:PO-005]

---

## DS-005 SQLite（memories 长期记忆）

- **关联技术选型**：TS-003 SQLite 3.46.1
- **表结构**：

#### memories 表

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| id | TEXT | 36 | ✅ | - | PK | 记忆 ID（UUIDv4） |
| user_id | TEXT | 32 | ✅ | - | IDX | 用户 ID |
| content | TEXT | 1000 | ✅ | - | - | 事实内容 |
| content_hash | TEXT | 64 | ✅ | - | UNIQUE | 内容 SHA256（幂等键） |
| embedding_id | TEXT | 36 | ✅ | - | - | ChromaDB ID |
| last_access | TIMESTAMP | - | ✅ | now | IDX | 最后访问时间（LRU） |
| access_count | INTEGER | - | ✅ | 0 | - | 访问次数 |
| importance | INTEGER | - | ✅ | 1 | - | 重要性 [1, 5] V4.5 |
| created_at | TIMESTAMP | - | ✅ | now | - | 创建时间 |

- **主键/唯一索引**：PK: id + UNIQUE(user_id, content_hash)
- **外键/关联关系**：user_id → users.id
- **约束条件**：CHECK(importance BETWEEN 1 AND 5)、CHECK(LENGTH(content_hash) = 64)
- **数据量预估**：初始 0 / 增长 10/天 / 峰值 100k
- **分片策略**：按 user_id 分区 + LRU 淘汰最旧 10%
- **来源标注**：[AR:API-007] + [AR:TD-AR-006]

---

## DS-006 ChromaDB（chunks 向量索引）

- **关联技术选型**：TS-004 ChromaDB 0.5.20
- **存储类型**：向量数据库
- **存储名称**：`chroma/` 目录（PersistentClient）
- **集合结构**：

#### chunks 集合

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| id | TEXT | 36 | ✅ | - | PK | chunk ID（UUIDv4） |
| embedding | FLOAT[768] | 768 | ✅ | - | HNSW | BGE-small 向量 |
| document | TEXT | 2000 | ✅ | - | - | chunk 文本 |
| metadata | JSON | - | ✅ | {} | - | 元数据（doc_id, user_id, page） |

- **主键/唯一索引**：PK: id
- **外键/关联关系**：metadata.doc_id → documents.id
- **约束条件**：HNSW 索引参数：ef_construction=200, M=16
- **数据量预估**：初始 0 / 增长 500/天 / 峰值 50k chunk（[AR:BR-005] 验证）
- **分片策略**：无（嵌入式）
- **来源标注**：[AR:TS-004] + [AR:DP-005] + [调研报告:RI-008]

---

## DS-007 ChromaDB（documents 文档元数据）

- **关联技术选型**：TS-004 ChromaDB 0.5.20
- **存储类型**：向量数据库（同时存于 SQLite）
- **集合结构**：

#### documents 集合

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| id | TEXT | 36 | ✅ | - | PK | doc ID（UUIDv4） |
| filename | TEXT | 256 | ✅ | - | - | 原始文件名 |
| user_id | TEXT | 32 | ✅ | - | - | 用户 ID |
| file_path | TEXT | 512 | ✅ | - | - | 文件路径 |
| file_size | INTEGER | - | ✅ | 0 | - | 文件大小（字节） |
| page_count | INTEGER | - | ✅ | 0 | - | 页数 |
| status | TEXT | 16 | ✅ | PENDING | - | PENDING/READY/FAILED/PARTIAL |
| translation_backend | TEXT | 16 | ✅ | - | - | pdf2zh/pdfplumber/lmstudio |
| chunk_count | INTEGER | - | ✅ | 0 | - | chunk 数 |
| trace_id | TEXT | 32 | ✅ | - | - | 追踪 ID |
| created_at | TIMESTAMP | - | ✅ | now | - | 创建时间 |

- **主键/唯一索引**：PK: id
- **外键/关联关系**：user_id → users.id
- **约束条件**：CHECK(status IN ('PENDING','READY','FAILED','PARTIAL'))、CHECK(file_size <= 104857600)（100MB）
- **数据量预估**：初始 0 / 增长 5/天 / 峰值 500
- **分片策略**：无
- **来源标注**：[AR:API-004] + [AR:SEC-005]

---

## DS-008 Cache（语义缓存）

- **关联技术选型**：TS-003 SQLite（默认）/ TS-005 Redis（可选）
- **存储类型**：缓存（双后端）
- **存储名称**：`cache/semantic.db`（SQLite 默认）/ `redis://...`（生产）
- **表结构**：

#### semantic_cache 表

| 字段 | 类型 | 长度 | 必填 | 默认值 | 索引 | 描述 |
|------|------|------|------|--------|------|------|
| key | TEXT | 64 | ✅ | - | PK | query_hash SHA256 |
| query | TEXT | 2000 | ✅ | - | - | 原始 query |
| response | TEXT | 10000 | ✅ | - | - | 缓存响应 |
| embedding | BLOB | - | ✅ | - | - | query 向量（用于相似度检索） |
| ttl | INTEGER | - | ✅ | 3600 | - | 过期时间（秒） |
| expire_at | TIMESTAMP | - | ✅ | now+1h | IDX | 过期时刻（±20% 抖动） |
| hit_count | INTEGER | - | ✅ | 0 | - | 命中次数 |
| last_access | TIMESTAMP | - | ✅ | now | - | 最后访问（LRU） |
| size_bytes | INTEGER | - | ✅ | 0 | - | 响应大小 |

- **主键/唯一索引**：PK: key + IDX(expire_at)
- **外键/关联关系**：无
- **约束条件**：CHECK(LENGTH(key) = 64)、CHECK(ttl > 0)
- **数据量预估**：初始 0 / 增长 100/天 / 峰值 10k
- **分片策略**：LRU 容量上限 10k
- **来源标注**：[AR:TS-005] + [AR:PO-006] + [AR:ADR-004]

---

## DS-009 File Store（文件存储）

- **关联技术选型**：TS-001 Python（pathlib）
- **存储类型**：文件系统
- **存储名称**：`~/.<app>/files/` 目录
- **结构**：

```
~/.<app>/
  data.db            # SQLite 主库
  chroma/            # ChromaDB 持久化
    chroma.sqlite3
    <collection-uuid>/
  files/             # 用户文件
    pdf/             # PDF 原文
    images/          # 图片
    cleaned/         # 清洗后文本
    chunks/          # 分块后 JSON
  cache/
    semantic.db      # 语义缓存
  models/
    nli/             # NLI 模型（1.5GB）
  logs/
    aitutor.log      # structlog 输出
  config.toml        # 用户配置
  .pre-commit-cache/ # 工具链缓存
```

- **主键/唯一索引**：N/A（按文件路径）
- **外键/关联关系**：路径白名单（仅 ~/.<app>/ 目录）
- **约束条件**：
  - PDF ≤100MB
  - 文件类型白名单（PDF/MD/PNG/JPG）
  - 拒绝路径穿越（../ 或绝对路径）
- **数据量预估**：初始 0 / 增长 50MB/天 / 峰值 10GB
- **分片策略**：按用户目录隔离（V4.0 多用户）
- **来源标注**：[AR:DP-001] + [AR:SEC-005] + [AR:TD-BP-009/017/018]

---

## 数据结构覆盖率

| 存储类型 | 数量 | 编号 |
|---------|------|------|
| SQLite 表 | 5 | DS-001（users/sessions）+ DS-002（turns）+ DS-003（audit_log）+ DS-004（fsrs_cards）+ DS-005（memories）|
| Chroma 集合 | 2 | DS-006（chunks）+ DS-007（documents）|
| 缓存 | 1 | DS-008（semantic_cache）|
| 文件系统 | 1 | DS-009 |
| **合计** | **9** | 全部有完整结构定义 |

来源标注：[AR:TS-003/004/005] + [AR:DP-004/005] + [DD推断:依据=TS 涉及数据存储的完整结构]
