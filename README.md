# ai-tutor

48 小时学完一科的私人 AI 辅导系统。基于 `../使用AI进行学习的技巧/ai-tutor-system-design/` 的 v3.0 七层认知架构。

> **状态速览**：4 个 MCP server · 31 个 tool（全部实现，无硬 stub）· 656 测试全绿（655 passed + 1 skipped，含 58 个接入真实实现的 BDD Scenario）· 零必需重依赖（重量级库全部「装了就升级、缺了优雅降级」）。

这份 README 主要写给**几个月后回来的自己**：先看懂架构和数据流，再知道每个能力在哪、怎么跑、当初为什么这么设计。详细历史在 [ROADMAP.md](./ROADMAP.md)。

---

## 1. 这是什么

把一科的资料（PDF / Markdown / Obsidian 笔记）喂进去，系统会：

1. **建知识图谱**（L4）：抽章节骨架 → LLM 富化每个概念（定义/例子/误解）→ 难度校准 + 向量化
2. **教你学**（L2/L5/L6）：BKT 掌握度追踪 + reduction 教学策略 + PGFGA 心流/增益回路 + 打断/检查点
3. **生成复习产物**（digest）：思维导图 / 笔记 / 测验 / 闪卡 / 三角色对话 / 幻灯片 / 朗读讲稿
4. **同步回工作流**（sync）：写回 Obsidian、git 版本化学习产物、监听 vault 变更

四个能力各是一个 MCP server，接进 Claude Desktop / Cursor 等 MCP host 即可用自然语言驱动。

---

## 2. 七层认知架构 → 目录映射

```
L7 交互层        ┐
L6 教学引擎      ├─ servers/tutoring_mcp/   (BKT, reduction 策略, PGFGA 心流)
L5 学习者建模    ┘
L4 知识工程      ── servers/knowledge_mcp/  (acquire→build→query→review→update→版本树)
L3 长期记忆      ── servers/tutoring_mcp/   (遗忘曲线拟合 + 复习调度)  + (可选)向量索引
L2 短期记忆      ── servers/tutoring_mcp/   (会话上下文 SessionContext)
L1 基础设施      ── shared/                 (schemas / errors / models / storage / providers)

产物与同步（横切）：
  servers/digest_mcp/   多模态复习产物（7 种 format）
  servers/sync_mcp/     Obsidian + git 双向同步
```

---

## 3. 四个 MCP server × 31 tool

### knowledge-mcp（L4 知识工程）— 9 tool
| tool | 作用 |
|---|---|
| `acquire_subject` | 采集资料（file 源：PDF 经 mineru→md / Markdown 直读；web/video 留接口） |
| `build_knowledge_graph` | 建 KG，`depth` ∈ `toc`(纯规则) / `concept`(LLM 富化) / `full`(+难度校准+embedding) |
| `query_knowledge` | `query_type` ∈ `concept` / `neighbors` / `path`(最短学习路径) / `subgraph`(N 跳邻域) |
| `review_kg` | quick/full 审查 + 缩略 Mermaid + 建议动作 |
| `update_kg` | 6 种编辑 op + 审计；`mode=versioned` 建新版本（base_id 版本树） |
| `diff_kg` | 按 base_id 对齐两版本：新增/删除/定义变更 |
| `rollback_kg` | subject 指针回滚到祖先版本（不删 child，留审计） |
| `resolve_conflicts` | 检测 5 种结构冲突（环/反向前置/重复/悬空边/孤岛） |
| `health` | 自检 |

### tutoring-mcp（L2/L3/L5/L6 教学）— 12 tool
| tool | 作用 |
|---|---|
| `cold_start_probe` | 冷启动摸底出题（跨难度 10 道，探测先验掌握） |
| `submit_cold_start` | 摸底判分 → 种 BKT 先验 + 画像初值（已掌握概念后续跳过） |
| `start_learning_session` | 开新会话，按章节定 Phase 化教学计划（跳过已掌握概念） |
| `resume_learning` | 续学：复用未结束会话或从首个未掌握概念继续 |
| `get_learning_progress` | 查跨 Session 进度（各 Phase 完成度 + 下一个该学的概念） |
| `respond` | 学生作答 → 评分 + 诊断 + 反馈（过非评判防火墙）+ 策略推进 + 心流/增益回路 |
| `next_action` | 按拓扑序 + BKT 掌握度推荐下一个动作 |
| `interrupt` | 处理打断：意图分类 → 分支响应 + 保存 checkpoint |
| `checkpoint` | 保存/恢复会话断点 |
| `learning_insight` | 学习者画像洞察 |
| `generate_review_plan` | 基于遗忘曲线（拟合 λ）排复习计划 |
| `health` | 自检 |

### digest-mcp（多模态产物）— 4 tool
| tool | 作用 |
|---|---|
| `digest` | 按 `formats` 生成 7 种产物：`mindmap` / `notes` / `quiz` / `simulation`(HTML闪卡) / `multi_agent`(三角色对话) / `slides`(HTML→可选pptx) / `audio`(讲稿→可选mp3) |
| `build_quiz_html` | 独立入口：直接从 KG 出测验（复用 quiz generator） |
| `compile_slides` | 独立入口：直接从 KG 出幻灯片（有 pptx→.pptx，否则 HTML） |
| `health` | 自检 |

### sync-mcp（Obsidian + git）— 6 tool
| tool | 作用 |
|---|---|
| `push_to_obsidian` | 把产物写进 Obsidian vault |
| `pull_homework_from_obsidian` | 扫 vault 里跟 subject 相关的 markdown（文件名/frontmatter/tag 匹配） |
| `init_subject_repo` | 为 subject 建本地 git 仓库（可选关联 GitHub remote） |
| `push_artifacts` | 产物提交进 git（可选 push 远程） |
| `watch_obsidian` | 轮询 vault 变更（mtime 增量） |
| `health` | 自检 |

完整 tool/分支清单与跨 server 依赖见 [ROADMAP.md](./ROADMAP.md)。

---

## 4. 数据流（一条主线）

```
资料(pdf/md)
  └─ knowledge.acquire_subject ─→ corpus
       └─ knowledge.build_knowledge_graph(depth=concept|full) ─→ KG (concepts + relations)
            ├─ tutoring.start_learning_session ─→ session
            │    └─ respond / next_action / interrupt  （学 + 评 + 心流追踪）
            │         └─ 遗忘曲线 ─→ generate_review_plan
            ├─ digest.digest(formats=[...]) ─→ 复习产物（7 种）
            └─ sync.push_to_obsidian / push_artifacts ─→ Obsidian + git
```

---

## 5. 快速开始

```powershell
cd C:\Users\yhn\Desktop\ai-tutor

# 1. 装依赖（必需 + dev；research 引擎可选）
uv sync --extra dev

# 2. 配 .env（没有 key 也能跑，LLM 路径降级到启发式/模板）
copy .env.example .env
#   .env 里填 DEEPSEEK_API_KEY=...

# 3. 初始化数据库
uv run python scripts/init_db.py

# 4. 全量测试（应 518 passed + 1 skipped；含 BDD 套件）
uv run pytest

# 5. 确认 4 个 server 能起
uv run python scripts/verify_servers.py
```

接进 Claude Desktop → 见 [INTEGRATION.md](./INTEGRATION.md)（5 分钟跑通）。
生产/多机/HTTP/备份/故障排查 → 见 [DEPLOYMENT.md](./DEPLOYMENT.md)。

---

## 6. demo 脚本（scripts/）

每个切片都有可独立运行的 demo，验证该层真实跑通（多数用 MockLLM，不耗 key）：

| 脚本 | 演示 |
|---|---|
| `demo_concept_mode.py` | KG concept 模式富化 |
| `demo_full_workflow.py` | acquire→build→query 全链路 |
| `demo_k3.py` | KG 版本树（update versioned / diff / rollback） |
| `demo_t1.py` / `demo_t1plus.py` | 教学 respond / 打断 + 检查点 |
| `demo_t2.py` | 遗忘曲线 + 复习调度 |
| `demo_t3.py` | PGFGA 心流追踪 + 增益回路 |
| `demo_digest.py` | 多模态产物生成 |
| `demo_sync.py` / `demo_s2.py` | Obsidian 同步 / git 版本化 |
| `run_e2e_demo.py` | 端到端串联 |
| `init_db.py` / `verify_servers.py` | 建表 / server 起停自检 |

跑法：`uv run python scripts/demo_xxx.py`（部分接受真实笔记路径参数，默认回退到 `tests/fixtures/mini_subject.md`）。

---

## 7. 依赖说明（重要：三档）

**A. 必需**（`uv sync` 自动装）：fastmcp · pydantic · sqlalchemy · alembic · structlog · httpx · pyyaml · anyio · numpy · scipy · networkx · openai · pypinyin

**B. pyproject extras**（按需 `uv sync --extra <name>`）：
- `research` — 复用桌面 `../调研/research-tool` 作采集/抽取后端（本地路径依赖）
- `vector` — chromadb + sentence-transformers（L3 向量索引）
- `dev` — pytest 全家桶 + ruff

**C. 软探测依赖**（**不在 pyproject**，代码用 `importlib` 探测，装了就升级、缺了优雅降级）：
| 库 | 影响的能力 | 缺失时降级为 |
|---|---|---|
| `python-pptx` | digest slides | 自包含 HTML 幻灯片 |
| `edge-tts` | digest audio | 朗读讲稿 .md（不合成 mp3） |
| `chromadb` | build full / 向量检索 | 仍写 numpy 64 维 embedding 进 full_json |
| 系统 `git` CLI | sync git 系列 | （git 通常已装；本地版本控制核心能力） |

> 这是刻意的设计：CI / 离线 / 中国区网络都能跑全套核心功能，重依赖只是「锦上添花」。

---

## 8. 给未来的你 — 关键设计决策速查

- **concept.id 三段式** `subject:chapter.section:slug`，必须 ASCII（中文经 pypinyin 转写）。`shared/schemas.py:CONCEPT_ID_PATTERN`。
- **KG 版本树**用 `base_id`（稳定身份）+ `parent_kg_id`（版本链），versioned 拷贝时 ConceptRow.id 加 `@v` 后缀；**不用复合主键**（会破坏 BKT 跨版本继承）。
- **难度校准是确定性加权公式**，不是 XGBoost——因为没有真实难度标注数据。`kg_full.py`，将来有学习者答题数据可无缝换成学习模型。
- **PGFGA 心流**做成基于信号净分的状态机，不是 7 条字面转移规则（鲁棒）。`servers/tutoring_mcp/flow_*.py`。
- **三轮 code-review 累计修 10 个真 bug**，教训沉淀在审查记忆里：死代码 / id 空间不一致 / 时区(utcnow vs local mtime) / 双存同步(names_json vs full_json) / `</script>` XSS / asyncio.run 嵌套事件循环。
- **HTML 产物内联 JSON 必须转义 `</`→`<\/`**（防 `</script>` 提前闭合脚本块）。
- **同步函数里调 asyncio.run** 若可能被 async 上下文调用，必须探测 running loop 走 worker thread（见 `digest_mcp/audio.py:_run_async`）。

---

## 9. 项目文件结构

标准 Python 包布局：配置/文档在根，`shared/` 是 L1 基础设施，每个 MCP server 一个包并自带 `tests/`。

```
ai-tutor/
├── 配置 / 入口（根目录）
│   ├── pyproject.toml          依赖 + 打包 + ruff/pytest 配置
│   ├── uv.lock                 依赖锁
│   ├── alembic.ini             迁移配置
│   ├── conftest.py             pytest 共享 fixture（必须在根）
│   ├── .env.example            环境变量模板
│   └── .gitignore
│
├── 文档
│   ├── README.md               全景入口（本文件）
│   ├── HANDOFF.md              接手必读：状态/约定/雷区/工作流
│   ├── ROADMAP.md              18 切片历史 + 每文件状态 + 测试分布
│   ├── INTEGRATION.md          接 Claude Desktop（5 分钟）
│   ├── DEPLOYMENT.md           生产/多机/HTTP/备份/故障排查
│   └── PGFGA-TUNING.md         心流/增益回路调参
│
├── examples/                   Claude Desktop 配置示例
├── migrations/                 alembic（env.py + script.py.mako）
│
├── scripts/                    demo + 工具脚本
│   ├── demo_concept_mode / demo_full_workflow / demo_k3        切片演示（10 个）
│   ├── demo_t1 / demo_t1plus / demo_t2 / demo_t3
│   ├── demo_digest / demo_sync / demo_s2
│   └── init_db / verify_servers / run_e2e_demo                 工具脚本
│
├── shared/                     L1 基础设施（所有 server 共用）
│   ├── schemas.py              60+ Pydantic 模型（改数据结构从这里开始）
│   ├── models.py               SQLAlchemy ORM（14 表）
│   ├── errors.py               TutorError + 错误码白名单
│   ├── storage.py              RelationalStore / FileStore
│   ├── config.py  logging_config.py  plugins.py  slug.py
│   ├── llm_client.py  llm_cache.py
│   └── providers/deepseek.py
│
├── servers/                    4 个 MCP server（每个自带 tests/）
│   ├── knowledge_mcp/          L4 知识工程（9 tool）
│   │     server + kg_builder / kg_full / kg_query / kg_diff / kg_rollback
│   │     kg_update / kg_review / kg_enrich_adapter / concept_enricher
│   │     acquisition_adapter / resolve_conflicts + tests/(15)
│   ├── tutoring_mcp/           L2/L3/L5/L6 教学（12 tool）
│   │     server + engine / session / bkt / bkt_store
│   │     flow_signals / flow_tracker / gain_loop_monitor        (PGFGA 心流)
│   │     memory_store / forgetting_curve / review_scheduler     (L3 长期记忆)
│   │     llm_scorer / error_diagnoser / intent_classifier
│   │     non_judgment_firewall / insight / strategy_selector
│   │     ├── strategies/  reduction / feynman / socratic / analogy / pbl / spaced_repetition / base
│   │     └── tests/(24)
│   ├── digest_mcp/             多模态产物（4 tool / 7 format）
│   │     server + orchestrator + _kg_read
│   │     mindmap / notes / quiz / simulation / multi_agent / slides / audio + tests/(7)
│   └── sync_mcp/               Obsidian + git（6 tool）
│         server + obsidian / git_sync / obsidian_watch + tests/(5)
│
└── tests/                      跨 server 测试
    ├── unit/                   schemas / storage / config / llm / plugins / k3_schema（8）
    ├── integration/            e2e_spine / digest_to_sync_e2e（2）
    └── fixtures/mini_subject.md
```

设计原则：核心代码是标准包布局，移动任何 `.py` 都会破坏 import 与全部 519 个测试——重构时优先保持包路径稳定。

---

## 10. 文档索引

| 文档 | 内容 |
|---|---|
| [HANDOFF.md](./HANDOFF.md) | **接手必读** — 给后续开发者/AI 的交接：状态、约定、雷区、工作流 |
| [ROADMAP.md](./ROADMAP.md) | 18 个切片历史 + 每文件状态 + 461 测试分布 + 剩余项 |
| [INTEGRATION.md](./INTEGRATION.md) | 接 Claude Desktop / Cursor，5 分钟跑通 |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 生产/多机/HTTP 传输/环境变量/数据备份/故障排查 |
| [PGFGA-TUNING.md](./PGFGA-TUNING.md) | 心流/增益回路调参手册 |
| `../使用AI进行学习的技巧/ai-tutor-system-design/` | v3.0 原始设计文档（合同来源） |
