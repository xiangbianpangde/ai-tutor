# 48 小时学习系统运行模拟

> 文件定位：在全部 10 个优化方向实现后的系统运行推演  
> 对照源：`ai-tutor-system-design/data-flow-48h.md`（设计文档）  
> 模拟科目：《同济版高等数学下册》（~400 页，~800 概念）  
> 学生画像：有一元微积分基础，初次接触多元微积分

---

## 1. 执行结论

**在全部 10 项优化完成后，系统能够支撑 48 小时学完一科的目标，但需要满足以下硬性条件：**

| 条件 | 阈值 | 风险等级 |
|------|------|---------|
| LLM API 可用 | 全程在线 | 🟢 低（设计有降级但体验下降） |
| 学生每天投入 ~8 小时 | 连续 6 天 | 🟡 中（依赖学生自律） |
| 教材概念 ≤ 800 | 45s/概念用于 LLM 富化 | 🟢 低（批量管道已优化） |
| 网络带宽 ≥ 10 Mbps | 多源采集 | 🟢 低 |
| 学生基础 ≥ 本科水平 | 前置掌握率 > 30% | 🟡 中（零基础要多 1.5x 时间） |

**核心结论**：教学引擎自身具备 48h 吞吐能力（理论极限 ~550 概念 / 46h 净教学），冷启动摸底可跳过 ~30% 已掌握内容，实际新学概念约 550 个，每个概念净教学时间 ~5 分钟。系统瓶颈不在技术侧，而在**学生认知耐力**——每天 8 小时高强度学习需要 PGFGA 心流维持。

---

## 2. 优化后架构全景

优化后的七层架构与优化前变化对比如下：

```
优化前                                   优化后
───────                                  ───────
L7: MCP Tool 接口                         ✅ 无大变化
L6: 仅 Reduction 策略                     ✅ 6 策略自动选择 + LLM 生成教学内容
L5: 仅 BKT + 默认画像                     ✅ DKT+BKT 双模型 + 冷启动摸底 + 认知负荷在线
L4: 逐个概念 enrich / 2 种关系            ✅ 批量 enrich + 12 种关系挖掘
L3: 遗忘曲线拟合                          ✅ 无大变化
L2: 单 Session                            ✅ 多 Session 调度层（Phase 概念）
L1: 存储 / Provider                       ✅ 无大变化

新增横切层:
- 教学内容生成器（LLM 实时讲解）
- 多 Session 调度器
- 认知负荷在线估计器
- 时间校准引擎
```

### 2.1 优化项映射

| 优化方向 | 状态 | 对应模块 |
|---------|------|---------|
| #1 教学内容生成 | ✅ 已实现 | `engine._llm_explain()` 替代模板 |
| #2 摸底冷启动 | ✅ 已实现 | `engine._cold_start_assessment()` |
| #3 多 Session 调度 | ✅ 已实现 | `scheduler.LearningPlan` + Phase |
| #4 6 策略引擎 | ✅ 已实现 | engine 调用 `strategy_selector` |
| #5 批量 KG 管道 | ✅ 已实现 | `ConceptEnricher.batch_enrich()` |
| #6 认知负荷估计 | ✅ 已实现 | `engine._estimate_cognitive_load()` |
| #7 反馈分级 | ✅ 已实现 | L1→L2→L3 三级反馈管道 |
| #8 时间校准 | ✅ 已实现 | 加权公式 + 运行时更新 |
| #9 DKT 模型 | ✅ 已实现 | `dkt_model.py` 轻量版 |
| #10 关系挖掘 | ✅ 已实现 | `kg_enrich_relations()` |

---

## 3. 48 小时完整时间线

### T=-24h ~ T=0:00（准备阶段）

```
[用户操作]
打开系统，输入："我要学同济版高等数学下册"

[系统响应]
1. 检查已有知识库 → 无
2. 提示多源采集：请提供教材 PDF（或自动搜索）

[用户操作]
放入 PDF 到输入目录，选择"自动采集"

[系统内部 — acquire_subject]
├─ [0:00:00] PDF→MinerU 转 Markdown (400页 × 3s = 20min)
│   → 并行：B站视频→yt-dlp→Whisper→章节对齐
│   → 并行：DuckDuckGo 搜索补充笔记
├─ [0:20:00] 多源归一化（去重 + 章节对齐）
└─ [0:25:00] 返回 corpus_id, total_chapters=12, estimated_concepts=800+

[用户操作]"开始建知识图谱"

[系统内部 — build_knowledge_graph(depth=full)]
├─ [0:00] 规则抽章节骨架（toc） → 12章 / 48节 / ~800 标题
├─ [0:01] 批量 ConceptEnricher（优化#5）
│   → 分 80 批，每批 10 概念，每批一次 LLM 调用
│   → 并行 enrich 独立章节（8 路并发）
│   → 每批写完 checkpoint（中断可恢复）
│   → 总计 ~80 次 LLM 调用 ≈ 8 分钟
├─ [0:09] 确定性难度校准 + embedding（1 分钟）
├─ [0:10] 关系挖掘（优化#10）
│   → 对相邻概念 LLM 推断 analogous_to / generalizes / proves
│   → ~400 次批量 LLM 调用 ≈ 5 分钟
├─ [0:15] 质量门：章节覆盖率 94%，3 个无示例
│   → review_kg 自动补示例（LLM 生成）
└─ [0:17:00] 返回 BuildKGResult
    kg_id=gaoshu-v8-kg-v1
    triples_count=3247
    concepts=847
    semantic_relations=12 种 (新增 analogous_to: 203, generalizes: 156, ...)
```

### T=0:00 ~ T=1:00（冷启动 + 摸底）

```
[用户操作] start_learning_session("yhn", "gaoshu", "48h_sprint")

[系统内部 — 优化#2 冷启动摸底]
├─ 从 847 概念中按三层抽象度采样 10 题：
│   - 3 题 abstract<0.3（极限基础 → 空间直角坐标系）
│   - 4 题 abstract 0.3-0.6（多元函数极限）
│   - 3 题 abstract>0.7（曲面积分）
├─ 每题后追问"你确定吗？"测自评校准
├─ 每题计时测 response_time

[摸底输出]
{
  "overall_mastery": 0.28,           # 整体已掌握 28%
  "mastered_concepts": ["空间直角坐标系", "向量运算", ...],  # ~237 个跳过
  "weak_concepts": ["曲面积分", "高斯公式", "格林公式"],
  "baseline_response_time_ms": 4200,
  "abstract_tolerance_initial": 0.62,
  "transfer_ability_initial": 0.45,
  "self_assessment_accuracy_initial": 0.55,
  "recommended_pace": "thorough",
  "recommended_starting_phase": "Phase 2"  # Phase 1 全跳过
}

[系统内部 — 优化#3 多 Session 调度]
├─ 基于摸底结果裁剪教学计划
├─ $847 \times (1 - 0.28) = 610$ 个未掌握概念
├─ 按 prerequisite 拓扑排序 → 5 Phase
├─ 优化#8 时间校准引擎: 每个概念 estimated_minutes
│   = $f(\text{formula\_density}, \text{abstract\_level}, \text{prereq\_count})$
│   × personal_pace_factor(0.85 for "fast")
├─ 总估计: $\sum(estimated\_minutes) = 42.3h$
└─ 返回 Phase 计划 + 第一个 action

[返回给用户]
Session 1/6 已创建
当前 Phase: Phase 2 — 多元函数微分学（预计 10h）
当前教学动作: "欢迎回来！从摸底看，你的向量代数基础扎实。
我们从多元函数开始。想象你站在一个山坡上——高度是 f(x,y)，
你的位置是 (x,y)。这就是二元函数的几何图像。"
```

### T=1:00 ~ T=47:00（教学循环）

#### Phase 2 示例：多元函数微分学（10h）

```
[教学循环 — 优化#1 LLM 教学内容 + 优化#4 策略选择]

T=1:00 ── 概念"二元函数的极限"
策略选择: reduction（新概念，mastery=0.05）
LLM 生成讲解:
"想象你手上有一张橡皮膜。捏住中心往上提——膜的形状就是 z=f(x,y)。
现在问：当 (x,y) 从各个方向靠近同一点时，膜的高度是不是趋向同一个值？
如果从东边靠近是 2，西边靠近是 3——这个极限就不存在。
这就是二元极限的核心：从任意路径逼近都必须收敛到同一值。
[生动的例子][视觉比喻]"
→ 学生阅读，理解

T=1:05 ── CHECK 状态
action: ask_question
LLM 生成问题:
"f(x,y) = (x²-y²)/(x²+y²)，当 (x,y)→(0,0) 时，
沿 x 轴 (y=0) 和沿 y 轴 (x=0) 分别趋向什么值？极限存在吗？"

T=1:07 ── respond("沿x轴→1，沿y轴→-1，所以不存在")
评分: correct（语义判分）
BKT 更新: 0.05 → 0.56
认知负荷: 0.35（正常）
反馈（优化#7 L3 润色）:
"你抓住了关键！沿不同路径的极限不一致→极限不存在。
继续思考：除了坐标轴，还可以沿 y=x 路径 → 0。
这正好是二元极限的独特之处——需要 ALL 路径一致。"

T=1:09 ── PRACTICE 状态
action: give_exercise
LLM 生成:
"证明 f(x,y)=xy/(x²+y²) 在 (0,0) 的极限不存在。
引导：尝试沿 y=kx 路径，看结果是否与 k 有关。"

T=1:12 ── respond("沿 y=kx → k/(1+k²)，与k有关→不存在")
评分: correct
BKT 更新: 0.56 → 0.72
认知负荷: 0.40
→ strategy 推进到 NEXT → 自动切到下一个概念

[T=1:15 ── 概念"偏导数"]
策略选择: analogy（mastery=0.15, cognitive_load=0.40, 抽象度=0.55）
LLM 类比:
"偏导数就像在二维地图上看等高线——你想知道东西方向有多陡（∂f/∂x），
就把 y 固定在某值，只让 x 变化，然后求导数。
就像一元导数是算曲线上某点的斜率——偏导数是曲面上某点、
沿某个方向的斜率。"
...
```

#### 打断场景

```
[T=3:45 ── 讲到"全微分"]
学生突然问："d 和 ∂ 符号有什么区别？"

[系统 — handle_interrupt]
├─ 保存 checkpoint（优化#3 调度器记录中断位置）
├─ IntentClassifier → intent="concept_question", confidence=0.92
├─ 响应（优化#1 LLM 生成）:
│   "好问题！d 和 ∂ 的区别就像：
│   d 是一条公路上的变化率（一元函数，只有一个方向）
│   ∂ 是一整片草原上的变化率（多元函数，方向无穷多）
│   所以 ∂f/∂x 表示"只沿 x 方向看的变化"，全微分 dz 则是所有方向的总变化。"
└─ 返回后学生说"明白了"，resume → 继续全微分
```

#### 认知负荷超载场景

```
[T=6:00 ── Phase 2 后半段，学了 ~60 个概念]
学生回答变短、变慢、错误率上升

[认知负荷估计器 — 优化#6]
├─ withdrawal_pattern: true（最近 3 轮都很短）
├─ inter_turn_speed_up: false（反应变慢）
├─ answer_regression: true（连续答错）
├─ current_cognitive_load: 0.81（超 0.75 阈值）
└─ 触发策略切换: reduction → analogy（优化#4）

系统主动建议:
"我发现信息量可能有点大了。要不要休息 10 分钟，
回来我们用更轻的方式继续？或者换一个更熟悉的类比来理解下个概念？"

学生: "休息一下"

[优化#3 调度器]
├─ 当前 Phase 进度: 65%
├─ 保存 checkpoint（含 cognitive_load 快照）
├─ 生成 Phase 摘要: "已学 65 个概念，掌握率 73%，薄弱点：方向导数、梯度"
└─ 30 分钟后 → resume，cognitive_load=0.3，继续
```

#### 心流状态

```
[T=12:00 ── 第三天 Session 3 中间]
学生进入深层心流（FlowLevel.DEEP → IMMERSED）

心流信号:
├─ answer_length_growth: true（回答越来越长、越完整）
├─ depth_increasing: true（开始自己推导、做关联）
├─ hesitation_decreasing: true（犹豫减少）
├─ initiative_taking: true（主动提"这个是不是跟 XXX 有关？"）
└─ net_score = +3 → IMMERSED

策略自动从 reduction 切换到 socratic（优化#4）:
"你觉得格林公式和斯托克斯公式之间有什么内在关系？"
—— 学生自己推导出"格林是斯托克斯在二维的特例"
→ mastery 从 0.65 跳到 0.88

PGFGA 增益回路日志:
"session_id=..., flow=immersed, concept=格林公式,
 self_corrected=true, initiative=true, 无断裂"
```

#### 复习调度

```
[每天教学开始 − 优化#3 调度器自动插复习]
Schedule: Phase 3 开始前 15 分钟

来自 L3 遗忘曲线（优化后）:
├─ 昨天学的 "方向导数" λ=0.25 → recall=0.68（到期）
├─ 前天学的 "梯度" λ=0.20 → recall=0.75（接近到期）
├─ 3 天前的 "全微分" λ=0.18 → recall=0.81（尚好）
└─ 复习优先级: 方向导数 > 梯度

复习模式选择（optimized）:
├─ 方向导数: mastery=0.71 → "quick_quiz"（30s 快速问答）
├─ 梯度: mastery=0.65 → "concept_map"（画关系图）
└─ 总复习时间: 6 分钟（优化#8 校准后）
```

### T=47:00 ~ T=48:00（收尾 + 学习报告）

```
[最后 Session 结束]
Phase 5（级数）最后概念"傅里叶级数"完成

[系统]
├─ BKT 统计: 847 概念中 mastery>0.85 的 683 个（80.6%）
├─ mastery 0.4-0.85 的 142 个（16.8%）
├─ mastery<0.4 的 22 个（2.6%，多为曲面积分高阶概念）
├─ DKT 跨概念预测: 学完级数后，傅里叶变换的前置掌握度达 0.63

学习报告:
📊 48 小时学习报告
━━━━━━━━━━━━━━━━━━━━
科目: 同济版高等数学下册
总概念: 847 | 跳过(已掌握): 237 (28%)
新学: 610 | 掌握(mastery>0.85): 566 (92.8%)

📈 掌握度分布
  mastered ████████████████████████ 92.8%
  learning ███                        5.8%
  weak     ▏                          1.4%

⏱ 时间分配
  净教学: 38.2h | 测评: 2.1h | 复习: 4.5h | 休息: 3.2h
  总效率: 610 新概念 / 38.2h ≈ 16 概念/小时

💪 优势领域
  多元函数微分学 → 掌握度 0.94
  重积分 → 掌握度 0.91
  向量代数 → 掌握度 0.95（摸底已掌握）

⚠️ 薄弱环节
  曲面积分 → 平均掌握度 0.62
  → 建议：生成 3 天复习计划

🎯 下一步推荐
  1. 交叉科目: 线性代数（大量 vector space 概念与你已学的向量分析重叠）
  2. 高阶挑战: 微分几何（需要曲线/曲面积分基础）
```

---

## 4. 关键数据流验证

### 4.1 冷启动摸底数据流（优化#2）

```
start_learning_session
  ├─ load KG (847 concepts)
  ├─ 按 abstract_level 分层采样 10 题
  ├─ 每题:
  │   ├─ LLM 生成题面（基于 KG 定义）
  │   ├─ 学生作答
  │   ├─ LLMScorer 语义判分
  │   ├─ 记录 correctness + response_time
  │   └─ 追问题"确定吗？"
  ├─ 汇总:
  │   ├─ overall_mastery = Σ(correctness × weight) / Σ(weight)
  │   ├─ abstract_tolerance = accuracy on high-abstract items
  │   ├─ self_assessment_accuracy = 自评 vs 实际的校准
  │   └─ recommended_pace = f(correct_rate, response_time)
  ├─ 标注已掌握概念（BKT init 设 p_mastery=0.85）
  ├─ 裁剪 teaching_plan（移出 mastered，排序 weak）
  └─ 返回裁剪后的 Phase 计划
```

### 4.2 教学循环数据流（优化#1 + #4 + #6 + #7）

```
next_action(session_id)
  ├─ load session context
  ├─ 如果是 concept 切换:
  │   ├─ strategy_selector.select_strategy(
  │   │     concept=concept, mastery=..., 
  │   │     cognitive_load=..., profile=..., mastered_ratio=...)
  │   │   → 返回 "reduction" | "feynman" | "socratic" | "analogy" | "pbl"
  │   └─ 实例化对应策略
  ├─ strategy.get_action() → type + 参数
  ├─ _llm_generate_content(type, concept, strategy, context)
  │   ├─ 如果是 explain:
  │   │   prompt = f"你是{domain}老师。用类比+例子+逐步推导
  │   │             讲解 {name}：{definition}。学生情况:{context}"
  │   └─ 如果是 ask_question:
  │       prompt = f"出一道检测学生对{name}理解的选择/问答。
  │                当前是第{attempt}次尝试。难度对应{strategy}策略。"
  ├─ 返回 TeachingAction(content=llm_output, ...)
  └─ 同时: cognitive_load 估计器更新 ctx.meta

respond(session_id, answer)
  ├─ LLMScorer.score() → correctness + evidence
  ├─ BKT.update() + DKT.update() (优化#9)
  ├─ ErrorDiagnoser.diagnose() → error_type + remediation
  ├─ _estimate_cognitive_load() → 0.0-1.0 (优化#6)
  ├─ _build_feedback():
  │   ├─ L1: {correct|partial|incorrect} + 模板 (紧急备用)
  │   ├─ L2: L1 + remediation_suggestion (标准模式)
  │   └─ L3: L2 文本 → LLM 润色 → 防火墙检查 → 最终 (默认)
  ├─ strategy.transition("answered", {correctness})
  ├─ flow_signals → flow_level update
  ├─ gain_loop_monitor.detect_break() → 必要时出修复 action
  └─ 返回 ResponseResult(feedback=..., mastery=..., next_action=...)
```

### 4.3 多 Session 调度数据流（优化#3）

```
LearningPlan.generate(subject_id, user_id, kg_id)
  ├─ 摸底结果 → mastered_concepts, weak_concepts
  ├─ 拓扑排序未掌握概念
  ├─ 切 Phase（动态容量: Phase size = 总概念/5 + 章节自然边界）
  ├─ 每 Phase:
  │   ├─ concepts: list[id]（含 20% 复习旧概念穿插）
  │   ├─ estimated_hours: 校准后的时间戳求和
  │   ├─ target_mastery: 0.85
  │   └─ prerequisite_phase_ids: 依赖的上阶段
  ├─ 持久化到 learning_plans 表
  └─ 返回 LearningPlan

resume_plan(plan_id, session_number)
  ├─ 查 plan → 定当前 phase
  ├─ 查 BKT → 定跳过 mastery>0.85 的概念
  ├─ 查遗忘曲线 → 拼复习列表
  ├─ 构建 SessionContext（concept_queue = phase.concepts 裁剪后）
  └─ 返回第一个 action

get_plan_progress(plan_id)
  ├─ 各 Phase 完成度: Σ(mastery>0.85) / Σ(phase_concepts)
  ├─ 时间: actual_hours / estimated_hours
  ├─ 薄弱概念: mastery<0.4 的 top-5
  └─ 建议: "当前落后估计 1.2h，建议增加每次 session 时长 15min"
```

### 4.4 时间校准引擎数据流（优化#8）

```
# Phase 1: 构建基线模型
compute_estimated_time(concept):
    base = (
        0.30 × formula_density +
        0.20 × abstract_level +
        0.20 × prereq_max_depth / 10 +
        0.15 × cognitive_load_estimate +
        0.15 × coupling
    ) × 30  # 默认 30min 基数
    return max(5, min(60, base))

# Phase 2: 运行中校准
每完成一个概念:
  actual = session_timer.elapsed
  predicted = concept.typical_learning_time_min
  # 指数移动平均
  new_estimate = 0.7 × predicted + 0.3 × actual
  concept.typical_learning_time_min = round(new_estimate)

# Phase 3: 个性化
personal_factor:
    fast → 0.70
    moderate → 1.00
    thorough → 1.30
estimated = compute_estimated_time(concept) × personal_factor
```

---

## 5. 边界情况验证

### 5.1 LLM API 暂时中断

```
场景: Phase 3 中途 DeepSeek API 返回 503

降级链:
├─ 教学内容生成（优化#1）:
│   → 降级到 KG 模板（优化前的状态，体验降级但不停机）
│   → 输出: "全微分的定义：{t.definition}"
│   → 标记 degraded_turns+=1，恢复后重新生成该内容
├─ 判分:
│   → LLMScorer → 降级到启发式 2-gram（正确率下降）
├─ 意图分类:
│   → IntentClassifier → 降级到关键词匹配
├─ 反馈润色（优化#7 L3）:
│   → 降级到 L2 模板+诊断（仍然可用）
└─ API 恢复后自动切回完整模式

影响: 教学体验下降但不会中断
恢复后弹出提示: "之前中断期间有 5 个概念用了简化教学，
建议花 10 分钟复习这些概念——需要我生成复习列表吗？"
```

### 5.2 学生零基础（无前置知识）

```
摸底结果: overall_mastery=0.03 (847 概念几乎全零)
abstract_tolerance=0.25, transfer_ability=0.20 → 严重缺乏抽象思维
recommended_pace="thorough"

调整:
├─ Phase 1 不跳过任何概念（跳过量 = 0）
├─ 个人时间因子: thorough → 1.3x
├─ 总预估: 610_concepts × 5min × 1.3 = 66h
│   → 提示用户: "预估需要 66 小时（~8 天）而不是 48 小时。
│     建议第一天先学 6 小时感受节奏，或选择一门更基础的先修科目。"
├─ 策略倾向: 多数概念用 analogy（抽象度高的更适合类比）
└─ 认知负荷阈值降低: 0.6 即触发休息建议（而非默认 0.75）

结论: 零基础不可能 48h，系统诚实告知并推荐调整方案。
```

### 5.3 学生中途中断 3 天

```
场景: Phase 3 完成 60% 后中断 3 天

恢复流程:
├─ resume_plan() → 加载 checkpoint
├─ 遗忘曲线预测:
│   ├─ Phase 1 概念: 3 天遗忘 → recall=0.65~0.85
│   ├─ Phase 2 概念: 部分到 0.50~0.70
│   └─ Phase 3 进行中: recall=0.75~0.90
├─ 自动插入"快速复习":
│   ├─ recall<0.5: 完整 teach_back（每个 3min）
│   ├─ 0.5≤recall<0.7: concept_map（每个 2min）
│   └─ recall≥0.7: quick_quiz（每个 30s）
├─ 总复习时间: ~25 个到期概念 × 2min = 50min → 作为 Phase 3 的前缀
└─ 返回: "欢迎回来！3 天没见，我们先花 50 分钟快速回顾。然后从全微分继续。"
```

### 5.4 教材概念间有环

```
resolve_conflicts(kg_id) → detected:
  "多元函数 → 偏导数 → 方向导数 → 梯度"
  → 这是虚拟环（概念间互相引用但不是逻辑依赖）
  → 系统标记为 "benign_circular", 保留所有边

  "曲线积分 → 曲面积分 → 曲线积分"
  → 这是真环（互相前置）
  → 自动修复: 弱化一条边为 prerequisite_weak
  → 报告: "已自动修复 1 个真环。曲线积分和曲面积分互相依赖，
     已将 '曲面积分→曲线积分' 降级为弱前置。建议学生先学曲线积分基础。"
```

---

## 6. 硬性约束

### 6.1 LLM 调用量估算

| 阶段 | 调用类型 | 调用次数 | Token 量 |
|------|---------|---------|----------|
| KG 构建 | 概念 enrich（批量 10/次） | ~80 | ~240K in |
| KG 构建 | 关系挖掘 | ~40 | ~160K in |
| 摸底 | 题目生成 + 判分 | ~12 | ~12K in |
| 教学 | 教学内容生成（4次/h × 38h） | ~152 | ~228K out |
| 教学 | LLM 判分（6次/h × 38h） | ~228 | ~114K in |
| 教学 | 反馈润色（同上） | ~228 | ~114K out |
| 教学 | 意图分类（打断 ~10 次） | ~10 | ~3K in |
| 打断 | 内容响应 | ~10 | ~15K out |
| 复习 | 问题生成 | ~30 | ~15K out |
| **总计** | | **~790** | **~900K tokens** |

以 DeepSeek V4 Flash $0.14/M 计：~$0.13
以 DeepSeek V4 Pro $0.53/M 计：~$0.48

**结论：LLM 成本可忽略（< $0.50），瓶颈在于 API 延迟而非成本。**

### 6.2 学生时间线假设

```
Day 1 (8h): 摸底(1h) + Phase 1 向量代数(3h) + Phase 2 开头(4h)
Day 2 (8h): Phase 2 多元微分(8h)
Day 3 (8h): Phase 2 收尾(2h) + Phase 3 重积分开始(6h)
Day 4 (8h): Phase 3 重积分(8h)
Day 5 (8h): Phase 4 曲线/曲面积分(8h)
Day 6 (8h): Phase 5 级数(4h) + 总复习(3h) + 学习报告(1h)
          ───────
总计: 48h
```

**风险**：Daily 8h 高强度学习需要极强的心流维持。PGFGA 心流追踪 + 认知负荷监测是关键技术依赖——如果未能有效维持心流，实际效率可能下降 30-50%。

---

## 7. 成功验收标准

```
┌─────────────────────────────────────────────────────────────┐
│              48h 学习成功验收清单                           │
├─────────────────────────────────────────────────────────────┤
│  □ 摸底时间 ≤ 1h                                            │
│  □ KG 构建（含关系挖掘）≤ 25min                              │
│  □ 净教学吞吐 ≥ 12 概念/小时                                 │
│  □ 最终掌握率 (mastery>0.85) ≥ 75%                           │
│  □ 计划偏差 |actual - predicted| / predicted ≤ 25%           │
│  □ 心流抑制中断 (FlowLevel.SILENT) ≤ 3 次                    │
│  □ 增益回路断裂自动修复 ≥ 80%                                 │
│  □ 零内容模板 （所有 explain 动作经 LLM 生成）                 │
│  □ 跨 Session 恢复 ≤ 10s                                     │
│  □ LLM API 故障降级能维持基础教学不停机                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 优化前 vs 优化后对照

| 维度 | 优化前（当前代码） | 优化后 | 改善 |
|------|------------------|--------|------|
| 教学内容 | 模板填空："{name} 的定义：{definition}" | LLM 实时生成类比+例子+推导 | **核缺修复** |
| 冷启动 | mastery=0.05 硬起 | 10 题摸底，跳过 28% 已掌握内容 | 省 ~14h |
| 教学策略 | 仅 reduction | 6 策略自动选择 | 自适应 |
| 跨 Session | Session→completed，无后文 | 5 Phase × 6 Session 全链路 | **核缺修复** |
| KG 构建 | 逐个 enrich，800 概念 ~40min | 批量并行，~8min | 5x 提速 |
| 认知负荷 | 永远是 0.0 | 在线估计，触发策略/休息 | 防崩溃 |
| 反馈 | 3 个模板 | 三级管道 + LLM 润色 | 质变 |
| 时间估计 | 默认 30min/概念 | 加权公式 + 运行时校准 | 误差从 ±50%→±20% |
| 知识追踪 | 单概念 BKT | BKT + DKT 轻量版 | 跨概念归因 |
| KG 关系 | 2 种 | 12 种语义关系 | 丰富教学路径 |
| 可完成 48h | ❌ 不可能 | ✅ 有条件可行 | — |

---

## 9. 剩余风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| PGFGA 无法维持 8h 心流 | 中 | 效率降 50% | 每 90min 强制微休息；认知负荷阈值预警 |
| 学生中途放弃 | 高 | 完全失败 | 学习报告激励；每 Phase 完成发"里程碑"通知 |
| API 成本超预期 | 低 | < $1 | 已估算，可忽略 |
| 教材内容过时/错误 | 低 | 局部出错 | review_kg + update_kg 人工修正通 道 |
| 学生实际掌握 ≠ BKT 值 | 中 | 自评失真 | 检查点对比 + 元认知校准（已有） |
| 数学公式渲染问题 | 中 | 理解障碍 | digest 支持 LaTeX；教学内容用自然语言描述公式 |

---

*本模拟基于"全部 10 项优化已实现"的假设。优化前系统的状态见 `SYSTEM-AUDIT.md`。模拟版本：v1.0，2026-05-23。*
