# ai-tutor 实施路线图

> 设计源：`../使用AI进行学习的技巧/ai-tutor-system-design/`  
> 状态符号：✅ 完成 | 🟡 stub（接口已立，行为待实现）| 🔴 未开始 | ⏸ 已删

## 1. 切片划分

| 切片 | 目标 | 关键产出 | 状态 |
|---|---|---|---|
| **Spine v0** | 项目骨架 + L1 基础设施 | shared/* 全部 + 烟囱测试 | ✅ |
| **Spine v1** | knowledge-mcp 端到端（toc 模式） | acquire(file) → build_kg(toc) → query → 持久化 | ✅ |
| **Spine v1.5** | 接口骨架 + 契约测试 | Protocol + stub + ROADMAP | ✅ |
| **Spine v2** | tutoring-mcp 端到端（BKT + reduction） | start_session → next_action → respond + e2e | ✅ |
| **Slice K1** | knowledge-mcp depth=concept | ConceptEnricher + ConceptKGBuilder + review_kg；用 MockLLM 跑通；真实 DeepSeekProvider 在 K2 | ✅ |
| **Slice K2** | 真实 LLM provider + update_kg 闭环 | DeepSeekProvider + LRU L1 缓存 + update_kg 6 op + .env 自动加载 + 真实笔记跑通 | ✅ |
| **Slice K3** | 完整 KG 版本树 | base_id + parent_kg_id 双字段；update_kg(mode=versioned) + diff_kg + rollback_kg；BKT 跨版本继承 | ✅ |
| **Slice T1** | 完整教学循环 | Reduction 完整状态机 + 5 种策略 stub + LLMScorer + ErrorDiagnoser + StrategySelector + concept 自动切换 | ✅ |
| **Slice T2** | L3 长期记忆 | ForgettingCurve (scipy 拟合) + MemoryStore + ReviewScheduler 多因子 + learning_insight + generate_review_plan + engine 自动 record | ✅ |
| **Slice T3** | 心流追踪 + 增益回路 | flow_signals(10信号) + flow_tracker(FlowLevel状态机) + gain_loop_monitor(4种断裂+修复) + engine 集成；CR1/CR2 修过其 bug | ✅ |
| **Slice D** | digest-mcp 多模态产物 | mindmap (✅) + notes (✅) + quiz (✅) + slides/audio/simulation/multi_agent (🟡 stub) | ✅ |
| **Slice D2** | digest 补全 4 format | simulation(自包含HTML闪卡) + multi_agent(三角色对话JSON,LLM/模板) + slides(HTML→可选pptx) + audio(讲稿md→可选mp3)；零必需依赖优雅降级；顺手修 simulation 的 `</script>` XSS。7/7 format 全实现 | ✅ |
| **Slice S** | sync-mcp Obsidian 集成 | push_to_obsidian + pull_homework + 真实 vault 跑通；GitHub stub 留 S2 | ✅ |
| **Slice S2** | sync-mcp git + watch 集成 | git CLI subprocess（无 PyGithub）：init_subject_repo / push_artifacts / push_to_remote + mtime 轮询 watch_obsidian；零新依赖 | ✅ |
| **Slice CR1** | 代码审查批 — 修 7 个真 bug | code-review 找 15 候选 → 验证 → 修 4 high + 3 medium：attempt_count 死代码、avoidance key 不存在、versioned isolated 误报、watch 时区错位、gain_loop 优先级倒置、merge_concepts 不同步、intent 优先级；零回归 | ✅ |
| **Slice Q** | query_knowledge 补全 path/subgraph | kg_query.py：networkx 最短学习路径（沿 prerequisite_strong）+ N 跳邻域子图；server 加 target/depth 参数。knowledge-mcp 9 tool 内分支全实现 | ✅ |
| **Slice CR2** | 第二轮代码审查 — 修 2 bug | 审 D2+Q 新代码（更干净，仅 2 finding）：audio 的 asyncio.run 在 MCP async loop 内必 RuntimeError → mp3 静默失效（修：_run_async 检测 running loop 走 worker thread）；multi_agent resp.content=None 未防御（修：(content or "") 兜底模板）。零回归 | ✅ |
| **Slice F** | build(depth=full) 补全最后重型 stub | kg_full.py：确定性加权难度校准（cognitive_load 0.3+formula 0.2+abstract 0.2+depth 0.15+time 0.15，无需训练数据/可解释）+ numpy feature-hashing embedding（64维 L2 归一，中文 2-gram，余弦近邻）；抽 _enrich_concepts 让 concept/full 共用 pipeline；可选 chromadb。schema 加 calibrated_difficulty。真实笔记跑通 20 概念 | ✅ |
| **Slice J** | 降阶法策略 (JiangjieStrategy) | `strategies/jiangjie.py`：独立的降阶学习法状态机 GOAL→REDUCE→COMPLEMENT→RECONSTRUCT→REVIEW→NEXT（+FLAG_DIFFICULT）；消费 FlowRegulator 的 PaceConfig（难度/脚手架/原子数/错误数）；产出知识骨架（前提→逻辑→结论→易错点）。strategy_selector 加规则 8（preferred_pace=="thorough" / 心流 SILENT / 中高负荷 → jiangjie，置于 overload 规则之后）+ 可选 flow_level 入参。真实概念跑通完整生命周期。**engine 动态选策略 + 调 flow_regulator 仍属 P1 #4，未做** | ✅ |
| **Slice CS** | 冷启动摸底 (P0 #2) | `cold_start.py`：选 10 道跨难度题（band 3/4/3）+ 判分（复用 LLMScorer）+ correctness×自评→BKT 先验 + 画像初值（abstract_tolerance/transfer/self_assessment）+ recommended_level。`BKTStore.seed_prior`（不覆盖真实观测）。engine `next_action` 跳过 mastery≥0.8 的概念（仅在概念未开教时；进行中不打断）。新增 2 tool `cold_start_probe`/`submit_cold_start` + 写 LearnerProfile 初值；`start_learning_session` 教学路径标出 skipped/to_learn。真实笔记验证：17→13 概念，8.5h→6.5h | ✅ |
| **Slice P1#4** | 6 策略引擎集成 | engine 动态选策略（接入 strategy_selector，输入 mastery/cognitive_load/profile/mastered_ratio/flow）+ flow_regulator 调 pace 传入策略 params。Strategy 基类加 `TERMINAL_STATES`/`is_complete()`/`export_state`/`restore_state`；7 策略声明终止态。`SessionContext.strategy_internal` 持久化策略内部计数器，使 jiangjie/feynman/socratic/pbl 跨重建无损。next_action 用 `is_complete()` 通用判完成。修一个 falsy-zero bug（FlowLevel.SILENT==0 被 `or` 吞）。真实笔记验证：thorough 学习者自动走降阶法，_atom_index 跨 respond 递增 | ✅ |
| **Slice MS** | 多 Session 调度 (P0 #3) | `learning_plan.py`：`build_plan` 把拓扑序按顶层章节切 Phase（含时长估计）+ `compute_progress`（每 Phase 完成度/当前 Phase/下一个该学的概念）+ `LearningPlanStore`（新表 `learning_plans`，按 user+subject 持久化）。新增 2 tool `get_learning_progress`（不开会话看进度）/`resume_learning`（复用未结束会话或新建并定位到首个未掌握）。`start_learning_session` 改用 Phase 化计划，teaching_plan 反映各 Phase 完成度。真实笔记验证：跨天续学"已掌握 10/17，当前 Phase 2，今天从【导数】继续" | ✅ |
| **Slice CG** | 教学内容 LLM 生成 (P0 #1) | `content_generator.py`：引擎 next_action 拿到策略动作后，按 action.type 用 LLM 把模板填空改写成真实讲解（直觉+例子/练习/提示），失败/不可用回退模板。加 provider 能力位 `supports_generation`（Stub/Mock=False、DeepSeek=True），使 Mock/Stub 测试完全不受影响。server `_llm()` 在有 `DEEPSEEK_API_KEY` 时接入 DeepSeek（同时启用判分/诊断/生成）。真实笔记验证：Stub→模板、真实 LLM→生动讲解。**至此 3 个 P0 全部完成** | ✅ |
| **Slice FG** | 教学反馈分级 (P1 #7) | `feedback_generator.py`：反馈三级管道 L1（correctness 模板）+ L2（remediation）+ L3（LLM 润色）。engine.respond 把 L1+L2 模板作为 fallback 传入 L3，润色结果再过非评判防火墙。同样 gated on `supports_generation`，Stub/Mock 返回模板 → 既有 respond 测试不变。 | ✅ |
| **Slice CL** | 认知负荷在线估计 (P1 #6) | `cognitive_load.py`：确定性加权公式（内在难度 0.35 + 表现 0.35 + 连续受挫 0.2 + 工作记忆压力 0.1）+ EMA 平滑。engine 在 respond 后（数据最全）+ 进入新概念时更新 `ctx.meta.current_cognitive_load`，喂给 strategy_selector（>0.6→jiangjie / >0.75→analogy/reduction）和 flow_regulator（>0.7 降难度+加脚手架）。此前恒 0.0 → 这两条分支永不触发，现已激活。 | ✅ |
| **Slice TC** | 时间校准 (P1 #8) | `time_estimator.py`：`estimate_time_min` 用非时间特征（认知负荷/公式密度/抽象度/前置数/深度）的加权公式给学习时长，映射到 5-45min，替代恒定 30。FullKGBuilder 先估时长再算难度（难度的 time_norm 用上校准值，告别循环）。`calibrate_time` 提供"公式估计 × 真实观测"置信度加权钩子（待时间追踪落地）。 | ✅ |
| **Slice DS** | 难度信号内容化 (P2 #11) | `concept_enricher.py`：enricher 用 LLM 从内容估计 abstract_level / formula_density / cognitive_load_estimate（clamp，向后兼容；去掉 prompt 对 abstract_level 的锚定）。修掉"难度/时长/band 只随标题层级变化"（48h 验证发现）。实测 full 深度：abstract 0.1-0.7、时长 10-28min、cold-start 三带齐全。 | ✅ |
| **Slice BK** | 批量 KG 管道 (P1 #5) | `batch_enrich.py`：有界并行 enrich（ThreadPoolExecutor，max_workers 限流）+ `EnrichCheckpoint`（JSONL 增量落盘，崩溃后续跑跳过已完成）。`_enrich_concepts` 改用它（默认 4 worker），Concept/FullKGBuilder 加 `max_workers`/`checkpoint_path` 字段透传。MockLLMProvider 加锁保证并发安全。容错/PLUGIN 上抛/顺序组装与原串行版一致。支撑数百概念规模。 | ✅ |

---

## 2. MCP Server 状态

### `servers/knowledge_mcp/` — L4 知识工程

| 文件 | 内容 | 状态 |
|---|---|---|
| `server.py` | FastMCP 入口 | ✅ |
| `acquisition_adapter.py` | file 源（pdf+md）；web/video 抛 DEPENDENCY_MISSING | 🟡（file ✅，web/video 🔴） |
| `kg_enrich_adapter.py` | toc 模式纯规则抽章节 | ✅ |
| `kg_builder.py` | KGBuilder Protocol + Toc/Concept/Full（_enrich_concepts 共用 pipeline） | ✅（三种 depth 全实现） |
| `kg_full.py` | 确定性难度校准加权公式 + numpy feature-hashing embedding + 余弦 | ✅ |
| `time_estimator.py` | 学习时长校准（非时间特征加权 → 5-45min，替代恒30）+ calibrate_time 观测加权钩子 | ✅ |
| `batch_enrich.py` | 批量并行 enrich（有界 ThreadPool）+ EnrichCheckpoint（JSONL 续跑）；_enrich_concepts 默认 4 worker | ✅ |

### Tools（按 `specs/server-api-spec.md`）

| Tool | 状态 | 备注 |
|---|---|---|
| `acquire_subject` | ✅ file 源 / 🔴 web+video | 多源签名已就位 |
| `build_knowledge_graph(depth=toc)` | ✅ | |
| `build_knowledge_graph(depth=concept)` | ✅ | 真实 DeepSeek (或 fallback Stub)，带 L1 LRU 缓存 |
| `build_knowledge_graph(depth=full)` | ✅ | concept + 确定性加权难度校准 + numpy feature-hashing embedding（64维，余弦近邻）；装 chromadb 则额外建向量库。零必需依赖优雅降级 |
| `query_knowledge(concept)` | ✅ | |
| `query_knowledge(neighbors)` | ✅ | 含 part_of 父 + 前置上下游 |
| `query_knowledge(path)` | ✅ | networkx 最短学习路径（沿 prerequisite_strong，A→B=A 是 B 前置）；无路径 found=False |
| `query_knowledge(subgraph)` | ✅ | 中心 concept N 跳无向 BFS 邻域子图（concepts+edges） |
| `review_kg` | ✅ | quick/full 模式 + 缩略 Mermaid + suggested_actions |
| `update_kg` | ✅ | 6 种 op + audit trail；K3 加 mode='versioned' 创建新 KG 版本 |
| `diff_kg` | ✅ | 按 base_id 对齐两 KG：added/removed/definition_changed 等 |
| `rollback_kg` | ✅ | subject.kg_id 回到 parent 链祖先；不删 child（审计） |
| `resolve_conflicts` | ✅ | 5 种结构冲突（环/反向前置/重复/悬空边/孤岛）；语义对立留 LLM 切片 |
| `health` | ✅ | |

### `servers/tutoring_mcp/` — L2/L3/L5/L6

| 文件 | 内容 | 状态 |
|---|---|---|
| `server.py` | FastMCP 入口（12 tool：start/resume/next/respond + cold_start_probe/submit_cold_start + get_learning_progress + 5 已实现） | ✅ |
| `cold_start.py` | 冷启动摸底核心逻辑（选题/出题/判分聚合/先验映射/画像初值） | ✅ |
| `learning_plan.py` | 多 Session 调度：build_plan（章节切 Phase）+ compute_progress + LearningPlanStore | ✅ |
| `content_generator.py` | 教学内容 LLM 生成（按 action.type 改写讲解/例子/练习；模板兜底；gated on supports_generation） | ✅ |
| `feedback_generator.py` | 教学反馈 L3 LLM 润色（L1模板+L2 remediation 作 fallback；gated on supports_generation） | ✅ |
| `cognitive_load.py` | 认知负荷在线估计（加权公式 + EMA）；引擎更新 ctx.meta.current_cognitive_load 喂给 selector/regulator | ✅ |
| `session.py` | L2 SessionContext CRUD | ✅ |
| `bkt.py` | BKT 贝叶斯更新 | ✅ |
| `bkt_store.py` | BKT 状态持久化（bkt_params 表）+ seed_prior（冷启动先验，不覆盖真实观测） | ✅ |
| `tracer.py` | L5 知识追踪（BKT+DKT 双模型） | 🔴 |
| `dkt_model.py` | PyTorch DKT | 🔴（Phase 3+） |
| `error_diagnosis.py` | L5 错误诊断 | 🔴 |
| `profiler.py` | L5 ProfileEvolver | 🔴 |
| `cognitive_load.py` | L5 认知负荷 | 🔴 |
| `engine.py` | L6 教学决策主循环（动态选策略 + flow_regulator 调 pace + LLMScorer + ErrorDiagnoser + concept 切换/跳过已掌握 + handle_interrupt + handle_checkpoint + 心流追踪 + 增益回路）| ✅ |
| `intent_classifier.py` | 5 类打断意图分类 + 关键词降级 | ✅ |
| `llm_scorer.py` | LLM 语义判分 + 启发式 fallback | ✅ |
| `error_diagnoser.py` | 10 种 ErrorType 诊断 + remediation | ✅ |
| `strategy_selector.py` | 8 条规则决策树（含降阶法规则 + 可选 flow_level 入参）；**已被 engine 调用**（Slice P1#4） | ✅ |
| `flow_regulator.py` | 心流调节器 FlowLevel→PaceConfig（主动调参）；**已被 engine 调用**（Slice P1#4） | ✅ |
| `strategy_selector.py` | L6 策略选择决策树 | 🔴 |
| `strategies/base.py` | Strategy ABC | ✅ |
| `strategies/reduction.py` | 通用降阶教学流程（讲→问→练）— 完整状态机 + FLAG_DIFFICULT | ✅ |
| `strategies/jiangjie.py` | 降阶学习法 — 独立方法论（目标→原子→补集→骨架重构）；消费 PaceConfig；产出知识骨架 | ✅ |
| `strategies/feynman.py` | 费曼法 — 精简状态机 | 🟡 |
| `strategies/socratic.py` | 苏格拉底法 — 精简状态机 | 🟡 |
| `strategies/pbl.py` | 项目驱动 — 精简状态机 | 🟡 |
| `strategies/analogy.py` | 类比桥接 — 强调 IDENTIFY_LIMITS | 🟡 |
| `strategies/spaced_repetition.py` | 间隔复习 — 4 种 review_mode | 🟡 |
| `strategies/__init__.py` | get_strategy 工厂 | ✅ |
| `memory_store.py` | L3 长期记忆持久化（record_review + load_curve + due_reviews） | ✅ |
| `forgetting_curve.py` | L3 个性化遗忘曲线（scipy.curve_fit + clamp） | ✅ |
| `review_scheduler.py` | L3 多因子优先级调度 + ReviewMode 选择 | ✅ |
| `insight.py` | learning_insight 真实实现 | ✅ |
| `knowledge_network.py` | L3 学生知识网络 | 🔴 (T3) |
| `non_judgment_firewall.py` | PGFGA 防火墙 | 🟡（正则版，待 LLM 二审） |
| `flow_tracker.py` | PGFGA 心流追踪 | 🔴 |
| `gain_loop_monitor.py` | PGFGA 增益回路 | 🔴 |

### `servers/digest_mcp/` — L7 多模态产物

| 文件 | 内容 | 状态 |
|---|---|---|
| `server.py` | FastMCP 入口（digest + build_quiz_html + compile_slides + health） | ✅ |
| `orchestrator.py` | 按 formats 分派；DigestRunResult 带 warnings | ✅ |
| `build_quiz_html` / `compile_slides` (server.py) | spec §三 #2/#3 独立 tool；复用 quiz/slides generator（薄封装） | ✅ |
| `mindmap.py` | KG → .mmd（max_depth / only_low_confidence 过滤） | ✅ |
| `notes.py` | KG → 结构化 markdown（章节深度自适应 + grade 年级适配：high_school 直觉优先 / college 形式化优先） | ✅ |
| `quiz.py` | KG → 填空+多选混合题 → quiz.html + quiz.json | ✅ |
| `assets/quiz-template.html` | 可交互测验模板（提交即看分） | ✅ |
| `_kg_read.py` | D2 共享：读 KG + 章节自然排序 + KG_NOT_FOUND | ✅ |
| `simulation.py` | 自包含 HTML 交互闪卡（无 CDN，`</script>` 已转义防 XSS） | ✅ |
| `multi_agent.py` | 三角色对话 JSON（teacher/student/skeptic）；llm 给定→LLM，否则模板 | ✅ |
| `slides.py` | 自包含 HTML 分页幻灯；装 python-pptx 则升级 .pptx | ✅ |
| `audio.py` | 朗读讲稿 .md（带 `[停顿]`）；装 edge-tts 则合成 .mp3 | ✅ |

### `servers/sync_mcp/` — Obsidian + GitHub

| 文件 | 内容 | 状态 |
|---|---|---|
| `server.py` | FastMCP 入口（6 工具全实现） | ✅ |
| `obsidian.py` | push_to_obsidian + pull_homework + 3 种匹配 + 元目录忽略 | ✅ |
| `git_sync.py` | git CLI subprocess：init_repo / commit_artifacts / push_to_remote；bytes-mode + utf-8 防 Windows GBK 崩 | ✅ |
| `obsidian_watch.py` | mtime 轮询 poll_changes + 长运行 watch 包装；零额外依赖 | ✅ |

---

## 3. shared/ 基础设施状态

| 模块 | 状态 | 备注 |
|---|---|---|
| `schemas.py` | ✅ | 60+ Pydantic 模型，含 PGFGA |
| `models.py` | ✅ | 全部 SQLAlchemy ORM |
| `errors.py` | ✅ | TutorError + 15 错误码 |
| `storage.py` | 🟡 | FileStore + RelationalStore ✅；VectorStore / Redis / StateStore 🔴 |
| `plugins.py` | ✅ | PluginRegistry + Plugin Protocol |
| `llm_client.py` | ✅ | Protocol + Stub/Mock ✅ |
| `providers/deepseek.py` | ✅ | OpenAI 兼容；from_env()；mock 单测 |
| `llm_cache.py` | 🟡 | L1 LRU ✅；L2 SQLite / L3 语义近邻 🔴 |
| `config.py` | ✅ | .env 自动加载（cwd / 父目录）；大小写不敏感 |
| `slug.py` | ✅ | 中文 → 拼音 |
| `logging_config.py` | ✅ | structlog |
| `llm_cache.py` | 🔴 | 三级缓存（内存/SQLite/语义） |

---

## 4. 数据库 / 迁移状态

| 表 | 状态 | 用途 |
|---|---|---|
| `users / subjects / corpora / knowledge_graphs / concepts / relations` | ✅ | 已落库且有数据 |
| `bkt_params / knowledge_snapshots / learner_profiles` | ✅ ORM | 等 Spine v2 写入 |
| `sessions` | ✅ ORM | 等 Spine v2 写入 |
| `learning_plans` | ✅ | 多 Session 调度（Slice MS）：按 user+subject 持久化 Phase 化计划 |
| `review_history / forgetting_curves` | ✅ ORM | 等 Slice T2 写入 |
| Alembic 自动 migration | 🟡 | 配置完成；`alembic revision --autogenerate -m initial` 还未首次执行；当前用 `scripts/init_db.py` |

---

## 5. 测试覆盖现状

| 类别 | 测试数 | 文件 |
|---|---|---|
| schemas 烟囱 | 19 | `tests/unit/test_schemas_smoke.py` |
| storage 烟囱 | 3 | `tests/unit/test_storage_smoke.py` |
| plugins 契约 | 5 | `tests/unit/test_plugins.py` |
| llm_client 契约 | 6 | `tests/unit/test_llm_client.py` |
| knowledge-mcp KG | 3 | `servers/knowledge_mcp/tests/test_kg_toc.py` |
| knowledge-mcp 多源 | 5 | `servers/knowledge_mcp/tests/test_acquire_multi_source.py` |
| knowledge-mcp builder | 6 | `servers/knowledge_mcp/tests/test_kg_builder_protocol.py` |
| knowledge-mcp server | 4 | `servers/knowledge_mcp/tests/test_server_smoke.py` |
| knowledge-mcp KG stub | 4 | `servers/knowledge_mcp/tests/test_kg_review_stubs.py` |
| tutoring-mcp strategy base | 4 | `servers/tutoring_mcp/tests/test_strategy_base.py` |
| tutoring-mcp firewall | 6 | `servers/tutoring_mcp/tests/test_non_judgment_firewall.py` |
| tutoring-mcp BKT | 10 | `servers/tutoring_mcp/tests/test_bkt.py` |
| tutoring-mcp BKTStore | 5 | `servers/tutoring_mcp/tests/test_bkt_store.py` |
| tutoring-mcp Session | 7 | `servers/tutoring_mcp/tests/test_session.py` |
| tutoring-mcp Engine | 5 | `servers/tutoring_mcp/tests/test_engine.py` |
| tutoring-mcp Server | 4 | `servers/tutoring_mcp/tests/test_server_smoke.py` |
| tutoring-mcp 拓扑序回归 | 5 | `servers/tutoring_mcp/tests/test_topological_order.py` |
| knowledge-mcp ConceptEnricher | 9 | `servers/knowledge_mcp/tests/test_concept_enricher.py` |
| knowledge-mcp ConceptKGBuilder | 6 | `servers/knowledge_mcp/tests/test_concept_builder.py` |
| knowledge-mcp review_kg | 6 | `servers/knowledge_mcp/tests/test_review_kg.py` |
| knowledge-mcp update_kg | 10 | `servers/knowledge_mcp/tests/test_update_kg.py` |
| DeepSeekProvider | 7 | `tests/unit/test_deepseek_provider.py` |
| config / .env 加载 | 7 | `tests/unit/test_config.py` |
| llm_cache LRU | 7 | `tests/unit/test_llm_cache.py` |
| digest-mcp mindmap | 5 | `servers/digest_mcp/tests/test_mindmap.py` |
| digest-mcp notes | 6 | `servers/digest_mcp/tests/test_notes.py` |
| digest-mcp quiz | 7 | `servers/digest_mcp/tests/test_quiz.py` |
| digest-mcp orchestrator | 7 | `servers/digest_mcp/tests/test_digest_orchestrator.py` |
| tutoring-mcp ReductionStrategy | 10 | `servers/tutoring_mcp/tests/test_reduction_strategy.py` |
| tutoring-mcp LLMScorer | 7 | `servers/tutoring_mcp/tests/test_llm_scorer.py` |
| tutoring-mcp ErrorDiagnoser | 7 | `servers/tutoring_mcp/tests/test_error_diagnoser.py` |
| tutoring-mcp 5 种策略 stub | 17 | `servers/tutoring_mcp/tests/test_other_strategies.py` |
| tutoring-mcp StrategySelector | 12 | `servers/tutoring_mcp/tests/test_strategy_selector.py`（含降阶法 4 规则） |
| tutoring-mcp JiangjieStrategy | 16 | `servers/tutoring_mcp/tests/test_jiangjie_strategy.py` |
| tutoring-mcp Engine T1 集成 | 5 | `servers/tutoring_mcp/tests/test_engine_t1.py` |
| sync-mcp Obsidian push | 7 | `servers/sync_mcp/tests/test_obsidian_push.py` |
| sync-mcp Obsidian pull | 9 | `servers/sync_mcp/tests/test_obsidian_pull.py` |
| sync-mcp Server | 6 | `servers/sync_mcp/tests/test_server_smoke.py` |
| tutoring-mcp ForgettingCurve | 11 | `servers/tutoring_mcp/tests/test_forgetting_curve.py` |
| tutoring-mcp MemoryStore | 8 | `servers/tutoring_mcp/tests/test_memory_store.py` |
| tutoring-mcp ReviewScheduler | 6 | `servers/tutoring_mcp/tests/test_review_scheduler.py` |
| tutoring-mcp Insight+ReviewPlan | 7 | `servers/tutoring_mcp/tests/test_insight_and_review_plan.py` |
| tutoring-mcp IntentClassifier | 11 | `servers/tutoring_mcp/tests/test_intent_classifier.py` |
| tutoring-mcp InterruptHandler | 8 | `servers/tutoring_mcp/tests/test_interrupt_handler.py` |
| tutoring-mcp CheckpointHandler | 8 | `servers/tutoring_mcp/tests/test_checkpoint_handler.py` |
| K3 Schema (base_id + parent_kg_id) | 5 | `tests/unit/test_k3_schema.py` |
| K3 update_kg(versioned) | 9 | `servers/knowledge_mcp/tests/test_update_kg_versioned.py` |
| K3 diff_kg + rollback_kg | 10 | `servers/knowledge_mcp/tests/test_diff_and_rollback.py` |
| T3 FlowSignals | 11 | `servers/tutoring_mcp/tests/test_flow_signals.py` |
| T3 FlowTracker | 10 | `servers/tutoring_mcp/tests/test_flow_tracker.py` |
| T3 GainLoopMonitor | 11 | `servers/tutoring_mcp/tests/test_gain_loop_monitor.py` |
| T3 Engine 集成 | 5 | `servers/tutoring_mcp/tests/test_engine_t3.py` |
| RC resolve_conflicts | 10 | `servers/knowledge_mcp/tests/test_resolve_conflicts.py` |
| S2 git_sync | 10 | `servers/sync_mcp/tests/test_git_sync.py` |
| S2 obsidian_watch | 7 | `servers/sync_mcp/tests/test_obsidian_watch.py` |
| CR1 bug 回归（7 真 bug） | 7 | `servers/tutoring_mcp/tests/test_bug_regression.py` |
| D2 simulation | 6 | `servers/digest_mcp/tests/test_simulation.py` |
| D2 multi_agent/slides/audio | 11 | `servers/digest_mcp/tests/test_d2_generators.py` |
| Q kg_query (path+subgraph) | 12 | `servers/knowledge_mcp/tests/test_kg_query.py` |
| CR2 bug 回归（2 bug） | 3 | `servers/digest_mcp/tests/test_cr2_regression.py` |
| F kg_full（难度+embedding） | 9 | `servers/knowledge_mcp/tests/test_kg_full.py` |
| F FullKGBuilder 集成 | 6 | `servers/knowledge_mcp/tests/test_full_builder.py` |
| integration e2e (v0+v1+v2) | 2 | `tests/integration/test_e2e_spine.py` |
| integration digest→sync | 2 | `tests/integration/test_digest_to_sync_e2e.py` |
| BDD 设计规格套件（接入真实实现） | 58（57 pass + 1 skip） | `BDD/test_bdd_ai_tutor.py` |
| tutoring-mcp ColdStart core | 10 | `servers/tutoring_mcp/tests/test_cold_start.py` |
| tutoring-mcp ColdStart tools | 6 | `servers/tutoring_mcp/tests/test_cold_start_server.py` |
| tutoring-mcp BKTStore seed_prior | +3 | `servers/tutoring_mcp/tests/test_bkt_store.py` |
| tutoring-mcp Engine skip-mastered | +4 | `servers/tutoring_mcp/tests/test_engine_t1.py` |
| tutoring-mcp 策略序列化+完成检测 | 17 | `servers/tutoring_mcp/tests/test_strategy_serialization.py` |
| tutoring-mcp Engine 策略选择+pace | 5 | `servers/tutoring_mcp/tests/test_engine_strategy_selection.py` |
| tutoring-mcp LearningPlan core | 9 | `servers/tutoring_mcp/tests/test_learning_plan.py` |
| tutoring-mcp 进度/续学 tool | 6 | `servers/tutoring_mcp/tests/test_learning_plan_server.py` |
| tutoring-mcp ContentGenerator | 16 | `servers/tutoring_mcp/tests/test_content_generator.py` |
| tutoring-mcp Engine 内容生成集成 | 2 | `servers/tutoring_mcp/tests/test_engine_t1.py` |
| tutoring-mcp FeedbackGenerator | 9 | `servers/tutoring_mcp/tests/test_feedback_generator.py` |
| tutoring-mcp Engine 反馈润色集成 | 1 | `servers/tutoring_mcp/tests/test_engine_t1.py` |
| tutoring-mcp CognitiveLoad | 9 | `servers/tutoring_mcp/tests/test_cognitive_load.py` |
| tutoring-mcp Engine 负荷集成 | 1 | `servers/tutoring_mcp/tests/test_engine_strategy_selection.py` |
| knowledge-mcp TimeEstimator | 11 | `servers/knowledge_mcp/tests/test_time_estimator.py` |
| knowledge-mcp Full build 时长校准 | 1 | `servers/knowledge_mcp/tests/test_full_builder.py` |
| knowledge-mcp BatchEnrich（并行+checkpoint） | 6 | `servers/knowledge_mcp/tests/test_batch_enrich.py` |
| knowledge-mcp 难度信号内容化 | 3 | `servers/knowledge_mcp/tests/test_concept_enricher.py` |
| code-review 收尾回归（CG/FG/CL/TC/BK） | 3 | content_generator / batch_enrich |
| **合计** | **662（661 passed + 1 skipped）** | |

跑 `uv run pytest` 应该全部 green（BDD 已加入 `testpaths`，与 canonical 一起跑）。

> 唯一 skip：PDF→MD 需外部 mineru CLI。digest-mcp 现 **4 tool**（新增独立
> `build_quiz_html` / `compile_slides`，复用现有 generator；`digest`/notes 已支持
> `grade` 年级适配），全套 **27 tool**。

---

## 5.1 真实笔记验证暴露的限制

2026-05-21 用 `xbpd_obsidian/.../4月24日-星期四-聚类.md`（3 章 / 8 节 / 20 概念）跑通端到端，发现：

| 现象 | 性质 | 下一步 |
|---|---|---|
| 父节点排在子节点后（已修） | bug：拓扑 tie-break 用字符串而非章节号 | ✅ 修复 + 5 个回归测试 |
| `next_action` 始终返回 INTRO | 限制：`ReductionStub` 只识别 `intro_done/explain_done`，engine 发的是 `answered` | Slice T1 写完整 6 种策略状态机时同步修 |
| 随便答都是 `partial` | 限制：`engine._score` 用 2-gram 重叠，没语义判分 | Slice T1 接 LLMProvider 做语义判分 |
| 平均 confidence=0.4（toc 模式默认低分） | 设计：toc 模式低置信，预期 review_kg 人工提分 | Slice K2 实现 review_kg/update_kg 后可手工提分 |

## 6. 已采纳但未实施的 spec 修正

来源：`specs/adopted-fixes.md`

| 修正 | 当前状态 | 实施位置 |
|---|---|---|
| KG 人工确认（review_kg/update_kg） | 🟡 stub | Slice K2 |
| 摸底测验（cold-start assessment） | ✅ Slice CS | `cold_start.py` + `cold_start_probe`/`submit_cold_start` tool + engine 跳过已掌握 |
| 时间估计校准（XGBoost on Khan） | ✅ Slice TC | `time_estimator.py` 改用可解释加权公式（非 XGBoost，无标注数据）；FullKGBuilder 已接入；calibrate_time 留观测加权钩子 |
| 48h 验证实验 E2E | 🔴 | Slice S |

---

## 6.1 调参文档

- `PGFGA-TUNING.md` — PGFGA 全套可调参数手册（信号词表 / 阈值 / 修复模板 / 监控指标 / 调参实验流程）

---

## 7. 给下一个工程师的入手清单

要继续 **Spine v2 (tutoring-mcp)**：
1. 读 `specs/tutoring-state-machine.md`（顶级会话状态机）
2. TDD：先写 `tests/unit/test_bkt.py`（一次答对 mastery 应升、连续答错应跌、参数边界）→ 红 → 实现 `servers/tutoring_mcp/bkt.py` → 绿
3. TDD：`test_session_crud.py` → `session.py`（持久化 SessionContext 到 sessions 表）
4. TDD：`test_engine_one_round.py` → `engine.py` 决策循环（最小：load context → strategy.start → strategy.get_action → respond → strategy.transition）
5. TDD：`test_tutoring_server_smoke.py` → `server.py` 三个 tool

要继续 **Slice K1 (depth=concept)**：
1. 在 `kg_builder.ConceptKGBuilder.build()` 里实现：
   ```python
   from research_tool.pipeline import Pipeline
   from research_tool.models import ExtractorConfig
   # ① 跑 research_tool 的 Extract 阶段拿 triples
   # ② 调 LLMProvider.chat 把 triple → 富 Concept + 12 种 SemanticRelation
   # ③ 走 _persist_kg() 落库
   ```
2. 配 `shared.llm_client.DeepSeekProvider`（继承 LLMProvider Protocol）
3. 添加 `shared/llm_cache.py` 三级缓存

要继续 **PGFGA 集成**：
- `non_judgment_firewall.py` 已就位，调用方应在 `respond()` 返回前过滤
- 还需 `flow_tracker.py` 实现 `FlowLevel` 状态机（详见 `pgfga-integration.md §二`）

---

## 8. 与桌面已有项目的复用边界

| 项目 | 复用方式 | 实施位置 |
|---|---|---|
| `C:/Users/yhn/pdf2zh/` | subprocess 调 `mineru -p ...` | `acquisition_adapter._convert_pdf` |
| `C:/Users/yhn/Desktop/调研/research-tool/` | uv path dep + import `research_tool.pipeline` | 待 `ConceptKGBuilder` + `_acquire_web` |
| `C:/Users/yhn/Desktop/调研/repos/cognee/` | 参考实现，**不直接 import** | — |
| `C:/Users/yhn/Desktop/调研/repos/autoschemakg/` | 同上 | — |

不直接 import 第三方仓库是为了：(1) 许可证隔离 (2) 避免传递依赖 (3) 学习成本可控。
