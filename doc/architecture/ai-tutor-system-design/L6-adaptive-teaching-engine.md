# L6 自适应教学引擎

> 职责：基于 L5 的学生模型和 L4 的知识图谱，动态选择教学策略、生成教学动作、实时调整节奏  
> 输入：TeachingContext（来自 L5）、KnowledgeGraph（来自 L4）、学生反应  
> 输出：教学动作序列 + 策略选择日志 + 干预决策

---

## 1. 六种教学策略原语

### 1.0 策略原语的形式化

每个策略原语是一个**有限状态机**，包含：

- **触发条件**：什么情况下选用此策略
- **输入参数**：可调节的具体参数
- **状态转换**：在哪些状态间如何流转
- **退出条件**：何时判定完成并切换策略
- **与学生反应的交互规则**：遇到每种反应该如何处理

---

### 1.1 降阶法（Reduction of Order）

**用途**：系统学习新科目，从最基础的概念开始，逐步向上。

**触发条件**：学生对该科目是新接触，或 L5 画像显示 `preferred_pace = "thorough"`。

```python
ReductionOfOrderParams = {
    'topology': Literal['bottom_up', 'top_down'],
    # bottom_up: 从叶子节点（无前置）开始 → 逐步向上（默认）
    # top_down: 从目标概念开始 → 向下追溯前置 → 再向上讲
    
    'skip_threshold': float,        # mastery > 此值跳过（默认 0.85）
    'fast_mention_threshold': float,# 琐碎概念嵌入讲解不单独开片断
    'max_concepts_per_session': int,# 单次会话最多讲几个概念
    'review_interleave_ratio': float, # 每 N 个新概念插入 1 个复习概念
}

# 状态机
states = {
    'PLAN':     # 构建教学路径（拓扑排序）
    'INTRO':    # 引入新概念（类比、实际背景）
    'EXPLAIN':  # 正式讲解（定义→定理→例子→反例）
    'CHECK':    # 理解检测（快速问答）
    'PRACTICE': # 练习（递进难度）
    'NEXT':     # 进入下一个概念
    'SESSION_END':  # 今日学习量完成
}

transitions = {
    'PLAN → INTRO':        '路径构建完成',
    'INTRO → EXPLAIN':     '引入完成，开始正式讲解',
    'EXPLAIN → CHECK':     '讲解完成，检测理解',
    'CHECK → PRACTICE':    'p_mastery > 0.6，进入练习',
    'CHECK → EXPLAIN':     'p_mastery < 0.4，重新讲解（换方式）',
    'CHECK → NEXT':        'p_mastery > 0.85，跳练习直接进入下一个',
    'PRACTICE → NEXT':     '练习正确率 > 80%',
    'PRACTICE → EXPLAIN':  '练习正确率 < 50%，回退到讲解',
    'NEXT → INTRO':        '还有概念未讲 → 继续',
    'NEXT → SESSION_END':  '本日配额完成',
    # 任何状态 → 中断处理（见 3.2）
}

# 核心算法
def build_teaching_path(kg: KnowledgeGraph, target_concept_id: str, 
                        mastery_map: Dict[str, float],
                        params: ReductionOfOrderParams) -> TeachingPath:
    """
    1. 从 target_concept 出发，沿 prerequisite 边反向 BFS
       收集所有需掌握的前置概念，得到依赖子树 G_sub
    2. 移除 mastery > skip_threshold 的节点
    3. 拓扑排序 → 层序 L0, L1, ..., Ln
       L0: 无前置依赖的概念（基础层）
       L1: 仅依赖 L0
       ...
       Ln: target_concept
    4. 对每层生成教学片断:
       TeachingSnippet = {
         concept: Concept,
         depth: int,               # 所在层
         estimated_minutes: int,   # 预估教学时长
         teaching_method: str,     # 本片断的子策略
         review_slot: bool,        # 是否在此处插入复习
       }
    """
```

---

### 1.2 费曼法（Feynman Technique）

**用途**：检验学生是否真正理解一个概念，而非机械记忆。

**触发条件**：L5 画像 `self_assessment_accuracy < 0.5`（自评不准），或概念 `abstract_level > 0.7`。

```python
FeynmanParams = {
    'fidelity_threshold': float,    # 解释中的关键要素覆盖率 ≥ 此值 → pass（默认 0.8）
    'max_attempts': int,            # 最多重新解释次数（默认 3）
    'guidance_level': int,          # 提示等级 0(不提示)~3(逐步提示)
}

states = {
    'PROMPT':              # "请用你自己的话向一个零基础的人解释[概念]"
    'WAIT_EXPLANATION':    # 等待学生回答
    'EVALUATE':            # 评估学生的解释
    'PASS':                # 通过，进入下一概念
    'GUIDED_CORRECTION':   # 指出具体遗漏点，给提示
    'SIMPLIFY':            # 学生连续失败 → 降级到更基础的解释
    'MODEL':               # 系统给出范例解释
}

transitions = {
    'PROMPT → WAIT_EXPLANATION':   '提问已发出',
    'WAIT_EXPLANATION → EVALUATE': '学生提交了解释',
    'EVALUATE → PASS':             'fidelity ≥ threshold',
    'EVALUATE → GUIDED_CORRECTION':'fidelity < threshold, attempts < max',
    'GUIDED_CORRECTION → PROMPT':  '提示已给出，重新提问',
    'EVALUATE → SIMPLIFY':         'attempts ≥ max/2，需要降级',
    'EVALUATE → MODEL':            'attempts ≥ max，系统示范',
    'MODEL → PROMPT':              '示范后让学生再讲一遍'
}

def evaluate_fidelity(student_explanation: str, concept: Concept, kg: KnowledgeGraph) -> FidelityScore:
    """
    评估维度:
    1. 核心定义覆盖度: 学生是否提到了概念定义中的关键词？
    2. 例子质量: 举的例子是否正确、贴切？
    3. 反例意识: 是否知道什么不是这个概念？
    4. 关系意识: 是否提及了与其他概念的关系？
    5. 语言转化度: 是否用自己的话而非逐字背诵？
    
    每项 0~1 分，加权平均 → fidelity_score
    """
```

---

### 1.3 苏格拉底法（Socratic Method）

**用途**：引导发现式学习，适用于学生已有一定基础但未形成深层理解时。

**触发条件**：L5 显示 `transfer_ability > 0.6`（有举一反三能力），但某概念 `mastery < 0.5`。

```python
SocraticParams = {
    'question_chain_depth': int,    # 最多追问几层（默认 3~5）
    'hint_level': int,              # 初始提示深度 0~3
    'discovery_threshold': float,   # 学生自己"发现"答案的程度（> 0.7 才算自主发现）
}

states = {
    'QUESTION':             # 提一个引导性问题
    'WAIT_ANSWER':          # 等待回答
    'ANALYZE_ANSWER':       # 分析回答方向
    'NUDGE':                # 轻度推动（"你再想想..."）
    'HINT':                 # 给出提示（不直接给答案）
    'REVEAL':               # 所有引导失败，揭示答案
    'REFLECT':              # 揭示后让学生反思为什么没想到
}

transitions = {
    'QUESTION → WAIT_ANSWER':        '',
    'WAIT_ANSWER → ANALYZE_ANSWER':  '',
    'ANALYZE_ANSWER → QUESTION':     '回答方向正确，继续追问下一层',
    'ANALYZE_ANSWER → NUDGE':        '回答接近但有偏差',
    'ANALYZE_ANSWER → HINT':         '回答方向偏得远',
    'ANALYZE_ANSWER → REVEAL':       '学生的思维完全卡死',
    'NUDGE → WAIT_ANSWER':           '',
    'HINT → WAIT_ANSWER':            '',
    'REVEAL → REFLECT':              '',
    'REFLECT → (exit)':              '',
}

def generate_socratic_question(concept: Concept, current_understanding: str, depth: int) -> str:
    """
    每层问题的设计:
    Layer 1 (depth=1): 具体体验 → "你能举一个极限存在的例子吗？"
    Layer 2 (depth=2): 反思观察 → "这个例子里为什么极限是存在的？"
    Layer 3 (depth=3): 抽象概括 → "从这两个例子看，极限存在需要什么条件？"
    Layer 4 (depth=4): 主动实验 → "如果我把某个条件去掉，极限还存在吗？"
    Layer 5 (depth=5): 迁移应用 → "这个判定条件能推广到多元函数吗？"
    """
```

---

### 1.4 项目驱动法（Project-Based Learning）

**用途**：综合应用多个概念，解决一个具体问题。

**触发条件**：L5 显示该科目 `mastered_count > 60%`（有一定基础），或 L5 画像 `transfer_ability > 0.5`。

```python
PBLParams = {
    'milestones': List[{
        'description': str,
        'concepts_required': List[str],
        'deliverable': str,
        'estimated_hours': float,
    }],
    'scaffolding_level': Literal['full', 'partial', 'minimal'],
}

states = {
    'ASSIGN':           # 布置项目
    'PLAN_REVIEW':      # 学生的项目计划→系统反馈
    'MILESTONE_CHECK':  # 阶段性检查
    'DELIVERABLE':      # 收到交付物
    'FEEDBACK':         # 给出反馈
    'FINAL_REVIEW':     # 终审
}

transitions = {
    'ASSIGN → PLAN_REVIEW':            '',
    'PLAN_REVIEW → ASSIGN':            '计划不合格，重新布置',
    'PLAN_REVIEW → MILESTONE_CHECK':   '计划通过',
    'MILESTONE_CHECK → FEEDBACK':      '',
    'FEEDBACK → MILESTONE_CHECK':      '还有下一个里程碑',
    'FEEDBACK → FINAL_REVIEW':         '所有里程碑完成',
}

def design_pbl(kg: KnowledgeGraph, concepts: List[str], learner: LearnerProfile) -> PBLParams:
    """
    项目设计原则:
    - 涉及 3~8 个概念（不宜太多）
    - 包括学习(learn) + 应用(apply) + 创造(create)
    - 每个里程碑有明确的 deliverable（可验证）
    - scaffolding_level 根据学生能力自动调节
    """
```

---

### 1.5 类比桥接（Analogical Bridging）

**用途**：用已知领域的知识类比解释未知领域的抽象概念。

**触发条件**：概念 `abstract_level > learner.abstract_tolerance * 1.2`（概念对学生来说太抽象）。

```python
AnalogyBridgeParams = {
    'source_domain': str,           # 类比源领域（从 student_profile.strongest_domains 自动选取）
    'mapping': List[{               # 概念映射
        'target_element': str,      # 目标概念的元素
        'source_element': str,      # 源领域的类比元素
        'isomorphism_strength': float,  # 映射的精确度（0=不准确, 1=完美同构）
    }],
    'breakaway_point': str,         # 类比不再成立的临界点（必须标明！）
}

states = {
    'ESTABLISH_SOURCE':     # "你对XX（学习者已知领域）熟吗？"
    'DRAW_ANALOGY':         # 画出类比映射
    'APPLY_ANALOGY':        # 用类比的逻辑推理解释目标概念
    'IDENTIFY_LIMITS':      # 指出类比失效的地方（避免过度泛化）
    'TRANSITION':           # 过渡到精确的（非类比）定义
}

def find_best_analogy_source(concept: Concept, learner: LearnerProfile) -> str:
    """
    - 从 learner.strongest_domains 中选择与 concept.cross_domain_tags 重叠最多的领域
    - 用 embedding 相似度找到概念匹配
    - LLM 验证类比映射的合理性
    """
```

---

### 1.6 间隔复习（Spaced Repetition）

**用途**：对抗遗忘，将知识从短期记忆巩固到长期记忆。

**触发条件**：见 L3 的复习调度器；由 L3 推送到 L6。

```python
SpacedRepetitionParams = {
    'algorithm': Literal['sm2', 'ebbinghaus', 'personalized'],
    'urgent': bool,                 # 是否为紧急复习（考试前）
    'review_mode': Literal['quick_quiz', 'concept_map', 'teach_back', 'error_revisit'],
}

states = {
    'RECALL':           # 自由回忆："昨天学了什么？"
    'FOCUSED_REVIEW':   # 针对特定概念的复习
    'INTERLEAVED_QUIZ': # 交错测试（混入其他概念）
    'CONSOLIDATE':      # 学习总结"今天的复习你掌握了..."
    'RESCHEDULE':       # 根据本次复习结果更新下次复习时间
}
```

---

## 2. 策略选择引擎

### 2.1 自动策略选择

```python
def select_strategy(concept: Concept, teaching_context: TeachingContext) -> Tuple[Strategy, StrategyParams]:
    """
    决策树（优先级从上到下）:
    """
    
    profile = teaching_context.learner_profile
    mastery = teaching_context.mastery_map.get(concept['id'], 0.0)
    
    # Rule 1: 认知过载 → 降级
    if teaching_context.cognitive_load > profile.cognitive.overload_threshold:
        if concept['difficulty']['abstract_level'] > 0.5:
            return (AnalogousBridging, {...})   # 用类比降低抽象度
        else:
            return (ReductionOfOrder, {'topology': 'bottom_up', 
                                       'skip_threshold': 0.99})  # 强制从头讲，不跳过任何
    
    # Rule 2: 抽象度过高 → 类比桥接
    if concept['difficulty']['abstract_level'] > profile.cognitive.abstract_tolerance * 1.2:
        return (AnalogousBridging, {...})
    
    # Rule 3: 新概念 → 降阶法
    if mastery < 0.2:
        return (ReductionOfOrder, {
            'topology': 'bottom_up',
            'skip_threshold': 0.85,
        })
    
    # Rule 4: 部分掌握 + 自评不准 → 费曼检验
    if 0.4 <= mastery < 0.7 and profile.metacognitive.self_assessment_accuracy < 0.5:
        return (FeynmanTechnique, {
            'fidelity_threshold': 0.7,
            'max_attempts': 3,
        })
    
    # Rule 5: 有一定基础 + 迁移能力强 → 苏格拉底引导发现
    if 0.3 <= mastery < 0.6 and profile.cognitive.transfer_ability > 0.5:
        return (SocraticMethod, {
            'question_chain_depth': 4,
            'hint_level': 2,
        })
    
    # Rule 6: 有已知强领域且概念有跨域标签 → 类比桥接
    if concept.get('cross_domain_tags') and profile.knowledge.strongest_domains:
        overlap = set(concept['cross_domain_tags']) & set(profile.knowledge.strongest_domains)
        if overlap:
            return (AnalogousBridging, {'source_domain': overlap[0]})
    
    # Rule 7: 该科目大部分已掌握 → 项目驱动
    if profile.knowledge.mastered_count > 0.6 * profile.knowledge.total_concepts_mastered:
        return (ProjectBasedLearning, {...})
    
    # Rule 8: fallback → 降阶法
    return (ReductionOfOrder, {'topology': 'bottom_up'})
```

### 2.2 策略组合与切换

一个教学阶段可能组合多个策略原语：

```
例：讲解"多元函数极值"（高抽象 + 前置依赖多）

Step 1: 降阶法 → 确保偏导数等前置掌握
Step 2: 类比桥接 → "多元极值就像在一元极值的基础上多了几个方向"
Step 3: 降阶法（正式讲解）→ 从二元到多元逐步推广
Step 4: 费曼法 → 检测是否真正理解
Step 5: 苏格拉底法 → 引导学生自己发现"极值判定条件为什么需要二阶导数"
```

策略切换由**实时教学决策循环**控制（见下文 3.1）。

---

## 3. 实时教学决策循环

### 3.1 核心循环

```python
def teaching_loop(session: TutoringSession, kg: KnowledgeGraph, 
                  tracer: KnowledgeTracer, profile: LearnerProfile):
    """
    每个教学步骤内执行:
    """
    
    while not session.is_complete():
        # (1) 获取 L5 的最新学生状态
        context = tracer.get_teaching_context(session.student_id, session.subject_id)
        
        # (2) 获取 L3 的复习建议
        review_suggestion = long_memory.get_review_suggestion(session.student_id, 
                                                              session.current_concept_id)
        
        # (3) 选择教学策略
        concept = kg.get_concept(session.current_concept_id)
        strategy, params = select_strategy(concept, context)
        
        # (4) 执行一个教学步骤
        action = strategy.next_action(session, concept, params, context)
        # action 结构:
        # {
        #   'type': 'explain' | 'ask_question' | 'show_example' | 
        #           'give_exercise' | 'request_explanation' | 'wait' | 'review',
        #   'content': str,            # 教学内容
        #   'expected_duration': int,  # 预估耗时（分钟）
        #   'difficulty_adaptation': str,  # 难度调整说明
        # }
        
        # (5) 发送给学生（通过 L7 交互层）
        yield action
        
        # (6) 等待学生反应
        student_reaction = yield  # 阻塞，等待 L7 传回学生输入
        
        # (7) 分析学生反应
        analysis = analyze_student_reaction(student_reaction, action, concept, kg)
        
        # (8) 更新 L5
        tracer.update(concept['id'], analysis)
        
        # (9) 更新 L3（写入答题记录等）
        long_memory.record_interaction(analysis)
        
        # (10) 决定下一步
        next_state = strategy.transition(session.current_state, analysis)
        
        # (11) 如果策略完成或需要切换：
        if strategy.is_terminal(next_state) or should_switch_strategy(analysis, context):
            strategy = select_strategy(next_concept, context)
        
        session.current_state = next_state
```

### 3.2 中断处理

```python
def handle_interrupt(session: TutoringSession, question: str, 
                     kg: KnowledgeGraph, tracer: KnowledgeTracer):
    """
    学生在任何状态都可以打断。
    """
    
    # (1) 保存当前状态
    checkpoint = {
        'session_id': session.id,
        'current_concept': session.current_concept_id,
        'strategy_state': session.current_state,
        'position_in_plan': session.position_in_plan,
        'last_action': session.last_action,
        'pending_question': session.pending_question,  # 教师端未完成的提问
        'timestamp': datetime.now(),
    }
    session.state = 'INTERRUPTED'
    session.interrupt_checkpoint = checkpoint
    
    # (2) 理解学生的打断
    context = tracer.get_teaching_context(session.student_id, session.subject_id)
    
    # (3) 分类打断类型
    intent = classify_interrupt_intent(question, session, kg)
    # intent ∈ {
    #   'concept_question': "这个概念什么意思？",
    #   'process_question': "这一步怎么推导过来的？",
    #   'prereq_gap':       "用到的东西我前提到没学过",
    #   'example_request':  "能举个例子吗？",
    #   'pace_complaint':   "太快了/太慢了",
    #   'distraction':      "与当前主题无关",
    #   'cognitive_overload': "我脑子满了"
    # }
    
    # (4) 根据不同意图做不同处理
    if intent == 'prereq_gap':
        # 检测真的前置缺失 → 插入 mini 复习
        missing_prereq = detect_prereq_gap(question, session, kg, context)
        if missing_prereq:
            return InterruptResponse(
                type='prereq_tutorial',
                content=f"这个问题用到了{missing_prereq}，我们先花3分钟回顾一下这个。",
                resume_after='this_subtopic',
                checkpoint=checkpoint,
            )
    
    elif intent == 'cognitive_overload':
        return InterruptResponse(
            type='pace_adjustment',
            content="我们慢一点。这个部分可以分解为三个小步骤...",
            adjusted_pace='slower',
            break_suggestion=f"也可以休息5分钟，当前进度已保存。",
            checkpoint=checkpoint,
        )
    
    elif intent == 'distraction':
        return InterruptResponse(
            type='redirect',
            content=f"这个问题和当前内容关系不大。我们先完成这个部分，如果你还想问这个问题，我们可以之后聊。",
            checkpoint=checkpoint,
        )
    
    # (5) 给出上下文感知的回答
    return InterruptResponse(
        type='context_aware_answer',
        content=generate_context_aware_answer(question, session, kg, context),
        checkpoint=checkpoint,
        resume_prompt=f"我们刚才在讲{concept.name}的{last_action.description}，继续？",
    )

def resume_from_interrupt(session: TutoringSession, resume: bool):
    """恢复被中断的会话"""
    if not resume:
        return
    checkpoint = session.interrupt_checkpoint
    # 恢复状态
    session.current_concept_id = checkpoint['current_concept']
    session.current_state = checkpoint['strategy_state']
    session.position_in_plan = checkpoint['position_in_plan']
    # 从断点继续
```

### 3.3 适应节奏

```python
class PaceController:
    """
    动态调整教学节奏
    
    信号 "太慢了":
    - 学生频繁说"知道了"/跳过练习
    - 答题速度快且正确率高 (> baseline * 0.7, accuracy > 0.9)
    - 动作: skip_threshold ↑, 概念粒度 ↑
    
    信号 "太快了":
    - 认知负荷 > 0.7
    - 连续错误
    - 频繁中断提问
    - 动作: 降低概念粒度, 多插入检查点, 增加类比
    """
    
    def adjust(self, signals: PaceSignals) -> PaceAdjustment:
        pass
```

---

## 4. 教学动作类型

```python
TeachingAction = Union[
    ExplainAction,        # 讲解一段内容（文本 + 图表 + 公式）
    AskQuestionAction,    # 提问（单选/填空/简答/解释）
    ShowExampleAction,    # 展示一个例子
    ShowCounterExample,   # 展示一个反例
    GiveExerciseAction,   # 布置练习
    RequestExplanation,   # 要求学生用自己的话解释（费曼）
    ProvideHintAction,    # 给出提示
    RevealAnswerAction,   # 揭示正确答案
    ReviewAction,         # 复习前置或多天前的概念
    CheckpointAction,     # 阶段性总结
    ReflectionAction,     # 要求学生反思自己的学习
    BreakSuggestion,      # 建议休息
    PaceFeedbackAction,   # 询问学生对节奏的感受
]

# 每个 Action 都有:
# - content: str      实际展示给学生的内容
# - metadata: 用于 L5 分析和 L3 记录的结构化数据
```

---

## 5. 与 L5 的闭环接口

```
     L5 推送                        L6 拉取
    ─────────                     ─────────
    teaching_context  ──────────→  决策循环
    认知负荷指数
    错误诊断结果
    知识状态快照
    
                                     │
    L5 更新 ←──────────────  学生反应分析结果
    tracer.update()               analyze_student_reaction()
    long_memory.record()             │
                                    
                                    ▼
                               L3 长期记忆更新
```

---

## 6. 实现路线

| 阶段 | 内容 | 预估 |
|------|------|------|
| Phase 1 | 降阶法 + 费曼法 状态机实现 + 策略选择规则引擎 | 1 周 |
| Phase 2 | 苏格拉底 + 类比桥接 + 实时决策循环 | 1 周 |
| Phase 3 | 项目驱动 + 间隔复习集成（联调 L3）+ 中断处理 | 0.5 周 |

总计：约 2.5 周
