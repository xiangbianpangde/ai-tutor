# 数据库 Schema 与 Migration 策略

> 目标：定义所有持久化表结构 + Alembic migration 管理策略  
> 数据库：SQLite（开发零配置）/ PostgreSQL（生产，同 DDL）  
> ORM：SQLAlchemy 2.0+

---

## 一、Migration 策略

```
工具: Alembic
迁移文件目录: ai-tutor/migrations/versions/
自动生成: alembic revision --autogenerate -m "描述"
应用: alembic upgrade head
回滚: alembic downgrade -1

原则:
1. 每次 schema 变更 → 一个新的 migration 文件
2. migration 文件包含 upgrade() 和 downgrade()
3. 不直接在数据库里手改表结构
4. CI 中跑 alembic upgrade head 验证 migration 可执行
5. 初始 migration (base) 包含下面所有表的 CREATE
```

---

## 二、完整 DDL

### 2.1 用户与科目

```sql
-- 用户表（最简单，仅用于关联）
CREATE TABLE users (
    id TEXT PRIMARY KEY,                  -- "yhn"
    display_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 科目表
CREATE TABLE subjects (
    id TEXT PRIMARY KEY,                  -- "gaoshu-v8"
    user_id TEXT NOT NULL REFERENCES users(id),
    display_name TEXT NOT NULL,           -- "同济版高等数学下册"
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'active',         -- active | completed | abandoned
    kg_id TEXT                            -- 最新 KG 版本 ID
);
```

### 2.2 L4 知识工程表

```sql
-- 语料库
CREATE TABLE corpora (
    id TEXT PRIMARY KEY,                  -- "gaoshu-v8-yhn-20260519"
    subject_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    manifest_json TEXT NOT NULL,          -- CorpusManifest JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 知识图谱
CREATE TABLE knowledge_graphs (
    kg_id TEXT PRIMARY KEY,               -- "gaoshu-v8-kg-v1"
    subject_id TEXT NOT NULL,
    corpus_id TEXT NOT NULL REFERENCES corpora(id),
    version TEXT NOT NULL,
    node_count INTEGER NOT NULL,
    edge_count INTEGER NOT NULL,
    quality_json TEXT,                    -- QualityReport JSON
    manifest_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 概念节点
CREATE TABLE concepts (
    id TEXT PRIMARY KEY,                  -- "gaoshu-v8:2.1.1:limit_epsilon_delta"
    kg_id TEXT NOT NULL REFERENCES knowledge_graphs(kg_id),
    name_primary TEXT NOT NULL,           -- 主名称
    names_json TEXT NOT NULL,             -- ["极限的ε-δ定义", ...]
    category TEXT NOT NULL,               -- definition | theorem | formula | ...
    definition TEXT NOT NULL,
    informal_description TEXT,
    abstract_level REAL NOT NULL,
    bloom_level TEXT NOT NULL,
    domain TEXT NOT NULL,
    cognitive_load_estimate REAL NOT NULL,
    typical_learning_time_min INTEGER NOT NULL,
    prereq_count INTEGER NOT NULL,
    prereq_max_depth INTEGER NOT NULL,
    formula_density REAL NOT NULL,
    coupling REAL NOT NULL,
    confidence REAL NOT NULL,
    full_json TEXT NOT NULL,              -- 完整 Concept JSON（含 examples, misconceptions 等）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 关系边
CREATE TABLE relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- SQLite: AUTOINCREMENT; PG: SERIAL
    kg_id TEXT NOT NULL REFERENCES knowledge_graphs(kg_id),
    from_id TEXT NOT NULL REFERENCES concepts(id),
    to_id TEXT NOT NULL REFERENCES concepts(id),
    type TEXT NOT NULL,                   -- is_a | prerequisite_strong | ...
    weight REAL NOT NULL,
    explanation TEXT NOT NULL,
    confidence REAL NOT NULL,
    deprecated INTEGER DEFAULT 0,         -- 0=active, 1=deprecated
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (from_id != to_id)              -- 禁止自环
);

-- 索引
CREATE INDEX idx_concepts_kg ON concepts(kg_id);
CREATE INDEX idx_concepts_domain ON concepts(domain);
CREATE INDEX idx_relations_kg ON relations(kg_id);
CREATE INDEX idx_relations_from ON relations(from_id);
CREATE INDEX idx_relations_to ON relations(to_id);
CREATE INDEX idx_relations_type ON relations(type);
```

### 2.3 L3 长期记忆表

```sql
-- 复习历史
CREATE TABLE review_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    concept_id TEXT NOT NULL,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    review_date DATE NOT NULL,
    days_since_last INTEGER NOT NULL,
    accuracy REAL NOT NULL,
    review_mode TEXT NOT NULL,            -- quick_quiz | concept_map | teach_back | error_revisit
    error_types TEXT,                     -- JSON array
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_user ON review_history(user_id);
CREATE INDEX idx_review_concept ON review_history(concept_id);
CREATE INDEX idx_review_date ON review_history(review_date);

-- 遗忘曲线参数
CREATE TABLE forgetting_curves (
    user_id TEXT NOT NULL,
    concept_id TEXT NOT NULL,
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    lambda REAL NOT NULL,                 -- 衰减速率
    r_squared REAL,
    n_data_points INTEGER DEFAULT 0,
    last_review_at TIMESTAMP,
    next_review_at TIMESTAMP,
    review_streak INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, concept_id)
);

-- 每日复习计划
CREATE TABLE review_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    plan_date DATE NOT NULL,
    plan_json TEXT NOT NULL,              -- DailyReviewPlan JSON
    completion_rate REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.4 L5 学习者模型表

```sql
-- BKT 参数（每个用户×概念一行）
CREATE TABLE bkt_params (
    user_id TEXT NOT NULL,
    concept_id TEXT NOT NULL,
    p_learn REAL NOT NULL DEFAULT 0.15,
    p_guess REAL NOT NULL DEFAULT 0.12,
    p_slip REAL NOT NULL DEFAULT 0.08,
    p_init REAL NOT NULL DEFAULT 0.05,
    p_mastery REAL NOT NULL DEFAULT 0.05,
    n_observations INTEGER DEFAULT 0,
    last_updated TIMESTAMP,
    PRIMARY KEY (user_id, concept_id)
);

-- 知识状态快照（每次 checkpoint 写入一份）
CREATE TABLE knowledge_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id),
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    snapshot_json TEXT NOT NULL,          -- KnowledgeSnapshot JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_snapshots_user_subject ON knowledge_snapshots(user_id, subject_id);

-- 学习者画像
CREATE TABLE learner_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    version INTEGER DEFAULT 1,
    profile_json TEXT NOT NULL,           -- LearnerProfile JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2.5 L2 会话表

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,                  -- "sess-abc123"
    user_id TEXT NOT NULL REFERENCES users(id),
    subject_id TEXT NOT NULL REFERENCES subjects(id),
    status TEXT DEFAULT 'active',         -- active | interrupted | completed | expired
    context_json TEXT NOT NULL,           -- SessionContext JSON
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);
```

---

## 三、SQLite ↔ PostgreSQL 兼容要点

| 差异点 | SQLite | PostgreSQL | 兼容方案 |
|--------|--------|------------|----------|
| 自增主键 | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL` 或 `GENERATED ALWAYS AS IDENTITY` | SQLAlchemy 的 `Integer, primary_key=True` 自动处理 |
| 布尔类型 | `INTEGER` (0/1) | `BOOLEAN` | SQLAlchemy `Boolean` 类型自动映射 |
| JSON 类型 | `TEXT` 存 JSON 字符串 | `JSONB` | SQLAlchemy `JSON` 类型；PG 用 JSONB，SQLite 用 TEXT |
| 时间戳 | `TEXT` / `INTEGER` | `TIMESTAMP` | 统一用 SQLAlchemy `DateTime` |
| DDL 中 CHECK | 部分支持 | 完整支持 | 简单约束（NOT NULL, CHECK id != id）两边都支持 |
| 并发写入 | 单写者 | 多写者 | 开发阶段 SQLite 足够；生产切 PG 后天然解决 |

**实现建议**：用 SQLAlchemy 声明式基类定义所有表，SQLite/PG 切换只需改 `DATABASE_URL`。

---

## 四、Alembic 配置

```ini
# alembic.ini
[alembic]
script_location = migrations
sqlalchemy.url = sqlite:///data/tutor.db  # 开发默认

# migrations/env.py 中:
# target_metadata = shared.models.Base.metadata
# 所有 ORM 模型定义在 shared/models.py，继承同一个 Base
```

### 初始 migration

```bash
# 生成初始 migration（含所有表）
alembic revision --autogenerate -m "initial_schema"

# 生成的 migration 文件包含所有 CREATE TABLE 语句
# 开发工程师只需确认生成的 DDL 与本规格一致
```

### 后续 migration 示例

```bash
# 例如：给 relations 表加一个字段
alembic revision --autogenerate -m "add_relation_verified_by_field"
```

---

## 五、ORM 模型组织

```
ai-tutor/shared/
├── models.py          # SQLAlchemy ORM 模型（映射上表）
│   ├── Base           # declarative_base()
│   ├── User
│   ├── Subject
│   ├── Corpus
│   ├── KnowledgeGraph
│   ├── Concept
│   ├── Relation
│   ├── ReviewHistory
│   ├── ForgettingCurve
│   ├── ReviewPlan
│   ├── BKTParam
│   ├── KnowledgeSnapshot
│   ├── LearnerProfile
│   └── Session
└── schemas.py         # Pydantic 模型（业务逻辑用，非 ORM）
```

**开发规则**：
- Pydantic 模型用于 API 输入/输出和业务逻辑
- SQLAlchemy 模型仅用于数据库读写
- 两者之间的转换用 `model_validate()` / `model_dump()`
- 不把 ORM 对象直接暴露给 MCP Tool 返回
