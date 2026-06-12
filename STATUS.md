# AI-Tutor 开发状态

> 更新: 2026-06-12（22 问题根因调查完成 + 10 项 v1 修复落地）
> 流程档位: 标准
> 收束节点: 功能点3后 / 功能点7后 / 功能点11后

---

## v1 总体进度（已完成）

| 维度 | 状态 |
|------|------|
| MCP server | 4/4 ✅ |
| Tool 总数 | 32 ✅ |
| 教学策略 | 7（2 完整 + 5 精简）|
| 测试 | 786 全绿（2026-06-12）|
| 架构 | MCP Server + Claude Desktop |

## 2026-06-12 · 22 问题根因调查与修复

> 根因报告（每问题：现象→根因 file:line→修复→落点）：`doc/reports/根因分析-22问题.md`
> 22 问题归结为 5 条系统性根因：R1 语料缺整理 / R2 标题当概念 / R3 引擎↔宿主契约模糊 / R4 MCP 长事务不匹配 / R5 横切关注点无接线

| 修复 | 内容 | 修的问题 |
|------|------|---------|
| FIX-A | 标题解析治理：代码围栏跳过 + 噪声标题过滤 + 重复名告警（kg_enrich_adapter）| #22 #1 #3 |
| FIX-B | 合并语料治理：真实标题(`<!--title-->`) + 剥元数据 + 标题降级 + 薄残文跳过（research_adapter）| #1 #22 |
| FIX-C | acquire 多源合并 `00_corpus.md`——KG 不再只吃第一个源（acquisition_adapter）| #8 #14 |
| FIX-D | 判分题目感知：score(+question)，答非所问最高 partial（llm_scorer/engine/cold_start）| #18 #20 |
| FIX-E | PRACTICE 死循环修复：接受 answered 事件（reduction）| #16 #20 |
| FIX-F | 连续学习 ≥50min → 主动休息建议；接线 total_elapsed/active_time（engine/schemas）| #10 |
| FIX-G | feynman 选择器门槛可达（默认画像即可触发）| #12 |
| FIX-H | 中文 PDF 语种映射 zh→ch 收尾 + 回归测试（pdf_parser）| #17 #19 |
| FIX-I | 调研 deepen 开关：LLM 拆 3-5 子面分别采集归并（research_adapter，默认关）| #9 #15 |
| FIX-J | digest 新产物 study_pack：语料拆 15-30min/份 + 索引（替代手工拆 121 份）| #2 #8 |

**真实语料验证**：ACP 75,393 行 merged md 重过新解析器——概念 356→211，噪声 126→**0**。
**架构级问题**（#3#4#5#6#7#11#15#21）：根因确认在 v1 架构，修复落 v2（验收红线已写入 `doc/plan/开发清单.md`），v1 不再投入。

---

## v2 重构进度

| 功能点 | BDD 规格 | 状态 | 完成日期 |
|--------|---------|------|---------|
| 1 后端骨架：FastAPI 统一应用 | specs/01-基础骨架.md | ⏳ 待开始 | - |
| 2 API 迁移：MCP → REST | specs/02-API迁移.md | ⏳ 待开始 | - |
| 3 中间件层：Session/File/Cache/Monitor | specs/03-中间件层.md | ⏳ 待开始 | - |
| 4 Electron 前端骨架 | specs/04-前端应用.md | ⏳ 待开始 | - |
| 5 可视化：KG图/遗忘曲线/掌握度 | specs/05-可视化.md | ⏳ 待开始 | - |
| 6 数据管线：采集→清洗→结构化 | specs/06-数据管线.md | ⏳ 待开始 | - |
| 7 research-tool 深度集成 | specs/07-research-tool集成.md | ⏳ 待开始 | - |
| 8 pdf2zh 深度集成 | specs/08-pdf2zh集成.md | ⏳ 待开始 | - |
| 9 Agentic RAG + 缓存 + 监控 | specs/09-AgenticRAG.md | ⏳ 待开始 | - |
| 10 策略升级 + 健康监控 + 幻觉检测 | specs/10-策略升级.md | ⏳ 待开始 | - |
| 11 打包发布：Electron + Python 嵌入 | specs/11-打包发布.md | ⏳ 待开始 | - |

## 收束节点历史

（尚无 — 计划阶段）

## v3.1 设计包交付（2026-06-02 · plan-writing 工作流）

| 维度 | 数值 | 路径 |
|------|------|------|
| 项目代号 | AITutor V3.1 | — |
| 阶段状态 | ⏸️ 计划阶段交付 · 待 review | `doc/plan/v3.1-aitutor-design/` |
| 设计包大小 | ~120 份文件 | 7 子目录 + research/ + reports/ |
| 7 棒收敛指数 | CCI=0.988 / RCI=0.997 / CTI=0.97 / TDI=0.97 / ARI=0.99 / DDI=0.96 / FRI(avg)=0.995 | `convergence-summary.md` |
| 全部指数 vs 0.85 门禁 | 7/7 ✅ | — |
| 模块数 | 17 个 M-NNN（M-001~M-017）/ D7=100 全过 | `06-framework/` |
| 调研工具 | 18 个真实 run / 865+ 来源 / 57 S/A 级 | `doc/research/v3.1-aitutor-research/` |
| 端到端模拟 | 15 拍可走通（7.8s）+ 3 异常分支 | `doc/reports/v3.1-aitutor-simulation/` |
| PRD 迭代 | 4 轮（V1→V2→V3→V3.1）/ 22-22 RA 反馈全采纳 / 0 硬回退 | — |
| 关键决策 | HaluGate 三级级联 / LangGraph 1.0 / FastAPI 0.115 / Python 3.11 | `04-tech-architecture/` |
| 风险项 | 5 项（详见 `REVIEW-CHECKLIST.md` §关键风险）| — |

### v3.1 ↔ v2 关系
- v3.1 是 v2 的**细化升级 + 局部重整**——**不替代**，**并行保留**
- 17 模块 ↔ 11 功能点 完整映射见 `doc/plan/v3.1-aitutor-design/V3.1-vs-V2-桥接.md`
- 推荐策略：v2 主体推进 + v3.1 引入的 3 个新模块（事件总线 M-006 / 打包调度 M-015 / 红线编排 M-016）作为增量补充

### v3.1 待 review 项
- [ ] 1 小时 review：按 `REVIEW-CHECKLIST.md` 7 段 60min 路线走一遍
- [ ] 决定 v3.1 走向（推荐选项 C：v2 主体 + v3.1 增量）
- [ ] 跟 v2 现有 10 份 `doc/plan/design/` 做交叉引用（见 V3.1-vs-V2-桥接.md §六 桥接速查）

## v3.1 之后需要完成的内容（2026-06-02 增）

> 范围：v3.1 review 通过后到正式开发结束期间的所有待办。按优先级排序，每项标 ☐ 未开始 / ◐ 进行中 / ✅ 已完成。

### 阶段 A · Review 收束（预计 1-2 天）
- ☐ **A1** 按 `REVIEW-CHECKLIST.md` 7 段 60min 路线 review 完（最关键 5 风险：R-16/R1/C2/pdf2zh AGPL/sqlite-vec）
- ☐ **A2** 决定 v3.1 走向（A/B/C/D 四选一，推荐 C），写入 `worklogs/YYYY-MM-DD_v3.1-走向决议.md`
- ☐ **A3** 写 v3.1 收束报告（按 07-汇报.md 二档）→ 落盘 `doc/reports/收束报告-v3.1.md`
- ☐ **A4** v2 现有 10 份 `doc/plan/design/` 与 v3.1 17 模块交叉引用，输出冲突/重复/补充清单

### 阶段 B · 开发准备（预计 1-2 天）
- ☐ **B1** Git 仓库状态检查（`git status` + 确认 `main` 干净）
- ☐ **B2** 配置 pre-commit：import-linter / ruff / pre-commit / spectral（按 `开发规范/02-coding_代码编写规范.md §二`）
- ☐ **B3** 锁版本：`uv.lock` 检查 / sqlite-vec 0.1.x / pdf2zh / FastAPI 0.115
- ☐ **B4** 启动 `ai-tutor/ai-tutor-system-design/` → 备份为 `v3.1-aitutor-design/历史快照/`（DEVELOPMENT-NORM §一 不轻易加新文件原则）
- ☐ **B5** 风险处置预案：
  - pdf2zh AGPL 法务审查（联系法务）
  - sqlite-vec 0.1.x 锁定 + 上游监控
  - M-008 内聚度细化（DD-M 阶段补）

### 阶段 C · 开发启动（5 波推进，按 V3.1↔V2 桥接 §四）
- ☐ **C1 第一波** M-001 服务入口 + M-002 API 网关 + M-003 客户端入口（对应 v2 #1+#2+#4）
- ☐ **C2 第二波** M-004 Session + M-005 Cache + M-006 事件总线 + M-007 Pipeline 调度 + M-014 数据管线（对应 v2 #3+#6+#7+#8）
- ☐ **C3 第三波** M-008 RAG 引擎 + M-009 教学编排（对应 v2 #9+#10 部分）
- ☐ **C4 第四波** M-010 费曼 + M-011 FSRS + M-012 阶段校准 + M-013 长期记忆 + M-016 红线编排（对应 v2 #10 拆分）
- ☐ **C5 第五波** M-015 打包调度 + M-001 收尾（对应 v2 #11）

### 阶段 D · 收束节点（按 03-第一步.md 1.6 预设 + 06-第三步_收束节点.md）
- ☐ **D1** 收束节点 1：C1 完成后（后端骨架 + API + 前端入口齐备）→ 走四阶段收束
- ☐ **D2** 收束节点 2：C3 完成后（核心引擎就位）→ 走四阶段收束
- ☐ **D3** 收束节点 3：C5 完成后（v2 11 功能点全过）→ 走四阶段收束 + ADR + 收束报告落盘

### 阶段 E · 持续维护
- ☐ **E1** 每功能点完成后按 07-汇报.md 更新 STATUS + worklog + （如变）FILE_GRAPH
- ☐ **E2** 每收束节点完成后写收束报告（落盘 `doc/reports/`）
- ☐ **E3** 监控 5 项关键风险状态（季度复审）

## 外部依赖清单

| 项目 | 路径 | 用途 | 集成方式 |
|------|------|------|---------|
| research-tool | `../调研/research-tool/` | 采集/检索/KG构建 | Python import（本地路径依赖） |
| pdf2zh | `C:/Users/yhn/pdf2zh/` | PDF解析+翻译 | subprocess 隔离调用 |

---

## 模块级状态

### knowledge-mcp（L4 知识工程）— 9 tool — ✅ 全实现

| Tool | 状态 | 说明 |
|------|------|------|
| `acquire_subject` | ✅ file / 🟡 web+video | 多源签名已就位，web/video 未实现 |
| `build_knowledge_graph` | ✅ | depth ∈ {toc, concept, full} 全部实现 |
| `query_knowledge` | ✅ | concept / neighbors / path / subgraph |
| `review_kg` | ✅ | quick + full + Mermaid |
| `update_kg` | ✅ | 6 op + versioned 模式 |
| `diff_kg` | ✅ | base_id 对齐版间 diff |
| `rollback_kg` | ✅ | 版本树回滚 |
| `resolve_conflicts` | ✅ | 5 种结构冲突检测 |
| `health` | ✅ | |

### tutoring-mcp（L2/L3/L5/L6 教学）— 12 tool — ✅ 全实现

| Tool | 状态 | 说明 |
|------|------|------|
| `cold_start_probe` | ✅ | 10 道跨难度摸底 |
| `submit_cold_start` | ✅ | 判分 → 先验 + 画像初值 |
| `start_learning_session` | ✅ | Phase 化教学计划 |
| `resume_learning` | ✅ | 续学恢复 |
| `get_learning_progress` | ✅ | 跨 Session 进度 |
| `respond` | ✅ | 评分→诊断→反馈→策略→心流 |
| `next_action` | ✅ | 拓扑序 + BKT 推荐 |
| `interrupt` | ✅ | 5 类意图分类 + 分支响应 |
| `checkpoint` | ✅ | 保存/恢复断点 |
| `learning_insight` | ✅ | 画像洞察 |
| `generate_review_plan` | ✅ | 遗忘曲线复习排程 |
| `health` | ✅ | |

### digest-mcp（多模态产物）— 4 tool — ✅ 全实现

| Tool | 状态 | 说明 |
|------|------|------|
| `digest` | ✅ | 7 种 format（mindmap/notes/quiz/simulation/multi_agent/slides/audio） |
| `build_quiz_html` | ✅ | 独立测验入口 |
| `compile_slides` | ✅ | 独立幻灯片入口（有 pptx→.pptx，否则 HTML） |
| `health` | ✅ | |

### sync-mcp（Obsidian + git）— 6 tool — ✅ 全实现

| Tool | 状态 | 说明 |
|------|------|------|
| `push_to_obsidian` | ✅ | |
| `pull_homework_from_obsidian` | ✅ | |
| `init_subject_repo` | ✅ | git 初始化 |
| `push_artifacts` | ✅ | git 版本化 |
| `watch_obsidian` | ✅ | mtime 轮询 |
| `health` | ✅ | |

### 教学策略 — 7 策略

| 策略 | 状态 | 说明 |
|------|------|------|
| `reduction` | ✅ | 完整状态机 |
| `jiangjie`（降阶法） | ✅ | 完整状态机，消费 PaceConfig |
| `feynman` | 🟡 | 精简状态机 IDLE→PROMPT→EVALUATE→PASS |
| `socratic` | 🟡 | 精简状态机 |
| `pbl` | 🟡 | 精简状态机 |
| `analogy` | 🟡 | 精简状态机 |
| `spaced_repetition` | 🟡 | 精简状态机 |

> 🟡 = 接口完整可调用，状态机可推进，但缺少深度行为（自动评分、自适应、完整状态分支）。
> 这些策略在实际教学中可被 engine 选中并执行，但教学效果不如 reduction 和 jiangjie 充分。

### L5 学习者建模 — 4 模块尚未创建

| 模块 | 状态 | 说明 |
|------|------|------|
| `tracer.py` | 🔴 未创建 | BKT+DKT 双模型知识追踪 |
| `dkt_model.py` | 🔴 未创建 | PyTorch DKT（Phase 3+） |
| `error_diagnosis.py` | 🔴 未创建 | L5 错误诊断聚合 |
| `profiler.py` | 🔴 未创建 | ProfileEvolver |

---

## 代码结构速查

```
ai-tutor/
├── shared/                    L1 基础设施（所有 server 共用）
│   ├── schemas.py             60+ Pydantic 模型 ← 改数据结构先看这里
│   ├── models.py              14 个 SQLAlchemy ORM 表
│   ├── errors.py              TutorError + 错误码
│   ├── storage.py             持久化
│   ├── config.py / logging_config.py / plugins.py / slug.py
│   └── llm_client.py / llm_cache.py + providers/
│
├── servers/
│   ├── knowledge_mcp/         19 文件 · 9 tool
│   ├── tutoring_mcp/          27 文件 · 12 tool · 7 策略
│   ├── digest_mcp/            复习产物生成
│   └── sync_mcp/              Obsidian + git 同步
│
├── scripts/                   demo + 工具（13 文件）
├── doc/                       文档（15 文件）
├── ai-tutor-system-design/    设计历史（40+ 文件）
└── tests/ + BDD/              测试
```

---

## 开发规范化

见 [`DEVELOPMENT-NORM.md`](./DEVELOPMENT-NORM.md)，包含：
- 文件增长控制原则（能加进已有文件就不加新文件）
- 增量添加规范
- 文档同步规则
- 迭代结束清理清单

---

## 下一步做什么（2026-06-12 更新）

**当前阶段**：22 问题根因修复已落地（FIX-A~J，786 测试全绿），**下一步先用真实科目复跑验证修复，再走 v3.1 review → v2 开发**。

按顺序做：

1. **真实复跑验证（半天 · 最优先）**：选一个**新科目**（别用 ACP 旧数据），端到端走
   `uv sync --extra research` → acquire(web, deepen=true) → build_kg(full) → review_kg →
   digest(study_pack) → 教学 15-20 步。⚠️ 注意：tutor.db 里旧 ACP KG（356 概念）是修复前
   的噪声版，只能当反面教材，不要拿它演示。
2. **A1/A2 · v3.1 review + 走向决议（1 小时）**：按 `doc/plan/v3.1-aitutor-design/REVIEW-CHECKLIST.md`
   走完，A/B/C/D 四选一（推荐 C：v2 主体 + v3.1 增量），写入 worklog。这是 v2 动工的唯一阻塞项。
3. **B 阶段开发准备（1-2 天）**：pre-commit（ruff/import-linter）、锁版本（sqlite-vec/FastAPI）、
   pdf2zh AGPL 法务、设计包快照备份。
4. **C1 第一波动工**：M-001 服务入口 + M-002 API 网关 + M-003 客户端入口。
   ⚠️ 按根因报告 §三的优先级修正：**M-014 数据管线（整理环节）提前到第一/第二波**——
   数据质量是教学/可视化/复习一切下游的瓶颈，比前端更紧迫。

## 接手挑战清单（谁接手谁过堂，过不了别说"做完了"）

> 来源：22 问题根因调查（`doc/reports/根因分析-22问题.md`）。每条都是可证伪的验收，
> 对应一个曾经真实发生的失败模式。

- [ ] **裸手跑通**：新科目端到端（上面第 1 步）全程**不写一行临时脚本**。写了，#8（需人引导）就没好。
- [ ] **噪声率过堂**：build_kg 后贴出 quality_report + 随机抽 30 个概念名——噪声率 <5%，
      文件名/代码注释/整句话概念 = 0（ACP 基线曾是 35%）。
- [ ] **答非所问攻击**：任取 3 道题，各给一个"内容沾边但不回答题目"的答案——correct 判定必须 0 个。
- [ ] **死循环回归**：教学 20 步，give_exercise 占比 <50%，且必须出现 explain/讲解类动作穿插
      （曾经：15 步里 14 步连发练习）。
- [ ] **休息触发**：连续学习 55 分钟（或 freezegun 模拟），必须收到 break_suggestion——不许靠答错题触发。
- [ ] **v2 第一波过堂**（动工后适用）：build_kg 必须是异步任务+进度可查（单 HTTP 调用超时 = 不及格）；
      同一问题问两遍第二遍命中缓存；进程重启后会话可续。
- [ ] **终极验收（#21）**：把 Claude Desktop 从流程里完全删掉，让一个不懂代码的人从安装走到
      学完第一课。做不到，"人→AI→ai-tutor"的三层架构就还在。

> 把你的当前目标写在这里，下次回来直接看这行就知道做什么。
