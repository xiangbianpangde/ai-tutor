# 设计 vs 实现 — 逐层比对报告

> 设计源：`ai-tutor-system-design/` v3.0 七层认知架构（2026-05-19）
> 实现：`C:\Users\yhn\Desktop\ai-tutor`（截至 2026-05-25）
> 判定标记：✅ 完成 | 🟡 部分完成/简化 | 🔴 未实现

---

## 总览

| 维度 | 设计目标 | 实现状态 |
|------|---------|---------|
| 架构层数 | 7 层 | 7 层全部覆盖 |
| MCP Server | 4 个 | 4 个全部实现 |
| MCP Tool | ~15 个（设计文档数） | 32 个（实际拆分更细） |
| 教学策略 | 6 种 | 7 种（含降阶法 Jiangjie） |
| 语义关系 | 12 种 | 3 种实现，9 种未实现 |
| 测试 | 目标验收 48h 实验 | 672 测试全绿 |
| 核心缺失 | DKT / 知识网络 / 多源融合 / 画像演化 | 见下方逐层明细 |

---

## 一、L1 基础设施

| 设计项 | 状态 | 说明 |
|--------|------|------|
| FileStore（本地/S3） | ✅ | `storage.py:LocalFileStore`，S3 未实现 |
| RelationalStore（SQLAlchemy） | ✅ | `storage.py:RelationalStore`；14 表全部落地 |
| StateStore（Redis/Memory） | 🔴 | 设计为独立 Redis/Memory 状态存储层；实现中会话状态通过 RelationalStore (SQLite) 持久化，无 Redis。L1 进程内存缓存未独立抽象 |
| VectorStore（ChromaDB/PGVector） | 🟡 | `kg_full.py` 写 numpy 64 维 embedding；chromadb 可选探测，缺则降级。无独立 VectorStore 抽象类 |
| 插件注册表 PLUGIN_REGISTRY | 🟡 | `plugins.py` 有 PluginRegistry + Plugin Protocol。但 pdf_parse/transcription/image_generation 多 provider 级联选择未实现。仅 LLM provider 有多实现（Stub/Mock/DeepSeek） |
| 认证（Bearer Token） | 🔴 | 设计 HTTP 模式需要；当前仅 stdio 模式，未实现认证中间件 |
| 错误模型（TutorError） | ✅ | `errors.py`：TutorError + 15 错误码，完全匹配设计 |
| 结构化日志（structlog） | ✅ | `logging_config.py`：structlog JSON 格式 |
| 并发模型（无状态 tool） | ✅ | 所有 tool 无进程内状态，通过 SQLite 共享 |
| 项目结构 | ✅ | 与设计 `L1-infrastructure.md` §7 高度吻合 |

**L1 差距评估**：基础骨架完整。StateStore 和 VectorStore 的设计抽象未落地，但功能被 RelationalStore + 可选 chromadb 覆盖。多 provider 插件级联是本层最大缺口。

---

## 二、L2 短期记忆

| 设计项 | 状态 | 说明 |
|--------|------|------|
| SessionContext 数据结构 | ✅ | `session.py`：完整实现，含 current / interrupt_checkpoint / recent_history / focus / meta / session_stats / strategy_internal 等字段。比设计多出 strategy_internal（策略内部计数器跨重建无损） |
| 三层缓存架构（L1 进程→L2 Redis→L3 SQLite） | 🔴 | 仅 L3 SQLite 实现。无 Redis 层，无 L1 独立进程内存缓存抽象。功能可用但不具备跨进程/跨重启恢复能力 |
| 聚焦管理（switch_focus） | ✅ | 通过 SessionContext.focus 字段 + engine 内逻辑实现 |
| 上下文窗口（get_context_window） | ✅ | engine 从 recent_history 取最近 N 轮 |
| 中断/恢复协议 | ✅ | `checkpoint` tool + `interrupt` tool 保存断点；支持 self_summary / test_result 两种模式。TTL 设计（24h）未独立实现，依赖 SQLite 持久化 |
| Redis 键设计 | 🔴 | 无 Redis，所有状态走 SQLite |

**L2 差距评估**：核心功能全部可用（会话上下文、聚焦、中断恢复）。缺失 Redis 中间层意味着不能跨进程共享会话、不能自动 TTL 过期。对单用户单机场景无影响。

---

## 三、L3 长期记忆引擎

| 设计项 | 状态 | 说明 |
|--------|------|------|
| 个性化遗忘曲线（指数衰减 + scipy 拟合） | ✅ | `forgetting_curve.py`：`collect_data_point` → `fit_lambda` (scipy.curve_fit) → `predict_recall` → `next_review_at`。冷启动默认 λ 按难度分级（easy/medium/hard） |
| λ 混合策略（冷启动→加权混合→个性化） | 🟡 | 冷启动值实现；数据点 3-5 时加权混合逻辑未实现，直接切换到拟合值 |
| 学生知识网络（StudentKnowledgeNetwork） | 🔴 | `knowledge_network.py` 标记 🔴 未开始。设计中的节点（StudentConceptNode）、边（StudentDiscoveredEdge）、网络指标、连接发现全部未实现 |
| 跨科目知识关联 | 🔴 | 设计 §2.3，未实现 |
| 多因子复习调度器 | ✅ | `review_scheduler.py`： urgency + prereq_importance + downstream_impact + difficulty_weight + student_aversion 五因子加权 |
| 每日复习计划生成 | ✅ | `generate_review_plan` tool |
| 复习模式自动选择（quick_quiz / concept_map / teach_back / error_revisit） | ✅ | `review_scheduler.py`：4 种模式，按 mastery + error_history 自动选 |
| 复习后更新闭环 | ✅ | engine 每次 respond 后自动 record；更新 λ、review_streak |
| L3↔L5/L6 接口 | ✅ | engine 读取 review_suggestion 插入复习节点；L5 交互记录推送 L3 |

**L3 差距评估**：遗忘曲线 + 复习调度完整实现。学生知识网络是整个 L3 设计中最核心的"构建学生脑内知识联接"能力，目前完全缺失。跨科目关联也未实现。这两个是 Phase 3+ 的大项。

---

## 四、L4 知识工程引擎

| 设计项 | 状态 | 说明 |
|--------|------|------|
| 概念节点（20+ 字段） | ✅ | `schemas.py:Concept`：id/names/category/definition/informal_description/attributes/classification/difficulty/examples/counter_examples/common_misconceptions/linguistic_signals/sources/confidence。设计中的 bloom_level/domain 未显式建模 |
| 12 种语义关系 | 🔴 | 仅实现 3 种：`prerequisite_strong`、`part_of`、`analogous_to`。缺失 9 种：`is_a`、`prerequisite_weak`、`contradicts`、`generalizes`、`instantiates`、`proves`、`computed_from`、`common_pitfall`、`historical_origin` |
| 知识抽取流水线（6 阶段） | 🟡 | 实现为 `toc`（纯规则章节骨架）+ `concept`（LLM 富化）+ `full`（+难度校准+embedding）。设计中的 Passage Splitter（LLM 边界校验）、独立 Concept Detector、独立 Relation Extractor 未作为独立阶段实现。LLM 在单个 prompt 中同时做概念识别+关系抽取+属性填充 |
| 难度评分 | ✅ | `kg_full.py`：确定性加权公式（cognitive_load 0.3 + formula_density 0.2 + abstract_level 0.2 + depth 0.15 + time 0.15），替代设计中的 XGBoost 回归（无训练数据） |
| Embedding Indexer | ✅ | `kg_full.py`：numpy feature-hashing（中文 2-gram，64 维 L2 归一）；可选 chromadb |
| Quality Gate（6 项检查） | ✅ | `resolve_conflicts` 检测 5 种结构冲突（环/反向前置/重复/悬空边/孤岛）；`review_kg` 质量报告。设计中的"章节覆盖率≥85%"、"每概念≥1示例"、"定义/定理/公式分布合理"未做结构化检查，依赖人工审查 |
| 多源融合（知识融合引擎） | 🔴 | 设计 §3：多源对齐（align_concepts）、冲突检测与仲裁（detect_conflicts + resolve_conflicts）。完全未实现。当前仅支持单源（一个 corpus → 一个 KG） |
| KG 版本管理 | ✅ | 完整实现：base_id + parent_kg_id 版本树、versioned 更新、diff_kg、rollback_kg、审计追踪 |
| 增量更新算法（delta_update） | 🔴 | 设计 §4：对已有 KG 做增量更新（新 corpus → 对齐 → delta.json）。未实现 |
| MCP Tool（9 个） | ✅ | acquire_subject / build_knowledge_graph(3 depth) / query_knowledge(4 type) / review_kg / update_kg(versioned) / diff_kg / rollback_kg / resolve_conflicts / health |
| 学习时长校准 | ✅ | `time_estimator.py`：非时间特征加权 → 5-45min，替代恒 30。含 calibrate_time 观测加权钩子 |
| 批量并行富化 | ✅ | `batch_enrich.py`：ThreadPoolExecutor + JSONL 断点续跑 |

**L4 差距评估**：KG 核心闭环完整（采集→建图→审查→更新→版本管理→查询）。最显著缺口：12 种语义关系仅实现 3 种（直接影响知识图谱的表达力）；多源融合完全缺失（当前只支持单一资料源）；知识抽取流水线简化为一阶段 LLM 调用（效果可能不如分阶段管道精细，但工程上更可行）。

---

## 五、L5 学习者建模

| 设计项 | 状态 | 说明 |
|--------|------|------|
| BKT 贝叶斯知识追踪 | ✅ | `bkt.py`：完整四参数模型（p_learn/p_guess/p_slip/p_init），贝叶斯更新公式完全匹配设计 §1.2 |
| BKT 持久化 + 冷启动先验 | ✅ | `bkt_store.py`：bkt_params 表、seed_prior（不覆盖真实观测）、跨版本继承（base_id） |
| DKT 深度学习知识追踪 | 🔴 | `dkt_model.py` + `tracer.py` 标记 🔴。设计 §1.1 的 LSTM+Dense 架构、双模型协作（偏差>0.2 触发诊断、uncertainty>0.3 回退 BKT）全部未实现 |
| 错误类型诊断（10 种） | ✅ | `error_diagnoser.py`：10 种 ErrorType 完全匹配设计 §2.1 |
| 诊断规则引擎 | 🟡 | 设计中的正则 ERROR_PATTERNS + LLM 深度分析 + KG 验证 + BKT 交叉验证四步流程，实现为 LLM 主路径 + 启发式 fallback。正则模式匹配表未完全落地 |
| 认知负荷实时估计 | ✅ | `cognitive_load.py`：加权公式（内在难度 0.35 + 表现 0.35 + 连续受挫 0.2 + 工作记忆压 0.1）+ EMA 平滑。信号采集比设计简化（缺 answer_length_variance、question_rephrasing_rate 等文本分析信号） |
| 自适应阈值（personalize_threshold） | 🔴 | 设计 §3.2：拟合"正确率开始明显下降"的拐点做个性化 overload_threshold。未实现，使用固定阈值 |
| 学习者画像（21 维） | 🟡 | 部分实现：cold_start 产出 abstract_tolerance/transfer_ability/self_assessment_accuracy/preferred_pace。设计中的 full 21 维画像（working_memory_span/analogical_reasoning/mathematical_maturity/preferred_modality 等）大部分字段仅有 schema 定义，未被行为数据填充 |
| 画像演化引擎（ProfileEvolver） | 🔴 | `profiler.py` 标记 🔴。设计 §4.2 的从数据推断画像的规则引擎完全未实现 |
| 知识状态快照（KnowledgeSnapshot） | ✅ | BKT 参数表 + learner_profiles 表覆盖了设计 §5 的核心字段 |

**L5 差距评估**：BKT 知识追踪 + 错误诊断 + 认知负荷三件套完整可用。最大缺口是 DKT（需要训练数据，设计已有明确 Phase 3 规划）和画像演化引擎（目前画像字段靠冷启动一次性播种，不会随使用动态演化）。21 维画像中仅 4 维可演化。

---

## 六、L6 自适应教学引擎

| 设计项 | 状态 | 说明 |
|--------|------|------|
| 降阶法策略（完整状态机） | ✅ | `strategies/reduction.py`：PLAN→INTRO→EXPLAIN→CHECK→PRACTICE→NEXT→SESSION_END，7 状态 + 8 转换，匹配设计 §1.1 |
| 费曼法策略 | ✅ | `strategies/feynman.py`：精简状态机（PROMPT→WAIT→EVALUATE→PASS/GUIDED_CORRECTION/SIMPLIFY/MODEL）实现。设计中的 fidelity 五维评估简化为 LLM 单次评估 |
| 苏格拉底法策略 | ✅ | `strategies/socratic.py`：精简状态机。五层问题设计（具体体验→反思→抽象→实验→迁移）由 LLM 根据 depth 参数生成 |
| 项目驱动法策略 | ✅ | `strategies/pbl.py`：精简状态机 |
| 类比桥接策略 | ✅ | `strategies/analogy.py`：含 IDENTIFY_LIMITS 状态（标注类比失效临界点） |
| 间隔复习策略 | ✅ | `strategies/spaced_repetition.py`：4 种 review_mode |
| 降阶法 Jiangjie（新增，非设计） | ✅ | `strategies/jiangjie.py`：GOAL→REDUCE→COMPLEMENT→RECONSTRUCT→REVIEW→NEXT + FLAG_DIFFICULT。消费 PaceConfig，产出知识骨架 |
| 策略选择引擎（8 规则决策树） | ✅ | `strategy_selector.py`：完全匹配设计 §2.1 的 7 条规则 + 降阶法规则（Rule 8）。引擎动态调用 |
| 实时教学决策循环 | ✅ | `engine.py`：11 步循环（获取 L5 状态→获取 L3 复习建议→选择策略→生成动作→等待学生反应→分析→更新 L5→更新 L3→决定下一步→策略完成检测→切换策略） |
| 中断处理（7 种意图分类） | ✅ | `intent_classifier.py` + `engine.handle_interrupt()`：concept_question / process_question / prereq_gap / example_request / pace_complaint / distraction / cognitive_overload。分类用 LLM + 关键词降级 |
| PaceController（独立节奏控制器） | 🟡 | 设计 §3.3 的独立 PaceController 类未实现。节奏调整分散在 flow_regulator（心流→PaceConfig）和 strategy_selector（策略参数）中 |
| 13 种教学动作类型 | 🟡 | 实现 9 种：explain / ask_question / show_example / give_exercise / request_explanation / provide_hint / reveal_answer / review / reflection。缺失 ShowCounterExample、BreakSuggestion、PaceFeedback 三种独立动作类型 |
| L5↔L6 闭环 | ✅ | engine.respond 后更新 BKT、认知负荷、复习记录。策略选择消费 mastery/cognitive_load/profile/mastered_ratio/flow |

**L6 差距评估**：核心教学循环完整，7 种策略全部可用，策略自动选择 + 心流追踪 + 增益回路全部集成。PaceController 未独立成类，教学动作类型比设计少 3 种。整体覆盖度极高。

---

## 七、L7 交互层

| 设计项 | 状态 | 说明 |
|--------|------|------|
| 4 个 MCP Server 分组 | ✅ | knowledge-mcp / tutoring-mcp / digest-mcp / sync-mcp，完全匹配设计 §1 |
| knowledge-mcp Tool 签名 | ✅ | 9 tool，签名匹配（比设计多出 review_kg/update_kg/diff_kg/rollback_kg，是实施过程中合理拆分） |
| tutoring-mcp Tool 签名 | ✅ | 13 tool（设计 §2.2 列 6 个，实施中拆分为冷启动/进度/续学/打断/检查点/洞察/复习等多项 tool） |
| digest-mcp Tool 签名 | ✅ | 4 tool：digest + build_quiz_html + compile_slides + health |
| sync-mcp Tool 签名 | ✅ | 6 tool：push_to_obsidian + pull_homework + init_subject_repo + push_artifacts + watch_obsidian + health |
| 打断协议 | ✅ | 完整实现：save checkpoint → classify intent → handle → resume |
| 进度可视化 | ✅ | `servers/dashboard/` 只读 Web 面板：4 个区域（指标卡/策略步骤条/掌握度分布+最近交互/48h Phase 进度），3s 轮询 |
| L6→L7 多模态渲染 | 🟡 | 设计 §5：纯文本/富文本/视觉/语音四种渲染模式。当前聚焦文本输出，多模态渲染依赖 MCP host（Claude Desktop）自行处理。digest 产物（HTML/mp3/pptx）覆盖了视觉和语音的离线生成 |

**L7 差距评估**：交互层核心功能完整。多模态实时渲染的设计理想（KaTeX 公式、自动图表生成、TTS 朗读实时对话）未实现，但 digest 的离线多模态生成部分弥补。

---

## 八、PGFGA 集成（设计规格 `specs/pgfga-integration.md`）

| 设计项 | 状态 | 说明 |
|--------|------|------|
| 心流等级（5 级） | ✅ | 实现为 SILENT/STRAIN/FLOW/OVERLOAD（4 级）。设计为 SILENT/SHALLOW/FLUENT/DEEP/IMMERSED（5 级）。命名不同，核心概念一致 |
| 心流信号（增长×6 + 衰减×4） | ✅ | `flow_signals.py`：10 种信号采集 |
| 心流状态转移规则 | ✅ | 实现为信号净分驱动的状态机（比字面转移规则更鲁棒） |
| 非评判防火墙（6 类禁止模式） | ✅ | `non_judgment_firewall.py`：正则版实现，覆盖否定性判断/评判性语言/说教式口吻/话题终结/外部空洞夸奖/话题扭转。LLM 二审标记 🟡 |
| PGFGA 化 respond 模板 | 🟡 | 防火墙 + 三级反馈管道覆盖了设计中的"先承接→再引导"理念。但按 flow_level 分级的精确模板未完全照做 |
| SDT 自主性支持 | 🟡 | 学生有跳过权（已掌握概念自动跳过）。设计中的显式"提出选项让学生选"（节奏/路径/检测方式三选一）未实现 |
| SDT 胜任感支持 | 🟡 | feedback_generator 的 L3 LLM 润色实现"精准看见"。设计中的"进步对比"和"困难再框架"未专门实现 |
| SDT 归属感支持 | 🔴 | 记住学生之前的表达、情绪先于道理、使用学生语言、不切换频道——这些深度个性化支持未实现 |
| 增益回路监测 | ✅ | `gain_loop_monitor.py`：4 种断裂检测 + 修复建议 |
| 回路断裂修复 | ✅ | 4 种修复：兴趣断裂→重新建联 / 自信断裂→重建安全感 / 节奏断裂→降速加深 / 情绪断裂→主动关怀 |

**PGFGA 差距评估**：心流追踪 + 防火墙 + 增益回路三大核心机制全部实现。SDT 三大需求（自主性/胜任感/归属感）的行为层支持不足——当前是"不伤害"（防火墙），但未到"主动滋养"的级别。

---

## 九、采纳修正（设计 `specs/adopted-fixes.md`）

| 修正项 | 状态 | 说明 |
|--------|------|------|
| 修正 1：KG 人工确认节点 | ✅ | `review_kg` (quick/full) + `update_kg` (6 种编辑 op)。成为 acquire→build→review→update→start_learning 标准流程 |
| 修正 2：冷启动摸底测验 | ✅ | `cold_start_probe` (10 题跨三带) + `submit_cold_start` (判分→BKT 先验→画像初值) |
| 修正 3：时间估计校准 | ✅ | `time_estimator.py`：加权公式替代 XGBoost，含 calibrate_time 观测加权钩子 |
| 修正 4：48h 验证实验 | 🔴 | 设计完整（简化教材 50-80 页/15-30 概念/3-5 人/前后测+主观评分），未正式执行 |

---

## 十、综合评估

### 10.1 完成度矩阵

| 层 | 核心功能 | 完整度 | 关键缺失 |
|-----|---------|--------|---------|
| L1 基础设施 | 存储/错误/日志/插件 | 75% | StateStore / VectorStore 抽象；多 provider 插件级联；认证 |
| L2 短期记忆 | 会话上下文/聚焦/中断恢复 | 80% | Redis 中间层；TTL 自动过期 |
| L3 长期记忆 | 遗忘曲线/复习调度 | 65% | 学生知识网络；跨科目关联；λ 加权混合 |
| L4 知识工程 | KG 构建/版本管理/查询 | 70% | 12→3 语义关系；多源融合；增量更新；分阶段抽取管道 |
| L5 学习者建模 | BKT/错误诊断/认知负荷 | 55% | DKT；画像演化引擎；自适应阈值；21→4 画像维度 |
| L6 教学引擎 | 7 策略/自动选择/决策循环 | 85% | PaceController 独立类；ShowCounterExample/BreakSuggestion/PaceFeedback |
| L7 交互层 | 4 MCP server/32 tool/面板 | 80% | 多模态实时渲染（KaTeX/TTS 对话） |
| PGFGA | 心流/防火墙/增益回路 | 70% | SDT 深度支持（自主选择/胜任感/归属感行为层） |

### 10.2 设计外新增能力

以下能力在设计文档中没有明确要求，但实施中自行添加：

- **降阶法 Jiangjie 策略**：独立方法论状态机（GOAL→REDUCE→COMPLEMENT→RECONSTRUCT→REVIEW），消费 PaceConfig
- **advance tool**：推进纯讲解态（设计只规划了 respond）
- **get_learning_progress / resume_learning**：不开会话看进度、跨天续学
- **learning_plan Phase 化调度**：跨 Session 的教学计划持久化
- **教学内容 LLM 生成**（content_generator）：LLM 改写模板填空为真实讲解
- **教学反馈分级**（feedback_generator）：L1 模板→L2 补救→L3 LLM 润色三级管道
- **难度信号内容化**（Slice DS）：LLM 从内容估计 abstract_level/formula_density/cognitive_load_estimate
- **批量 KG 管道**（batch_enrich）：有界并行 + JSONL 断点续跑
- **状态面板**（dashboard）：与 4 server 共享 SQLite 的只读 Web 仪表盘

### 10.3 架构忠实度评价

实现与设计在**宏观架构层面高度一致**：七层认知架构全部落地，4 个 MCP server 分组完全匹配，工具签名 95% 对应，教学策略 7/6 覆盖（含新增），核心数据流（采集→建图→教学→复习→产物）匹配设计。

在**微观细节层面存在合理的工程简化**：
- 12 种语义关系 → 3 种（剩下 9 种对 V1 教学引擎不阻塞）
- DKT → 仅 BKT（设计已规划 Phase 3，且需要训练数据）
- 多源融合 → 单源（对个人学习场景第一版可接受）
- 画像 21 维 → 4 维可演化（其余留 schema 桩）
- 知识抽取 6 阶段管道 → 一阶段 LLM（效果略粗但工程可行性更高）

**最值得关注的三个缺失**（按影响排序）：
1. **学生知识网络**（L3）：无法建模学生脑内"概念之间的关联"，错失了最有价值的个性化复习能力
2. **DKT 深度知识追踪**（L5）：纯 BKT 无法捕捉跨概念的技能迁移，当前冷启动画像只用一次
3. **画像演化引擎**（L5）：画像字段永久停留在冷启动初值，无法"越用越懂你"

---

## 十一、建议实施优先级（若要补齐）

| 优先级 | 项目 | 预估 | 理由 |
|--------|------|------|------|
| P0 | 学生知识网络（L3） | 1 周 | 直接影响复习质量，把"孤立概念复习"变为"关联概念联合复习" |
| P1 | 画像演化引擎（L5） | 1 周 | 让画像从一次性冷启动变为持续演化，是"越用越懂你"的关键 |
| P1 | DKT 集成（L5） | 1.5 周 | 需要历史交互数据积累；初期可继续用 BKT 兜底 |
| P2 | 12 种语义关系补全（L4） | 0.5 周 | 增强 KG 表达力，让教学引擎的路径规划和复习调度更精准 |
| P2 | SDT 深度支持（PGFGA） | 0.5 周 | 把"不伤害"升级到"主动滋养"：自主选择、进步对比、情绪先于道理 |
| P3 | 多源融合引擎（L4） | 1 周 | 支持多教材/多视频源交叉验证，提高 KG 质量 |
| P3 | Redis 状态中间层（L2） | 0.5 周 | 生产部署需要，单机单用户可延后 |
| P4 | 48h 验证实验（修正 4） | 1 周 | 收集真实学习数据，校准时间/难度估计，验证全链路 |
