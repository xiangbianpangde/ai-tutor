# AI-Tutor v2 — AI 项目上下文

> **⚠️ 仅供 AI Agent 读取**，新会话自动加载。人类请读 `README.md`。
> 每次功能点完成后更新本文件。

---

## 项目概述

48 小时学完一科的私人 AI 辅导系统。v1 基于 4 个 MCP Server + Claude Desktop；v2 重构为独立 Electron 桌面应用。

**当前阶段**：v1 修复迭代 + v2 计划待 review。INTEGRATED-PLAN 阶段一~三已提交；2026-06-12 完成 22 问题根因调查与 10 项修复（FIX-A~J，根因报告：`doc/reports/根因分析-22问题.md`）。v2 重构计划已编写，待 review 后启动，详见 `doc/plan/`。

## 目录索引

```
ai-tutor/
├── shared/                     # L1 基础设施（所有 server 共用）
│   ├── schemas.py              #   60+ Pydantic 模型 ← 改数据结构先看这里
│   ├── models.py               #   14 个 SQLAlchemy ORM 表
│   ├── errors.py               #   TutorError + 错误码
│   ├── storage.py              #   持久化
│   └── llm_client.py           #   LLM provider 抽象
│
├── servers/                    # 4 个 MCP server（v1 架构，v2 将迁移到 backend/engines/）
│   ├── knowledge_mcp/          #   L4 知识工程 · 9 tool
│   ├── tutoring_mcp/           #   L2/L3/L5/L6 教学 · 13 tool
│   ├── digest_mcp/             #   多模态产物 · 4 tool
│   ├── sync_mcp/               #   Obsidian+git · 6 tool
│   └── dashboard/              #   状态面板（v2 被前端替代）
│
├── doc/                        # 文档
│   ├── plan/                   #   ** v2 重构计划（当前阶段）**
│   │   ├── 背景.md
│   │   ├── 开发清单.md
│   │   ├── design/             #   10 份设计文档（含 research-tool + pdf2zh 集成）
│   │   └── v3.1-aitutor-design/#   ** v3.1 设计包（120 份·2026-06-02 交付）**
│   │       ├── README.md
│   │       ├── REVIEW-CHECKLIST.md
│   │       ├── V3.1-vs-V2-桥接.md  #  17 模块 ↔ 11 功能点映射
│   │       ├── 01-requirement/ 01-requirement/     #  PRD V3.1 + 追溯矩阵
│   │       ├── 02-business/        #  BP/BR/DD/EX/AR
│   │       ├── 03-architecture/    #  4 视图 / 17 模块 / 7 ADR
│   │       ├── 04-tech-architecture/  #  选型/API/部署/安全
│   │       ├── 05-detailed-design/    #  DD/MD/IC/DS
│   │       └── 06-framework/          #  17 模块 M-001~M-017 / 85 份
│   ├── research/               #   调研报告
│   │   └── v3.1-aitutor-research/  #  V3.1 调研（18 个 research-tool run）
│   ├── reports/                #   阶段汇报 / 模拟运行报告
│   │   └── v3.1-aitutor-simulation/  #  V3.1 端到端模拟
│   ├── specs/                  #   11 份 BDD 规格
│   ├── 发现问题.txt             #   21 个测试发现的问题
│   └── ...                     #   旧文档（USAGE / ROADMAP / DESIGN-VS-IMPL...）
│
├── worklogs/                   # AI 工作日志（07-汇报.md 必做）
│   └── 2026-06-02_v3.1-设计交付.md
│
├── scripts/                    # demo + 工具脚本
├── tests/                      # 跨 server 测试
├── data/                       # 运行时数据（SQLite + 文件）
├── pyproject.toml
├── README.md
└── STATUS.md
```

## 架构速查（v1 → v2 迁移）

```
v1: User → Claude Desktop (MCP Host)
            ├── knowledge-mcp (stdio)
            ├── tutoring-mcp (stdio)
            ├── digest-mcp   (stdio)
            └── sync-mcp     (stdio)
                   ↓ 共享
              SQLite (data/tutor.db)

v2: User → Electron App
            ├── React Frontend (HTTP + WebSocket)
            └── Python Backend (FastAPI, single process)
                  ├── engines/knowledge (ex-knowledge-mcp)
                  ├── engines/tutoring  (ex-tutoring-mcp)
                  ├── engines/digest    (ex-digest-mcp)
                  ├── engines/sync      (ex-sync-mcp)
                  └── middleware/       (NEW: Session/Cache/Monitor/Pipeline/RAG)
                        ↓
                  SQLite (data/tutor.db)
```

## 核心规则

1. **阶段感知**：v2 重构（backend/）仍处计划阶段，未经 review 不启动；v1 代码（servers/ + shared/）可修复与增强，改前先看 `doc/reports/根因分析-22问题.md` 避免复发已修根因。
2. **改计划**：修改 `doc/plan/` 下的文件，保持各文件间一致性。
3. **设计文档五段式**：背景/目标/方案/影响范围/风险。只有涉及 3+ 模块的复杂功能才写。
4. **数据保持不变**：SQLite schema 兼容迁移，旧 `data/` 可在 v2 中使用。
5. **测试保持通过**：迁移过程中旧测试继续跑，新测试随新代码添加。

## 规范速查

| 规范 | 文件 | 核心红线 |
|------|------|---------|
| 架构 | - | 禁循环依赖 / 领域层不依赖框架 / 禁跨层调用 |
| 代码 | - | 密钥走环境变量 / SQL 参数化 / 禁 print / 禁静默吞异常 |
| API | - | 名词复数 kebab-case / 统一 JSON 响应 / 向后兼容 |
| 测试 | - | 测试独立 / 只 Mock 外部边界 / 覆盖正常+边界+异常 |
| 文档 | - | 必有 README / CHANGELOG 按 Keep a Changelog / 文档随码同 PR |

> 完整规范在 `C:/Users/yhn/Desktop/开发规范/conventions/`。

## 常见任务速查

| 用户说 | AI 做什么 |
|--------|----------|
| "完善计划" | 读 `doc/plan/` → 分析缺失 → 修改/新增设计文档 |
| "开始开发" | 按 `开发清单.md` 功能点顺序执行，从 #1 开始 |
| "审查计划" | 对照 22 个问题检查覆盖度，检查设计文档间一致性 |
| "修改设计文档 X" | 修改对应 `doc/plan/design/` 文件，同步更新引用的文档 |

## 22 问题对照（来源：`doc/发现问题.txt`；根因+证据：`doc/reports/根因分析-22问题.md`）

> 2026-06-12 完成全部 22 个问题的根因调查；v1 可修的 10 项已修（FIX-A~J），
> 架构级的留给 v2（验收红线已回灌 `doc/plan/开发清单.md`）。

| # | 问题 | 对应功能点 | 对应设计文档 |
|----|------|-----------|-------------|
| 1 | 无调研工具/清洗 | #6 数据管线, #7 research-tool | 设计文档-数据管线, 设计文档-research-tool集成 |
| 2 | 降阶法5万行md | #10 策略升级 | 设计文档-教学策略升级 §1 |
| 3 | 可视化=放屁 | #5 可视化 | 设计文档-前端桌面应用 |
| 4 | MCP调用失败 | #1,#2 骨架+API | 设计文档-总体架构 |
| 5 | 文件结构混乱 | #3 中间件层 | 设计文档-中间件层 §2 |
| 6 | 无会话切换/记忆 | #3 中间件层 | 设计文档-中间件层 §1 |
| 7 | status无自动更新 | #5 可视化 | WebSocket 实时推送 |
| 8 | 需人引导 | #4 前端骨架 | 首次使用向导 |
| 9 | 重检索覆盖不足 | #7 research-tool, #9 RAG | 设计文档-research-tool集成, 设计文档-AgenticRAG |
| 10 | 无休息提醒 | #10 策略升级 | 设计文档-教学策略升级 §4 |
| 11 | 缺缓存/监控 | #3 中间件层, #9 RAG | 设计文档-中间件层 §3,§4 |
| 12 | 无费曼学习法 | #10 策略升级 | 设计文档-教学策略升级 §2 |
| 13 | 看不到遗忘曲线 | #5 可视化 | 设计文档-前端桌面应用 |
| 14 | 调研无本地资料 | #6 数据管线, #7 research-tool | 设计文档-数据管线, 设计文档-research-tool集成 |
| 15 | Agentic RAG | #7 research-tool, #9 RAG | 设计文档-research-tool集成, 设计文档-AgenticRAG |
| 16 | 阶段过渡太猛 | #10 策略升级 | 设计文档-教学策略升级 §3 |
| 17 | 中文论文格式 | #6 数据管线, #8 pdf2zh | 设计文档-数据管线, 设计文档-pdf2zh集成 |
| 18 | 长期幻觉 | #10 策略升级 | 设计文档-教学策略升级 §5 |
| 19 | pdf2zh结合差 | #8 pdf2zh | 设计文档-pdf2zh集成 |
| 20 | AI凭理解运行 | #10 策略升级 | 设计文档-教学策略升级 §6 |
| 21 | 人→Claude→AI | #1 后端骨架, #11 打包 | 设计文档-总体架构 |
| 22 | 标题当概念(KG噪声) | #6 数据管线 | v1 已修（kg_enrich_adapter 围栏跳过+噪声过滤）；v2 内容级抽取 |

## 外部项目速查

| 项目 | 路径 | AI-Tutor 中的用法 |
|------|------|------------------|
| research-tool | `C:/Users/yhn/Desktop/调研/research-tool/` | 采集(10源搜索+抓取)、Deepen(反偏差深挖)、Clean(去噪/去重)、Extract(实体/关系)、Organize(知识树)、Backward(KG质量迭代) |
| pdf2zh | `C:/Users/yhn/pdf2zh/` | PDF→Markdown(MinerU)、PDF→中文Markdown(并发翻译)、多翻译后端(DeepSeek/Ollama/LM Studio) |
