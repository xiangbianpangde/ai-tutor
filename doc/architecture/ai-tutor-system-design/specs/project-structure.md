# 项目文件树与职责说明

> 完整的 monorepo 结构，每个文件/目录的职责和依赖关系

---

## 一、顶层

```
ai-tutor/                              # Git 仓库根
├── .github/
│   └── workflows/
│       └── test.yml                   # CI: unit + integration + lint + e2e(nightly)
├── shared/                            # 跨 server 共享库
│   ├── __init__.py
│   ├── schemas.py                     # Pydantic 模型 (specs/shared-schemas.md)
│   ├── models.py                      # SQLAlchemy ORM 模型 (specs/database-schema.md)
│   ├── errors.py                      # TutorError + ERROR_CODES
│   ├── storage.py                     # FileStore + StateStore + RelationalStore + VectorStore
│   ├── plugins.py                     # PluginLoader + PLUGIN_REGISTRY
│   ├── llm_client.py                  # LLM API 调用封装 (分级/缓存/熔断)
│   ├── llm_cache.py                   # LLM 三级缓存 (L1内存/L2 SQLite/L3语义)
│   └── logging_config.py             # structlog 配置
├── servers/
│   ├── knowledge_mcp/
│   │   ├── __init__.py
│   │   ├── server.py                  # FastMCP server 入口
│   │   ├── acquisition.py             # acquire_subject 实现
│   │   │   ├── fetch_textbook()       #   Anna's Archive 检索
│   │   │   ├── pdf_to_markdown()      #   Docker pdf2zh 调用
│   │   │   ├── transcribe_video()     #   yt-dlp + whisper 调用
│   │   │   ├── web_collect()          #   DuckDuckGo/Tavily 调用
│   │   │   └── normalize_corpus()     #   去重 + 章节对齐
│   │   ├── extraction.py              # L4 知识抽取流水线
│   │   │   ├── PassageSplitter        #   语义段落切分
│   │   │   ├── ConceptDetector        #   概念识别 (规则+LLM)
│   │   │   └── RelationExtractor      #   关系抽取 (LLM+验证)
│   │   ├── difficulty.py              # L4 难度评分器
│   │   ├── embedding.py               # L4 Embedding索引 (all-MiniLM)
│   │   ├── quality_gate.py            # L4 Quality Gate
│   │   ├── fusion.py                  # L4 知识融合 (对齐+冲突检测)
│   │   ├── kg_store.py                # KG 版本化存储
│   │   └── tests/
│   │       ├── test_acquisition.py
│   │       ├── test_extraction.py
│   │       └── test_kg_store.py
│   ├── tutoring_mcp/
│   │   ├── __init__.py
│   │   ├── server.py                  # FastMCP server 入口
│   │   ├── session.py                 # L2 会话管理 (CRUD + 断点)
│   │   ├── tracer.py                  # L5 知识追踪 (BKT + DKT)
│   │   ├── bkt.py                     # BKT 贝叶斯更新引擎
│   │   ├── dkt_model.py               # DKT PyTorch 模型 (Phase 3)
│   │   ├── error_diagnosis.py         # L5 错误诊断引擎
│   │   ├── cognitive_load.py          # L5 认知负荷估计
│   │   ├── profiler.py                # L5 学习者画像 (ProfileEvolver)
│   │   ├── engine.py                  # L6 教学决策主循环
│   │   ├── strategy_selector.py       # L6 策略选择决策树
│   │   ├── strategies/
│   │   │   ├── __init__.py
│   │   │   ├── reduction.py           #   降阶法 状态机
│   │   │   ├── feynman.py             #   费曼法 状态机
│   │   │   ├── socratic.py            #   苏格拉底法 状态机
│   │   │   ├── pbl.py                 #   项目驱动法
│   │   │   ├── analogy.py             #   类比桥接法
│   │   │   └── spaced_repetition.py   #   间隔复习
│   │   ├── memory.py                  # L3 长期记忆 (遗忘曲线+复习调度)
│   │   ├── forgetting_curve.py        # L3 个性化遗忘曲线拟合
│   │   ├── review_scheduler.py        # L3 多因子复习调度器
│   │   ├── knowledge_network.py       # L3 学生知识网络
│   │   └── tests/
│   │       ├── test_bkt.py
│   │       ├── test_strategies.py
│   │       ├── test_engine.py
│   │       └── test_memory.py
│   ├── digest_mcp/
│   │   ├── __init__.py
│   │   ├── server.py                  # FastMCP server 入口
│   │   ├── orchestrator.py            # digest() 编排逻辑
│   │   ├── quiz.py                    # build_quiz_html()
│   │   ├── slides.py                  # compile_slides()
│   │   ├── mindmap.py                 # Mermaid → PNG
│   │   ├── notes.py                   # reportlab PDF
│   │   ├── audio.py                   # edge-tts MP3
│   │   ├── simulation.py              # HTML 交互模拟
│   │   ├── multi_agent.py             # 多智能体脚本
│   │   ├── references/                # format-*.md (从 knowledge-digest 迁移)
│   │   │   ├── format-notes.md
│   │   │   ├── format-quiz.md
│   │   │   ├── format-slides.md
│   │   │   ├── format-mindmap.md
│   │   │   ├── format-audio.md
│   │   │   ├── format-simulation.md
│   │   │   └── format-multi-agent.md
│   │   ├── assets/
│   │   │   └── quiz-template.html     # 测验 HTML 模板
│   │   └── tests/
│   │       └── test_digest.py
│   └── sync_mcp/
│       ├── __init__.py
│       ├── server.py                  # FastMCP server 入口
│       ├── github_sync.py             # PyGithub + git 操作
│       ├── obsidian_sync.py           # watchdog + vault 扫描
│       └── tests/
│           └── test_sync.py
├── migrations/                        # Alembic migration 文件
│   ├── env.py
│   ├── alembic.ini
│   └── versions/
│       └── 001_initial_schema.py
├── data/                              # 运行时数据目录 (gitignore)
│   ├── corpora/                       #   语料库
│   ├── knowledge_graphs/              #   KG 文件
│   ├── output/                        #   产物目录 (artifact://)
│   ├── models/                        #   DKT 模型文件
│   └── tutor.db                       #   SQLite 数据库 (开发)
├── tests/
│   ├── conftest.py                    # 共享 fixtures (temp_dir, mock_kg, db_session)
│   ├── unit/                          # 单元测试
│   └── integration/                   # 集成测试
├── examples/
│   ├── claude_desktop.json            # Claude Desktop MCP 配置示例
│   └── workflow_48h.md                # 48h 端到端演示脚本
├── docker-compose.yml                 # pdf2zh + whisper + redis + 4 个 server
├── Dockerfile                         # 每个 server 的通用 Dockerfile
├── pyproject.toml                     # uv workspace 配置
├── uv.lock                            # 依赖锁定
├── .env.example                       # 环境变量模板
├── .gitignore
├── README.md                          # 项目 README
└── LICENCE                            # MIT
```

---

## 二、每个 server 的依赖关系

```
digest-mcp:
  → shared (schemas, plugins, errors, llm_client)

sync-mcp:
  → shared (schemas, storage, errors)

knowledge-mcp:
  → shared (schemas, storage, plugins, errors, llm_client, llm_cache)

tutoring-mcp:
  → shared (schemas, storage, errors, llm_client)
  → knowledge-mcp 的 KG 数据 (通过 shared/storage 读写，不直接 import)
```

**关键约束**：
- tutoring-mcp **不 import** knowledge-mcp 的代码
- 两个 server 通过**共享的数据库**交换 KG 数据（knowledge-mcp 写入，tutoring-mcp 读取）
- 这就是 MCP 规范中的"server 间通信由 host 协调"的实现方式

---

## 三、各层代码所属

| 层 | 代码位置 | 核心文件 |
|-----|---------|---------|
| L1 | `shared/` (全部) + `docker-compose.yml` | storage.py, plugins.py, errors.py |
| L2 | `servers/tutoring_mcp/session.py` | SessionContext CRUD |
| L3 | `servers/tutoring_mcp/memory.py` + `forgetting_curve.py` + `review_scheduler.py` | 长期记忆 |
| L4 | `servers/knowledge_mcp/` (全部) | extraction.py, fusion.py, kg_store.py |
| L5 | `servers/tutoring_mcp/tracer.py` + `bkt.py` + `error_diagnosis.py` + `profiler.py` | 学习者建模 |
| L6 | `servers/tutoring_mcp/engine.py` + `strategies/` | 教学引擎 |
| L7 | 每个 server 的 `server.py` (FastMCP) | MCP Tool 定义 |

---

## 四、关键文件大小估计

| 文件 | 估计行数 | 复杂度 |
|------|---------|--------|
| `shared/schemas.py` | ~400 | 低（纯数据定义） |
| `shared/models.py` | ~300 | 低（SQLAlchemy 映射） |
| `shared/storage.py` | ~250 | 中（多后端抽象） |
| `shared/plugins.py` | ~200 | 中（选择+健康检查） |
| `shared/llm_client.py` | ~300 | 中（分级+缓存+熔断） |
| `knowledge_mcp/acquisition.py` | ~400 | 高（编排5个子流程） |
| `knowledge_mcp/extraction.py` | ~500 | 高（LLM批处理+验证） |
| `knowledge_mcp/fusion.py` | ~300 | 中（对齐+冲突检测） |
| `tutoring_mcp/engine.py` | ~400 | 高（教学决策主循环） |
| `tutoring_mcp/tracer.py` | ~250 | 中（BKT+DKT 双模型） |
| `tutoring_mcp/strategies/reduction.py` | ~200 | 中（状态机实现） |
| `tutoring_mcp/memory.py` | ~300 | 中（遗忘曲线+调度） |
| **总计** | **~8000** | — |

---

## 五、启动顺序

```
开发环境:
  1. 启动 Docker 依赖: docker compose up -d pdf2zh whisper redis
  2. 启动 knowledge-mcp: uv run python -m servers.knowledge_mcp.server --transport stdio
  3. 启动 tutoring-mcp: uv run python -m servers.tutoring_mcp.server --transport stdio
  4. 启动 digest-mcp: uv run python -m servers.digest_mcp.server --transport stdio
  5. 启动 sync-mcp: uv run python -m servers.sync_mcp.server --transport stdio

生产环境:
  docker compose up  # 一键启动全部
```

---

## 六、开发工程师的切入点

```
第一步: 阅读 specs/shared-schemas.md → 建 shared/schemas.py
第二步: 阅读 specs/database-schema.md → 建 shared/models.py + migrations/
第三步: 阅读 specs/server-api-spec.md → 建各 server 的 server.py 骨架
第四步: 阅读 specs/project-structure.md (本文) → 建项目目录 + pyproject.toml
第五步: 阅读 specs/testing-strategy.md → 建 CI + 写测试
第六步: 阅读各 L 层设计文档 → 按 Phase 实施
```
