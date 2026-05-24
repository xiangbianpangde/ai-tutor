# HANDOFF — 给接手这个项目的 AI

你正在接手 `ai-tutor`：一个「48 小时学完一科」的私人 AI 辅导系统。这份文档让你**不用重读全部代码就能安全地继续开发**。先读这份，再读 [README.md](./README.md)，需要历史细节查 [ROADMAP.md](./ROADMAP.md)。

---

## 0. 第一件事：读取记忆

用户有一套**持久化文件记忆**，每次会话开头会被加载，但你应主动查阅完整版：

```
C:\Users\yhn\.claude\projects\C--Users-yhn-Desktop---AI-------\memory\
├── MEMORY.md                              ← 索引（一行一条）
├── project_ai_tutor_system.md             ← 项目背景
├── reference_mcp_suite.md                 ← MCP 套件结构
├── reference_code_review_cr1.md           ← ★ 三轮审查 10 个真 bug + 教训（必读）
├── feedback_avoid_malformed_toolcalls.md  ← 工具调用报错现象说明
└── ...
```

**`reference_code_review_cr1.md` 是踩坑地图**，浓缩了本项目最容易再犯的 bug 类型。开发前必读。

记忆写法：一个文件一个事实，frontmatter + body；写完在 `MEMORY.md` 加一行索引。不要把代码已记录的东西（结构/git 历史）写进记忆。

---

## 1. 当前状态（截至交接）

| 维度 | 数值 |
|---|---|
| MCP server | **4 个**：knowledge / tutoring / digest / sync |
| tool | **31 个**，全部实现，无硬 stub（tutoring 新增 cold_start / get_learning_progress / resume_learning） |
| 测试 | **617 passed + 1 skipped**（`uv run pytest`，~39s；含 58 个接入真实实现的 BDD Scenario） |
| 切片 | **23 个**全绿（+ J 降阶法 + CS 冷启动 + P1#4 6策略引擎 + MS 多Session调度 + CG 教学内容LLM生成；**3 个 P0 全部完成**） |
| 代码量 | ~16k 行生产代码 |
| 真 bug 修复 | 11 个（含 Slice P1#4 的 FlowLevel falsy-zero bug） |
| 设计文档 | 7 份概念设计 + 16 份规格 + 2 份审计（`SYSTEM-AUDIT.md` + `48H-SIMULATION.md`） |

**唯一软 stub**：`resolve_conflicts` 的 `contradictory_definition`（需 LLM 语义判定，已能检 5 种结构冲突并优雅跳过语义判定）。功能层面无阻塞性缺口。

**未排期的接口预留**（不是 bug，是设计留口）：
- `acquire_subject` 的 web/video 源（只有 file 源实现）
- 12 种 SemanticRelation 推断（当前只用 part_of + prerequisite_strong）

**新模块**：
- `servers/tutoring_mcp/flow_regulator.py` — 心流调节器（已实现，见 §12.2）
- `servers/tutoring_mcp/strategies/jiangjie.py` — 降阶法策略（**已实现**，Slice J；见 §12.1）
- `ai-tutor-system-design/specs/jiangjie-strategy.md` — 降阶法策略实现规格
- `doc/降阶学习法.md` — 降阶法理论源文档

> 2026-05-23（续）：实现 Slice J 降阶法策略 `JiangjieStrategy`（6 状态机 + 知识骨架
> 产出，16 测试）；strategy_selector 加规则 8（降阶法，置于 overload 规则之后，+4 测试，
> +可选 flow_level 入参）。**注意**：engine 仍未动态选策略也未调 flow_regulator——
> 那属 P1 #4「6 策略引擎」，是下一块更大的集成（见 §11.2 / §13）。

> 2026-05-23：BDD 套件接入真实实现并入 `testpaths`；digest 独立 tool
> `build_quiz_html` / `compile_slides` 已实现（薄封装复用 generator）；digest `grade`
> 年级适配已透传到 notes generator（high_school 直觉优先 / college 形式化优先）。
> 本周期完成系统审计（`SYSTEM-AUDIT.md`）和优化后运行模拟（`48H-SIMULATION.md`），
> 识别出 8 个致命/严重缺口及 10 个优化方向，新增降阶法策略和心流调节器的设计。

---

## 2. 30 秒上手

```powershell
cd C:\Users\yhn\Desktop\ai-tutor
uv sync --extra dev                        # 装依赖
uv run pytest                              # 617 passed + 1 skipped = 健康
uv run python scripts/verify_servers.py    # 4 个 [OK] = server 能起
```

没配 `DEEPSEEK_API_KEY` 也能跑——所有 LLM 路径都有启发式/模板 fallback，测试用 MockLLM。

---

## 3. 架构地图（哪里找什么）

```
shared/                       L1 基础设施（所有 server 共用）
  schemas.py                  ★ 60+ Pydantic 模型；改数据结构从这里开始；extra="forbid"
  models.py                   SQLAlchemy ORM（14 表）；ConceptRow 有 base_id（版本树）
  errors.py                   TutorError + ERROR_CODES（错误码白名单）
  storage.py                  RelationalStore / FileStore；session(expire_on_commit=False)
  config.py                   load_env() + get_deepseek_config()（大小写不敏感）
  llm_client.py               LLMProvider Protocol + MockLLMProvider（chat(messages=)→.content）
  providers/deepseek.py       DeepSeekProvider（OpenAI 兼容）
  llm_cache.py                CachedLLMProvider（LRU L1）

servers/knowledge_mcp/        L4 知识工程（9 tool）
  server.py                   FastMCP 入口；_db()/_llm() 单例
  kg_builder.py               ★ Toc/Concept/Full 三 builder；_enrich_concepts 共用 pipeline
  kg_full.py                  难度校准（确定性公式）+ embedding（numpy hashing）
  kg_enrich_adapter.py        toc 纯规则抽章节 + _persist_kg + _compute_quality + _to_mermaid
  concept_enricher.py         单 concept LLM 富化
  kg_update.py / kg_diff.py / kg_rollback.py   版本树 CRUD
  kg_query.py                 path（最短学习路径）+ subgraph（N 跳邻域）
  resolve_conflicts.py        5 种结构冲突检测（networkx）

servers/tutoring_mcp/         L2/L3/L5/L6 教学（10 tool）
  engine.py                   ★ TeachingEngine：动态选策略(strategy_selector)+调pace(flow_regulator)+respond/next_action/interrupt/checkpoint+心流；next_action 跳过已掌握(mastery≥0.8)
  cold_start.py               ★ 冷启动摸底：选题(band 3/4/3)+判分+BKT先验+画像初值（Slice CS）
  learning_plan.py            ★ 多Session调度：章节切Phase + compute_progress + LearningPlanStore（Slice MS）
  content_generator.py        ★ 教学内容LLM生成：按 action.type 改写模板为真实讲解；gated on supports_generation（Slice CG）
  session.py                  SessionStore（L2 短期记忆）
  strategies/                 教学策略状态机集合
    reduction.py              通用降阶教学流程（INTRO→EXPLAIN→CHECK→...）
    jiangjie.py               ★ 降阶学习法（GOAL→REDUCE→COMPLEMENT→RECONSTRUCT→REVIEW）；产出知识骨架
    feynman.py / socratic.py / analogy.py / pbl.py / spaced_repetition.py
    __init__.py               策略注册表 + 工厂函数
  strategy_selector.py        8 条决策树规则（含降阶法；已集成进 engine，Slice P1#4）
  flow_regulator.py           心流调节器 FlowLevel→PaceConfig（已被 engine.next_action 调用）
  flow_regulator.py           ★ 心流调节器（新增，已实现，见 §12.2）
  flow_signals.py             PGFGA 10 信号提取（纯启发式）
  flow_tracker.py             心流级别状态机（SILENT→SHALLOW→FLUENT→DEEP→IMMERSED）
  gain_loop_monitor.py        4 种增益回路断裂检测 + 修复 action
  llm_scorer.py / error_diagnoser.py / intent_classifier.py
  non_judgment_firewall.py    6 类禁止模式正则检测
  memory_store.py / forgetting_curve.py / review_scheduler.py   L3 长期记忆
  insight.py                  学习者画像洞察聚合

servers/digest_mcp/           多模态产物（4 tool，7 format）
  orchestrator.py             按 formats 分派；单 format 失败不影响其他
  mindmap/notes/quiz/simulation/multi_agent/slides/audio.py
  _kg_read.py                 共享：读 KG + 章节自然排序

servers/sync_mcp/             Obsidian + git（6 tool）
  obsidian.py                 push/pull
  git_sync.py                 git CLI subprocess（bytes+utf-8 防 GBK）
  obsidian_watch.py           mtime 轮询（_now_ref 统一时区）

scripts/                      13 个 demo + init_db + verify_servers
tests/                        集成测试 + fixtures（mini_subject.md）
```

**新增/更新文档**（本周期）：

| 文档 | 定位 |
|------|------|
| `SYSTEM-AUDIT.md` | 当前代码的缺陷分析：8 个缺口 + 15 个子问题，按 P0-P3 分级 |
| `48H-SIMULATION.md` | 全部优化实现后的运行推演：完整章节教学记录 + 心流日志 |
| `ai-tutor-system-design/specs/jiangjie-strategy.md` | 降阶法策略实现规格（给编码者看的状态机定义） |
| `doc/降阶学习法.md` | 降阶法教学理论源文档 |
| (本文件) `doc/HANDOFF.md` | 接手文档（你正在读的这份） |

---

## 4. 开发约定（IMPORTANT — 必须遵守）

1. **严格 TDD**：先写测试让它 RED，再写实现到 GREEN。本项目每个切片都这么做。改 bug 也先写复现测试。
2. **一个切片做完再做下一个**，全量 `uv run pytest` 绿了才算完，并更新 ROADMAP。
3. **stub 要立接口 + 抛 `DEPENDENCY_MISSING`/`PLUGIN_NOT_AVAILABLE` + hint 指向后续**，不要留 `NotImplementedError` 裸奔。
4. **concept.id 格式**：`subject:chapter.section:slug`，必须匹配 `schemas.CONCEPT_ID_PATTERN`，纯 ASCII（中文用 pypinyin 转写）。
5. **错误用 `TutorError(code, hint=)`**，code 必须在 `errors.ERROR_CODES` 白名单里。
6. **LLM 调用统一 `llm.chat(messages=[...])` → `resp.content`**，不是 `.complete()`。
7. **零必需重依赖原则**：新功能若要重库（pptx/tts/向量等），做成 `importlib` 软探测 + 优雅降级，别加进 pyproject 必需依赖。
8. **改 schema 后**：开发期可重建 `data/tutor.db`，但生产用 alembic 迁移。
9. **新的横切模块要可独立调用**（心流调节器就是典型：它不依赖 engine，只依赖 `FlowLevel` + 输入参数，可单测、可复用到其他策略）。

---

## 5. 雷区（这些坑已经踩过，别再踩）

来自三轮 code-review 的 10 个真 bug，全文见 `reference_code_review_cr1.md`。最容易复发的：

- **id 空间不一致**：版本树里 ORM `row.id` 带 `@v` 后缀，但 `full_json["id"]` 是 base id。任何拿 row.id 当 Concept.id 用的代码会炸（pattern 不许 `@`）。涉及 isolated 检测要用对 id 空间（CR1 BUG.3）。
- **双存同步**：`ConceptRow.names_json`（列）和 `full_json["names"]`（JSON）是两份；改一个必须同步另一个，否则下游 `Concept.model_validate(full_json)` 看到旧值（CR1 BUG.6）。
- **时区**：`datetime.utcnow()`（naive UTC）和 `datetime.fromtimestamp()`（naive local）混用会错 8 小时。统一用 helper（如 `obsidian_watch._now_ref`）（CR1 BUG.4）。
- **asyncio.run 嵌套**：同步函数里调 `asyncio.run`，若可能被 async MCP tool 调用 → `RuntimeError`。必须探测 running loop 走 worker thread（`audio.py:_run_async`）（CR2）。
- **HTML 内联 JSON 的 XSS**：往 `<script>` 里塞 JSON 必须 `.replace("</", "<\\/")`，否则 `</script>` 提前闭合脚本块（D2）。
- **死代码 `if False`**：会让整条逻辑分支静默失效，且测试覆盖不到边界时发现不了（CR1 BUG.1）。
- **dict 顺序当优先级**：`intent_classifier._KEYWORDS` 的插入顺序决定匹配优先级，调顺序要写测试钉死（CR1 BUG.7）。
- **Pydantic `model_copy(update=)`** 绕过 validate_assignment——方便但要自己保证值合法。
- **`FlowLevel.SILENT == 0` 是 falsy**：`flow = get_flow() or FlowLevel.FLUENT` 会把真实的 SILENT 吞成 FLUENT（Slice P1#4 踩过）。IntEnum 的 0 值成员永远用 `if x is None` 兜底，别用 `or`。
- **策略内部计数器要持久化**：engine 每轮从 `ctx` 重建策略实例，只靠 `current_strategy_state`(字符串) 无法还原 jiangjie 的 `_atom_index` 等。带计数器的策略必须 override `export_state`/`restore_state`，engine 存进 `ctx.strategy_internal`。否则计数器每轮归零（Slice P1#4）。
- **不要让 `flow_regulator` 成为 engine 的内部对象**：它是独立的调节器，策略和 engine 都可以调用它。如果硬编码到 engine 内部，以后新策略想用自己的心流逻辑就要改 engine——违背"分开实现"原则。

---

## 6. 怎么继续开发一个新切片（推荐工作流）

1. 查 `MEMORY.md` + `reference_code_review_cr1.md`（避免重蹈覆辙）。
2. 在 ROADMAP 找/加切片行，明确目标 + 产出。
3. **写测试文件**（`servers/<x>/tests/test_<feature>.py`），覆盖正常 + 边界 + 错误路径，跑出 RED。
4. 写实现到 GREEN；单 server 测试绿后跑**全量** `uv run pytest`。
5. 真实 demo 验证（写 `scripts/demo_<x>.py` 或内联 python，优先用真实笔记跑一遍——真实数据最会暴露 bug）。
6. 更新 ROADMAP（状态 + 测试数）+ README（如影响全景）。
7. 阶段性跑 `/code-review`（用户触发）做质量门。
8. 把「不能从代码看出的决策/教训」写进 memory。

**测试隔离注意**：`conftest.py` 在项目根；有 autouse fixture 删 `DEEPSEEK_API_KEY` 防止测试误用真实 LLM（慢）。新测试别依赖真实 key。

---

## 7. 关键设计决策（为什么这么做，代码里看不出来）

- **KG 版本树用 `base_id` + `parent_kg_id` 双字段**，不用复合主键——复合主键会破坏 BKT 跨版本掌握度继承。versioned 拷贝时 id 加 `@v` 后缀。
- **难度校准是确定性加权公式不是 XGBoost**——没有真实难度标注数据，未训练的树模型是空中楼阁。`kg_full.py` 注释写明：有学习者答题数据后可无缝换学习模型。
- **PGFGA 心流是基于信号净分的状态机**，不是 spec 里 7 条字面转移规则——为鲁棒性。
- **embedding 用 numpy feature-hashing（64 维）不依赖 sentence-transformers**——零依赖、离线可用；装了 chromadb 才升级专业向量库。
- **降阶法与心流调节器分开实现**：`JiangjieStrategy`（策略）调用 `FlowRegulator`（调节器）获取教学参数。两者是调用关系，不是继承关系——这意味着可以独立测试、独立升级、甚至替换。
- **降阶法不是 ReductionStrategy 的升级版**：它们是两个完全不同的策略。ReductionStrategy 是"讲→问→练"的通用教学流程；降阶法是"GOAL→REDUCE(原子问题)→COMPLEMENT(补集排除)→RECONSTRUCT(骨架重构)"的四步方法论。策略选择器根据学生状态选哪个更合适。

---

## 8. 关于「tool call malformed」报错

本会话频繁出现 `Your tool call was malformed and could not be parsed`。**别被它带偏**：
- 工具其实**成功执行并返回了数据**，错误出现在返回**之后**；
- **不丢数据、不写坏文件**；
- 是会话层间歇性传输/解析现象，疑似超长中文上下文放大，**非你的内容非法**。
- 应对：出现时先看上一步返回值（数据通常在），直接用，别盲目重试同一动作。

详见 `feedback_avoid_malformed_toolcalls.md`。

---

## 9. 文档索引

| 文档 | 用途 |
|---|---|
| [README.md](./README.md) | 全景入口 + 架构 + 快速开始 |
| [ROADMAP.md](./ROADMAP.md) | 18 切片历史 + 每文件状态 + 测试分布 + 剩余项 |
| [SYSTEM-AUDIT.md](../SYSTEM-AUDIT.md) | ★ 当前代码的缺陷分析（必读，决定优先修什么） |
| [48H-SIMULATION.md](../48H-SIMULATION.md) | ★ 优化后系统的运行推演（必读，理解正确的系统行为） |
| [INTEGRATION.md](./INTEGRATION.md) | 接 Claude Desktop（5 分钟） |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 生产/多机/HTTP/备份/故障排查 |
| [PGFGA-TUNING.md](../PGFGA-TUNING.md) | 心流/增益回路调参 |
| `ai-tutor-system-design/specs/jiangjie-strategy.md` | 降阶法策略实现规格 |
| `../使用AI进行学习的技巧/ai-tutor-system-design/` | v3.0 原始设计（合同来源，有歧义时以它为准） |

---

## 10. 项目尚未进 git

交接时项目**还不在版本控制里**。接手后第一个建议动作：`git init` + 首次提交（用户认可后再做；提交信息别用 `--no-verify`）。`.env`、`data/`、`*.db` 应进 `.gitignore`。

---

## 11. 当前缺口速查（来自 SYSTEM-AUDIT.md 的完整分析）

现有代码能跑通 20 概念的 mini-demo，但放大到 800 概念 / 48 小时的真实场景，以下缺口会阻止目标达成。

### 11.1 P0（不修无法运行）

| # | 缺口 | 核心文件 | 说明 |
|---|------|---------|------|
| 1 | ~~教学内容空洞~~ ✅ **已修（Slice CG）** | `content_generator.py` | 引擎 next_action 用 LLM 按 action.type 把模板改写成真实讲解（直觉+例子/练习/提示）；server 在有 DEEPSEEK_API_KEY 时接 DeepSeek。无真实 LLM 时回退模板。 |
| 2 | ~~无冷启动摸底~~ ✅ **已修（Slice CS）** | `cold_start.py` + 2 tool | 10 题跨难度摸底 → BKT 先验种子 + 画像初值；engine 跳过 mastery≥0.8 的概念。真实笔记验证省 ~24% 时间。 |
| 3 | ~~无跨 Session 调度~~ ✅ **已修（Slice MS）** | `learning_plan.py` + 2 tool | 持久化 Phase 化 LearningPlan + `get_learning_progress`/`resume_learning`；跨天答"已掌握 N/M、当前 Phase、今天从【X】继续"。 |

### 11.2 P1（严重影响体验）

| # | 缺口 | 核心文件 | 说明 |
|---|------|---------|------|
| 4 | ~~6 策略仅 1 种可用~~ ✅ **已修（Slice P1#4）** | `engine.py` | engine 现按 mastery/profile/flow 动态选策略 + flow_regulator 调 pace；Strategy 加 export/restore_state，带计数器的策略（jiangjie 等）跨重建无损。 |
| 5 | **KG 无法扩展** | `kg_builder.py` | 逐个 concept 调 LLM，800 概念 ~40min。无 checkpoint、无并行。已验证最大规模仅 20 概念。 |
| 6 | **时间估计全默认值** | `kg_enrich_adapter.py` | 所有概念 typical_learning_time_min=30。200 概念 × 30min = 100h，远超 48h。 |
| 7 | **认知负荷空转** | `engine.py` | ctx.meta.current_cognitive_load 永远是 0.0。策略选择器的 cognitive_load > 0.75 判断永远不触发。 |
| 8 | **教学反馈粗粒度** | `engine.py` | 只有 3 个模板（correct/partial/incorrect），没有 LLM 润色。 |

### 11.3 P2-P3（长期）

| # | 缺口 | 说明 |
|---|------|------|
| 9 | DKT 模型未实现（`dkt_model.py` 🔴） | 无跨概念知识关联推理 |
| 10 | 12 种语义关系只用了 2 种 | KG 是目录树而非知识图谱 |
| 11 | 采集只有 file 源（web/video 🔴） | 设计的多源互补能力缺失 |
| 12 | LearnerProfile 几乎不演化 | 仅 self_assessment_accuracy 在更新 |

---

## 12. 新增模块：降阶法策略 + 心流调节器

这两个模块都**已实现**：降阶法策略 `strategies/jiangjie.py`（Slice J），心流调节器 `flow_regulator.py`。

### 12.1 降阶法策略（已实现，Slice J）

**实现文件**：`servers/tutoring_mcp/strategies/jiangjie.py`（16 测试全绿）

**规格文档**：`ai-tutor-system-design/specs/jiangjie-strategy.md`

**已实现要点**：
- 6 状态机 GOAL→REDUCE→COMPLEMENT→RECONSTRUCT→REVIEW→NEXT（+FLAG_DIFFICULT）
- REDUCE/COMPLEMENT 内部计数器（`_atom_index`/`_error_index`）；REDUCE 答错不推进、COMPLEMENT 答错也推进（补集教学）
- RECONSTRUCT 用 4 个引导问题让学生自述骨架（无 LLM），产出存 `self.skeleton`
- REVIEW 失败用专用 `_review_fail_count` 跨 RECONSTRUCT 往返累计（不被往返清零）
- 消费 PaceConfig（scaffold_level 影响 GOAL 详略，sub_step_count/error_count 控制步数，difficulty_multiplier 透传 REVIEW metadata）
- 已注册到 `_REGISTRY`（key `"jiangjie"`）；strategy_selector 规则 8 已加（见 §11.2 P1 #4 说明）

**已接入 engine（Slice P1#4）**：engine `_make_strategy` 现调用 strategy_selector 动态选策略、
flow_regulator 给 pace 参数。降阶法在 thorough 学习者 / 心流 SILENT / 中高负荷时被自动选中并驱动；
其内部计数器靠 `export_state`/`restore_state` + `ctx.strategy_internal` 跨重建保留。
注意：GOAL→REDUCE 仍需 host 发 `goal_understood` 事件（同 reduction 需 intro_done/explain_done），
respond 只发 `answered`。

**理论源文档**：`doc/降阶学习法.md`

降阶法不是现有 `ReductionStrategy` 的升级版，而是一种**独立的全新策略**。

**核心差异**：
- ReductionStrategy：从定义出发 → 讲解 → 检测 → 练习
- 降阶法：从目标出发 → 拆成原子问题 → 补集排除 → 骨架重构

**状态机**：

```
GOAL → REDUCE → COMPLEMENT → RECONSTRUCT → REVIEW → NEXT
                                      ↑           |
                                      └── fail ───┘
```

**6 个状态**：
- `GOAL`：定义高阶目标（"学完这个你能..."）
- `REDUCE`：降维成 `sub_step_count` 个原子问题，逐个确认
- `COMPLEMENT`：列出 `error_count` 个常见错误，逐一排除
- `RECONSTRUCT`：学生构建知识骨架（前提→逻辑→结论→易错点）
- `REVIEW`：当堂验证（难度由调节器控制）
- `NEXT` / `FLAG_DIFFICULT`

**与心流调节器的结合**：
- 每次 `start()` 时调用 `FlowRegulator.recommend_pace()` 获取教学参数（`PaceConfig`）
- SILENT → diff=0.6, scaffold=3, sub=3, err=5（最温柔）
- IMMERSED → diff=1.4, scaffold=0, sub=4, err=10（最高挑战）
- 认知负荷 > 0.7 时自动修正

**实现注意事项**：
1. `JiangjieStrategy` 继承 `strategies/base.py:Strategy`（三个抽象方法：start/get_action/transition）
2. REDUCE 和 COMPLEMENT 有内部计数器（`_atom_index`, `_error_index`），答错不推进
3. COMPLEMENT 答错时：给出错因解析后仍然推进（补集教学：让学生知道了"为什么错"就算完成）
4. RECONSTRUCT 的骨架不依赖 LLM——用 4 个引导问题让学生自己说
5. 注册到 `_REGISTRY`（`strategies/__init__.py`），key 用 `"jiangjie"`
6. Strategy selector 加规则：cognitive_load>0.6 或心流 SILENT 时优先选降阶法

### 12.2 心流调节器（已实现）

**文件**：`servers/tutoring_mcp/flow_regulator.py`

与 PGFGA 心流追踪的定位区别：
- `flow_tracker.py`：**被动检测** — 10 个信号 → FlowLevel（事后评估）
- `gain_loop_monitor.py`：**被动修复** — 检测 4 种断裂 → 修复 action
- `flow_regulator.py`：**主动调节** — FlowLevel → PaceConfig（**教学动作前**调参）

**核心接口**：

```python
class FlowRegulator:
    def recommend_pace(
        self,
        *,
        flow_level: FlowLevel | int,
        cognitive_load: float = 0.0,
        recent_accuracy: float | None = None,
    ) -> PaceConfig:
        """返回教学参数（难度/脚手架/原子数/错误数）"""
```

`PaceConfig` 包含 6 个字段，降阶法策略将其作为 `params` 传入：
- `difficulty_multiplier`（0.5-1.5）
- `scaffold_level`（0-3）
- `sub_step_count`（原子问题数）
- `error_count`（补集枚举数）
- `confirm_each_step`（是否逐条确认）
- `label`（日志标签）

**修正逻辑**：
- 认知负荷 > 0.7：自动降难度 15% + 升脚手架 + 减少原子数
- 最近 3 轮正确率 < 30%：降难度 20% + 升脚手架 + 增加错误数
- 正确率 > 90% 且心流 ≥ FLUENT：升难度 15% + 降脚手架

**使用方式**（策略内部调用）：

```python
from tutors_mcp.flow_regulator import get_regulator

pace = get_regulator().recommend_pace(
    flow_level=FlowLevel.FLUENT,
    cognitive_load=0.3,
    recent_accuracy=0.85,
)
params = pace.to_dict()
strat.start(target=concept, mastery_map={}, params=params)
```

---

## 13. 10 项优化方向优先级

来自 `SYSTEM-AUDIT.md` 的 10 项优化，按优先级排列。

```
Week 1-2（3 个 P0 全部完成 ✅）：
  P0 #1: 教学内容生成（LLM 替代模板填空）—— ✅ 已完成（Slice CG）
  P0 #2: 冷启动摸底（10 题 + 自适应跳过）—— ✅ 已完成（Slice CS），省 ~24% 时间
  P0 #3: 多 Session 调度（LearningPlan + Phase）—— ✅ 已完成（Slice MS）

Week 3-4（P1 严重缺陷）：
  P1 #4: 6 策略引擎（集成 strategy_selector + flow_regulator 到 engine）—— ✅ 已完成（Slice P1#4）
  P1 #5: 批量 KG 管道（批量 enrich + checkpoint + 并行）
  P1 #6: 认知负荷估计（在线更新 ctx.meta.current_cognitive_load）
  P1 #7: 教学反馈分级（L1→L2→L3 三级管道 + LLM 润色）
  P1 #8: 时间校准（加权公式 + 运行时更新）

后续（P2-P3）：
  P2 #9: DKT 模型
  P3 #10: 12 种关系挖掘
```

新接手者应优先实现 **P0 #2（冷启动摸底）**——投入产出比最高，1-2 天可完成，直接减少用户无效学习时间。然后实现 **P0 #1（教学内容生成）**——这是优化后系统模拟中的教学根基。`48H-SIMULATION.md` 展示了这三个 P0 完成后的系统行为。

---

## 14. 需要理解的关键数据流

### 14.1 降阶法 × 心流调节器的协同

完整流程在 `48H-SIMULATION.md` §3（心流调节器全流程日志）有真实数据：

```
next_action():
  1. strategy_selector.select_strategy() → "jiangjie"
  2. flow_regulator.recommend_pace(flow_level, cognitive_load, accuracy)
     → PaceConfig { diff, scaffold, sub_count, err_count, ... }
  3. strat.start(target=concept, mastery_map={}, params=pace.to_dict())
  4. action = strat.get_action()  // 当前状态对应的教学动作
  5. 返回 action

respond():
  1. 评分 + 更新 BKT
  2. strat.transition("answered", {correctness})  // 推进状态机
  3. 更新 flow_signals + flow_level
  4. gain_loop_monitor 检测断裂
  5. 更新 cognitive_load
  6. 返回 feedback + next_action
```

### 14.2 里程碑完成

一个"里程碑" = 一个章节。完整路径：

```
章节概览 → (概念 × N，每概念走降阶法 4 步) → 章节出口验证 → 知识骨架汇总
```

出口验证：综合题检验整章概念的整合运用。答错 → 回溯到具体概念修正骨架。完成时该章节所有概念的知识骨架持久化，BKT 掌握度记录入表。

---

## 15. 新开发者的常见问题

**Q: 先修哪个 P0？**
A: P0 #2（冷启动摸底）— 独立、不影响其他模块，1-2 天完成。

**Q: 降阶法策略要优先实现吗？**
A: 是的。规格文档已完整（`jiangjie-strategy.md`），`flow_regulator.py` 已实现可直接调用。实现周期约 2-3 天（含测试）。

**Q: 怎么验证降阶法实现正确？**
A: 写单测覆盖 6 个状态的 transition 路径（完整路径 + 答错回溯 + FLAG_DIFFICULT），调通后用真实笔记跑 `demo_full_workflow.py` + 内联 exploration。

**Q: 模拟文档里的教学场景是真实的吗？**
A: `48H-SIMULATION.md` 展示的是"全部优化完成后"的运行推演——它定义了正确的系统行为。每个场景都可以作为验收标准。目前系统还没达到那个状态，差距由 `SYSTEM-AUDIT.md` 定量描述。

**Q: `flow_regulator.py` 已经写了，还能改吗？**
A: 可以改。它是新模块，没有生产依赖。但改之前读 `48H-SIMULATION.md` §3（心流日志）——那 22 行调参记录定义了它的期望行为边界。
