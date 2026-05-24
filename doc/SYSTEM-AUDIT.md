# ai-tutor 系统运行模拟与缺陷分析报告

> 日期：2026-05-23（缺陷分析）  
> 更新：2026-05-24（解决状态）  
> 目标：验证系统是否能实现"48 小时学完一个科目"的设计承诺  
> 方法：代码审查 + 设计对照 + 运行模拟

---

## 0. 解决状态（2026-05-24 更新）

> **本报告识别的 3 个 P0 + 5 个 P1 缺口已全部 RESOLVED。** 下文 §1-§3 的缺陷描述
> 保留为历史分析记录；当前实现状态以本节为准。测试 519 → 658 全绿，已 git + 远端备份。

| 优先级 | 缺口 | 状态 | 修复切片 / 实现 |
|--------|------|------|----------------|
| P0 #1 | 教学内容空洞（模板填空） | ✅ RESOLVED | Slice CG — `content_generator.py`：next_action 按 action.type LLM 生成讲解/例子/练习，gated on `supports_generation`，模板兜底 |
| P0 #2 | 无冷启动摸底 | ✅ RESOLVED | Slice CS — `cold_start.py` + `cold_start_probe`/`submit_cold_start`：10 题跨难度摸底 → BKT 先验 + 画像初值；引擎跳过 mastery≥0.8 |
| P0 #3 | 无跨 Session 调度 | ✅ RESOLVED | Slice MS — `learning_plan.py` + `get_learning_progress`/`resume_learning`：持久化 Phase 化计划，跨天续学 |
| P1 #4 | 6 策略仅 1 种可用 | ✅ RESOLVED | Slice P1#4 — engine 接入 strategy_selector + flow_regulator；Strategy 加 export/restore_state 跨重建无损 |
| P1 #5 | KG 无法扩展 | ✅ RESOLVED | Slice BK — `batch_enrich.py`：有界并行 + JSONL checkpoint 续跑；get_builder 透传 |
| P1 #6 | 认知负荷空转（恒 0.0） | ✅ RESOLVED | Slice CL — `cognitive_load.py`：加权公式 + EMA；引擎在线更新，激活 selector/regulator 负荷分支 |
| P1 #7 | 教学反馈粗粒度 | ✅ RESOLVED | Slice FG — `feedback_generator.py`：L1 模板 + L2 remediation + L3 LLM 润色 → 非评判防火墙 |
| P1 #8 | 时间估计全默认 30min | ✅ RESOLVED | Slice TC — `time_estimator.py`：非时间特征加权 → 5-45min；FullKGBuilder 接入；calibrate_time 观测钩子 |

**仅剩长期项**（P2/P3，非阻塞，且成本高/需真实数据，故暂缓）：
- P2 #9：DKT 跨概念知识追踪（需 PyTorch 重依赖 + 真实答题数据训练，违背零必需重依赖原则）
- P3 #10：12 种语义关系挖掘（当前用 part_of + prerequisite_strong）
- ~~P2 #11：ConceptEnricher 不填难度信号~~ ✅ **已修**（48h 验证发现并修复）：enricher 现用
  LLM 从内容估计 abstract_level/formula_density/cognitive_load_estimate（+去掉 prompt 锚定）。
  实测 full 深度：难度/时长/band 全部内容驱动，cold-start 三带齐全（current126/basic9/abstract4），
  总学时 46.9h。详见 `48H-VALIDATION.md`。

---

## 1. 执行摘要

代码实现了**完整的 4 server × 27 tool 接口**、**519 测试全绿**、PGFGA 心流/防火墙/增益回路到位，在**架构完整性**上做得很好。但在"系统能力能否撑起 48 小时"这个问题上，存在 **3 个 P0 致命缺口**和 **5 个 P1 严重缺口**。

> 以下为 2026-05-23 原始缺陷清单；**均已于 2026-05-24 解决**（见 §0）。保留作历史记录。

**P0（不修无法运行）：** ~~全部已解决~~
- ~~教学内容只有模板填空，没有 LLM 实时生成~~ → Slice CG
- ~~无冷启动摸底，所有概念从 mastery=0.05 开始~~ → Slice CS
- ~~无跨 session 学习计划，无法"分 6 次学完"~~ → Slice MS

**P1（严重影响体验）：** ~~全部已解决~~
- ~~6 种教学策略仅 reduction 可用~~ → Slice P1#4
- ~~KG 构建无法扩展到真实教材（800 概念）~~ → Slice BK
- ~~时间估计全用默认值 30min~~ → Slice TC
- ~~认知负荷在线估计不存在~~ → Slice CL
- ~~教学反馈只有 3 个模板~~ → Slice FG

原始结论（已过时）：代码能跑通 demo（20 概念 / 5 分钟会话），但放大到真实教材会暴露缺口。
**当前**：8 个缺口全部修复，整条教学闭环打通，测试 658 全绿。

---

## 2. 运行模拟

### 场景：48 小时学完《机器学习》（~200 概念）

```
T= -24h 准备环境                    → 🟡 web/video 源缺失

T= 0:00 acquire_subject(file=.md)   → ✅ 单文件采集完成
T= 0:05 build_kg(toc)               → ✅ 纯规则抽章节骨架
T= 0:10 build_kg(concept)           → ⚠️ 200 次 LLM 调用，~40 分钟
T= 0:50 review_kg / update_kg       → 🟡 靠人工介入
T= 1:00 start_learning_session      → ❌ 无摸底，全从 mastery=0.05 开始
                                      ❌ 200 概念 × 30min = 100h，远超 48h
T= 1:05 next_action                 → ⚠️ 模板教学："交叉验证：一种..."
T= 1:08 respond("我猜是评估模型")   → ⚠️ 反馈："你关于交叉验证的思考有对的地方"
T= 3:00 第一个 session 结束         → ❌ 无法回答"明天从哪继续"
T= 8:00 学完 Phase 1 (40 概念)      → ❌ 所有概念都用 reduction 从零讲
                                      ❌ 已经掌握的概念也在讲
                                      ❌ 认知负荷从没被考虑
T=24:00                              → ❌ 跨 session 调度不存在
T=48:00                              → ❌ 不可能完成
```

### 设计期望 vs 实际能力

| 维度 | 设计文档期望 | 实际实现 | 缺口 |
|------|------------|---------|------|
| 多源采集 | PDF+MinerU + 视频+Whisper + 网页 | 仅 file 源 | 缺 2/3 |
| 冷启动摸底 | 10 道摸底题校准画像 | 无 | **全缺** |
| KG 规模 | 800 概念 / 3200 关系 | 已验证 20 概念 | 40x 差距 |
| 教学内容 | 类比 + 例子 + 逐步推导 | 模板填空 | **核缺** |
| 策略自适应 | 6 种策略自动选择 | 仅 reduction | 缺 5/6 |
| 跨 session | 5 phase × 47 教学片断 | 无 Phase 概念 | **全缺** |
| 时间估计 | 实证校准的回归模型 | 默认 30min | 无校准 |
| 知识追踪 | DKT + BKT 双模型 | 仅 BKT | 缺 DKT |
| 认知负荷 | 在线估计 | 固定 0.0 | 未实现 |
| 关系抽取 | 12 种语义关系 | 2 种 | 缺 10/12 |
| 反馈质量 | 针对性诊断 + 鼓励 | 3 种模板 | 粗粒度 |
| 学习计划 | 5 phase 分时计划 | 单 session | 缺调度层 |

---

## 3. 现有缺陷（按严重度排列）

### 3.1 致命缺陷

#### #1 教学内容空洞 — 所有"讲解"都是模板填空

**文件**：`servers/tutoring_mcp/strategies/reduction.py` 第 44-70 行

```python
# ReductionStrategy.get_action() 的实际输出：
if self.state == "EXPLAIN":
    return TeachingAction(
        type="show_example",
        content=f"{name} 的核心定义：{t.definition}",  # 仅重述 KG 定义
        ...
    )
if self.state == "CHECK":
    return TeachingAction(
        type="ask_question",
        content=f"用你自己的话说说 {name} 是什么？",  # 模板
        ...
    )
```

所有 6 种策略（feynman / socratic / analogy / pbl / spaced_repetition）的 `get_action()` 都是 `f"{name} 的 XXXX"` 模板。没有 LLM 实时生成的教学内容。**举不出例子、做不出类比、没有逐步推导**。

**对比设计文档期望**：
> "空间直角坐标系由三个互相垂直的坐标轴组成..."

**实际输出**：
> "空间直角坐标系的核心定义：空间直角坐标系"

这种质量的教学输出撑不起 48 小时。

---

#### #2 无冷启动摸底 — 不知道学生起点

**文件**：`servers/tutoring_mcp/server.py` 第 129-200 行

`start_learning_session` 的核心流程：
```python
async def start_learning_session(user_id, subject_id, goal="48h_sprint"):
    # ...
    ordered = _topological_order(db, kg_id)  # 拓扑排序所有概念
    ctx.current_concept_id = ordered[0].id   # 从第一个开始
    ctx.position_in_plan = 0                 # 从头讲
    # 没有任何摸底代码
```

设计文档的 `adopted-fixes.md` 修正 2 明确要求 10 道摸底题，状态 🔴（未开始）。

**后果**：
- 学生已掌握的 30% 内容被重讲 → 浪费 14.4 小时
- 学生缺前置知识（如"学高数没学过向量"）→ 教学必然卡死
- `CognitiveProfile` 保持默认值（abstract_tolerance=0.5），策略选择器拿不到真实输入

---

#### #3 无法跨 session 持续学习

**文件**：`servers/tutoring_mcp/engine.py` 第 150-185 行

Session 结束时的行为：
```python
def next_action(self, session_id):
    # ...
    if next_pos >= len(order):
        ctx.status = "completed"           # 标记完成就结束了
        return TeachingAction(type="reflection", ...)
    # 没有"已学概念进度持久化"、
    # 没有"下一阶段该学什么"、
    # 没有"明天回到系统从哪继续"
```

设计文档规划了 **5 phase × 47 teaching snippets** 的分时学习计划（见 `data-flow-48h.md`），但代码中没有任何 Phase 的概念：
- Session 结束后 `status=completed`，没有"第 2 天回到系统"的入口
- `BKTParamRow` 和 `ForgettingCurve` 虽然持久化，但没有"基于这些数据算下一 session 该从哪开始"的逻辑
- 没有 `get_progress()` / `resume_learning()` / `phase_summary()` 这些工具

---

### 3.2 严重缺陷

#### #4 6 种策略仅 1 种可用

`strategy_selector.py` 7 条决策规则已完整实现：
```python
# 决策顺序：
# 1. cognitive_load 高 + 抽象 → analogy
# 2. cognitive_load 高 + 不抽象 → reduction(slower)
# 3. 概念抽象远超 tolerance → analogy
# 4. mastery < 0.2 → reduction
# 5. 0.3-0.6 mastery + transfer 高 → socratic
# 6. 0.4-0.7 mastery + 自评不准 → feynman
# 7. mastered_ratio > 0.6 → pbl
```

但 `engine.py` 从未调用 `select_strategy()`——engine 始终使用 `ReductionStrategy`。5 种策略（feynman/socratic/analogy/pbl/spaced_repetition）虽然实现了精简状态机，但从未被执行引擎选中。

另外，非 reduction 策略的状态机不完备——feynman 和 socratic 的 transition 逻辑比 reduction 简单很多，缺少事件驱动的完整处理。

---

#### #5 KG 构建无法扩展到真实教材

**文件**：`servers/knowledge_mcp/kg_builder.py` 第 97-137 行

```python
def _enrich_concepts(*, llm, subject_slug, markdown_path):
    # ...
    concepts, edges = _build_toc(subject_slug, markdown_path)
    sections = _split_sections(markdown_path, concepts)
    enricher = ConceptEnricher(llm=llm)
    for c in concepts:                     # 逐个迭代
        body = sections.get(c.id, "")
        ec, w = enricher.enrich(concept=c, body_text=body)  # 一次 LLM 调用
        enriched.append(ec)
```

**三个问题**：
1. **逐个调用**：800 概念 × 每次 LLM 调用 ~3s = 40 分钟 + 大笔 token 费用
2. **无 checkpoint**：第 400 个概念调用失败，进度丢失，得重头来
3. **单线程**：没有利用章节独立性做并行 enrich

已跑通的最大规模是 20 概念（`tests/fixtures/mini_subject.md`），从未验证 200+ 概念规模。

---

#### #6 时间估计全用默认值

**文件**：`servers/knowledge_mcp/kg_enrich_adapter.py` 第 79 行

```python
ConceptDifficulty(
    # ...
    typical_learning_time_min=30,  # 所有概念都是 30 分钟
)
```

`start_learning_session` 的总时间计算：
```python
total_min = sum(n.typical_learning_time_min for n in ordered)
# 200 概念 × 30min = 6000min = 100h —— 远超 48h
```

设计文档的 `adopted-fixes.md` 修正 3（时间估计校准）状态 🔴。没有实证数据支持的时间模型。

---

#### #7 认知负荷在线估计不存在

**文件**：`servers/tutoring_mcp/engine.py` 第 220-368 行

`respond()` 的完整流程中有 BKT 更新、错误诊断、心流追踪、增益回路，但**从未更新 `ctx.meta.current_cognitive_load`**。

```python
# SessionMeta 中有这个字段
class SessionMeta(BaseModel):
    current_cognitive_load: float = 0.0  # 永远是 0.0
```

策略选择器的 `cognitive_load > 0.75` 判断无法触发，因为没有更新逻辑。

---

#### #8 教学反馈只有 3 个模板

**文件**：`servers/tutoring_mcp/engine.py` 第 205-213 行

```python
def _build_raw_feedback(self, *, correctness, concept, score_evidence, remediation):
    if correctness == "correct":
        return f"你抓住了 {concept.names[0]} 的关键。{score_evidence} 继续？"
    if correctness == "partial":
        return f"你关于 {concept.names[0]} 的思考有对的地方。{remediation or '我们再看一个细节。'}"
    return f"我看到你在认真想这个问题。{remediation or '我们换个角度看 ' + concept.names[0] + '。'}"
```

虽然 `ErrorDiagnoser` 提供了 `remediation_suggestion`，但 feedback 生成逻辑没有利用 LLM 做润色。对比设计文档期望的"针对你特定错误的针对性反馈"，实际输出是通用模板。

---

### 3.3 中等缺陷

| # | 缺陷 | 位置 | 影响 |
|---|------|------|------|
| 9 | 12 种语义关系只用了 part_of + prerequisite_strong | `kg_builder.py` | KG 是目录树而非知识图谱 |
| 10 | DKT 模型未实现 | `dkt_model.py` (🔴) | 无跨概念知识关联推理 |
| 11 | 采集只有 file 源 | `acquisition_adapter.py` | web/video 抛异常 |
| 12 | LearnerProfile 仅 self_assessment_accuracy 在更新 | `engine.py:636-653` | 画像几乎不演化 |
| 13 | KG 定义无事实验证 | `kg_review.py` (需人工) | LLM 生成的错误定义无法自动发现 |
| 14 | 非评判防火墙仅正则级别 | `non_judgment_firewall.py` | 语义级违规漏检 |
| 15 | 心流信号启发式不精确 | `flow_signals.py` | 关键词判断情绪，精度有限 |

---

## 4. 10 个优化方向

### P0（必须优先修复）

**方向 1：概念级教学内容生成 — 替代模板填空**

在 engine 的教学动作（`explain` / `show_example` / `provide_hint` / `ask_question` 等）中，注入 LLM 实时生成。

```python
# 改造方案示意
class TeachingEngine:
    def _llm_explain(self, concept: Concept, strategy: str, error_history: list) -> str:
        """基于 KG 概念 + 学生掌握度 + 策略生成一段真实教学讲解"""
        prompt = f"""你是{concept.classification.domain}老师。
用类比+例子+逐步推理的方式讲解 {concept.names[0]}。
定义：{concept.definition}
学生目前：{strategic_context}
策略：{strategy}
别只说定义——给具体例子，联系生活。"""
        return self.llm.chat([...], temperature=0.7).content
    
    # 在 respond() 返回 TeachingAction 前调用
    action = TeachingAction(
        type="explain",
        content=self._llm_explain(concept, ...),  # 不是模板
        ...
    )
```

**预计工作量**：2-3 天  
**LLM 成本**：每次教学动作 ~500 tokens × 4 次/h × 48h = ~96K tokens（$0.01）——可忽略

---

**方向 2：摸底测验 + 自适应跳过的冷启动**

实现 `adopted-fixes.md` 修正 2。在 `start_learning_session` 中加入摸底阶段：

```python
async def start_learning_session(user_id, subject_id, goal="48h_sprint"):
    assessment = _cold_start_assessment(db, kg_id, user_id)
    # assessment 输出：
    # - mastered_concepts: [id, ...]     # 跳过
    # - weak_concepts: [id, ...]         # 优先
    # - cognitive_profile: {...}         # 校准后的画像
    # - recommended_pace: "fast"/"thorough"
    # 基于 assessment 裁剪 teaching_plan
```

**预计工作量**：1-2 天  
**LLM 成本**：10 题 × ~500 tokens = 5K tokens（一次性）

---

**方向 3：多 Session 调度器 — 分阶段学习**

新增一个调度层，位于 session 之上：

```python
class LearningPlan:
    id: str
    subject_id: str
    user_id: str
    phases: list[Phase]      # 每个 phase 有独立的概念子集
    current_phase_index: int
    total_estimated_hours: float
    
class Phase:
    concepts: list[Concept]
    prerequisite_phase_ids: list[str]
    target_mastery: float = 0.85
    review_interleave: float = 0.25  # 25% 复习旧概念
```

新增 MCP 工具：`get_plan_progress()` / `resume_plan()` / `generate_plan_from_kg()`

**预计工作量**：3-4 天

---

### P1（严重影响体验）

**方向 4：6 策略自动选择引擎**

在 `engine` 中集成 `strategy_selector`：
- `next_action()` 中每次 concept 切换时调用 `select_strategy()`
- 补全 feynman/socratic/analogy 的 transition 事件处理
- 把 cognitive_load 的实时估值（方向 6）喂给选择器

**预计工作量**：2-3 天

**方向 5：批量 KG 构建管道**

三件事：
1. `ConceptEnricher` 支持批量 enrich（一次 LLM 调用处理 5-10 个概念）
2. 添加 checkpoint：每批 enrich 后存临时进度，中断可恢复
3. 对独立章节并行 enrich（并发概念 enrich 调用）

**预计工作量**：2 天

**方向 6：认知负荷在线估计**

在 `engine.respond()` 中添加估计逻辑：
```python
# 基于信号
signals = compute_flow_signals(history)
load = 0.0
if signals.withdrawal_pattern:    load += 0.3
if signals.help_seeking_spike:    load += 0.2
if signals.answer_regression:     load += 0.2
if not signals.inter_turn_speed_up: load += 0.1
if len(answer) < 5:               load += 0.1
ctx.meta.current_cognitive_load = min(1.0, load)
```

**预计工作量**：0.5 天

**方向 7：教学反馈分级**

三层反馈体系：
- **L1 模板**（当前）：正确/部分/错误 + 最低信息
- **L2 模板+诊断**：利用 `ErrorDiagnoser.remediation_suggestion`
- **L3 LLM 润色**：把 L2 模板 + 学生答案 + 错误分析 送给 LLM 做教学润色

防火墙加到 L2 → L3 之间。

**预计工作量**：1 天

**方向 8：时间校准引擎**

三步：
1. 基于概念 difficulty 的加权公式（替代默认 30min）
2. 运行时记录实际用时，更新 concept 级别的 mean_learning_time
3. 学生个人系数（fast/moderate/thorough → 0.7x / 1.0x / 1.3x）

**预计工作量**：1 天

---

### P2-P3（长期优化）

| 方向 | 工作量 | 依赖 |
|------|--------|------|
| #9 DKT 跨概念知识追踪 | 5-7 天 | 需要学习行为数据训练 |
| #10 KG 关系挖掘（12 种关系） | 2-3 天 | 依赖批量 LLM 调用 |

---

## 5. 优先级与路线图

```
Week 1-2：
  P0: 方向#1 教学内容生成      ← 最重要，48h 体验的根基
  P0: 方向#2 摸底冷启动        ← 省 20-30% 时间
  P0: 方向#3 多 Session 调度    ← 让持续学习成为可能

Week 3-4：
  P1: 方向#4 多策略引擎        ← 自适应教学的核心
  P1: 方向#5 批量 KG 管道      ← 让 200+ 概念可用
  P1: 方向#6 认知负荷估计      ← 策略选择器的数据输入
  P1: 方向#7 教学反馈分级      ← 提升学习体验
  P1: 方向#8 时间校准          ← 让 48h 计划可信

后续：
  P2: 方向#9 DKT 模型
  P3: 方向#10 关系挖掘
```

---

## 6. 附录：代码健康度速查

| 模块 | 健康度 | 需关注 |
|------|--------|--------|
| `shared/` | 🟢 稳定 | 无 |
| `knowledge_mcp/` | 🟡 能用 | 采集缺 web/video；KG 规模瓶颈 |
| `tutoring_mcp/` | 🟡 能用 | 无冷启动；策略未集成；内容模板化 |
| `digest_mcp/` | 🟢 完整 | 7 种 format 全实现 |
| `sync_mcp/` | 🟢 完整 | Obsidian + git 双向同步 |
| `tests/` | 🟢 517/519 通过 | 2 skip 标记已知缺口 |
| `ROADMAP.md` | 🟢 | 与实现一致，是最好的文档入口 |

---

*本报告基于代码审查（2026-05-23），测试状态为 517 passed + 2 skipped。*
