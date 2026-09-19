# L3 长期记忆引擎

> 职责：对抗遗忘、构建知识互联网络、智能化复习调度  
> 输入：L5 的知识状态快照、学生交互历史  
> 输出：个性化复习计划、知识网络可视化、最优复习时机预测

---

## 1. 个性化遗忘曲线

### 1.1 理论模型

经典艾宾浩斯曲线是群体平均，不适用于个体。L3 为每个用户的每个概念拟合**个人遗忘曲线**。

```python
# 指数衰减模型
# R(t) = R_0 * e^(-λt)
# 其中:
#   R(t): t 天后的记忆保留率
#   R_0: 初始学习后的记忆保留率（通常 ≈ 1.0）
#   λ:   衰减速率（因人而异、因概念而异）
#   t:   自上次复习后的天数
```

### 1.2 数据采集与拟合

```python
class ForgettingCurveEstimator:
    """
    对每个 (user_id, concept_id) 维护独立的数据点和衰减参数。
    """
    
    def collect_data_point(self, user_id: str, concept_id: str, 
                           days_since_last_review: int, 
                           recall_accuracy: float):
        """
        每次复习/测试时收集一个数据点:
        (days_since_last_review, recall_accuracy)
        
        例如:
        (1, 0.95)   # 学完1天后复习，正确率95%
        (3, 0.82)   # 3天后复习，正确率82%
        (7, 0.61)   # 7天后复习，正确率61%
        (14, 0.34)  # 14天后复习，正确率34%
        """
    
    def fit_lambda(self, user_id: str, concept_id: str) -> float:
        """
        用最小二乘法拟合:
        log(R(t)) = log(R_0) - λ * t
        → λ = -slope
        
        当数据点 < 3 时，使用全局默认 λ_global（从群体数据估计）
        当数据点 ≥ 5 时，使用个性化 λ_personal
        当数据点在 3~5 之间时，使用加权混合:
        λ_blended = w * λ_personal + (1-w) * λ_global
        w = min(n_data_points / 10, 1.0)
        """
    
    def predict_recall(self, user_id: str, concept_id: str, days: int) -> float:
        """
        预测 t 天后该概念的回忆率
        """
        lam = self.fit_lambda(user_id, concept_id)
        return math.exp(-lam * days)
    
    def next_review_at(self, user_id: str, concept_id: str, 
                       recall_threshold: float = 0.70) -> datetime:
        """
        计算回忆率降到阈值以下的时间 → 建议的复习时间
        """
        lam = self.fit_lambda(user_id, concept_id)
        days_to_threshold = -math.log(recall_threshold) / lam
        return datetime.now() + timedelta(days=days_to_threshold)
```

### 1.3 冷启动策略

```python
# 新用户/新概念没有历史数据时，使用以下默认值:
DEFAULT_FORGETTING_PARAMS = {
    'easy_concept_lambda': 0.03,       # 简单概念（abstract_level < 0.3）
    'medium_concept_lambda': 0.05,     # 中等概念
    'hard_concept_lambda': 0.10,       # 难概念（abstract_level > 0.7）
    
    # 初始复习间隔建议（天）
    'initial_intervals': [1, 3, 7, 14, 30, 60],
    
    # 概念难度维度修正系数
    'prereq_count_penalty': 0.01,      # 前置越多，忘得越快
    'abstract_level_penalty': 0.02,    # 越抽象，忘得越快
    'formula_density_penalty': 0.005,  # 公式越密，忘得越快
}
```

---

## 2. 知识互联网络

### 2.1 概念

这不是 L4 的知识图谱（客观的学科知识结构），而是**学生脑内的实际知识网络**：

```python
StudentKnowledgeNetwork = {
    'user_id': str,
    'subject_id': str,
    
    # 节点：概念（带掌握概率）
    'nodes': Dict[str, StudentConceptNode],
    
    # 边：学生发现的关联
    'edges': List[StudentDiscoveredEdge],
    
    # 网络指标
    'metrics': {
        'network_density': float,       # 连接密度
        'avg_path_length': float,       # 平均最短路径
        'modularity': float,            # 模块化程度（学生是否把相关概念聚类）
        'isolated_nodes': List[str],    # 孤岛概念（会但不会用）
    },
}

StudentConceptNode = {
    'concept_id': str,
    'mastery': float,                   # L5 的 BKT p_mastery
    'importances': {                    # 学生对概念的主观重要性
        'assigned_by_student': float,   # 学生自己打的（可选）
        'inferred_from_review': float,  # 从复习行为推断的
    },
    'affective_tag': Literal['like', 'neutral', 'dislike', 'fear'],
    'first_learned_at': datetime,
    'n_reviews': int,
}

StudentDiscoveredEdge = {
    'from_id': str,
    'to_id': str,
    'relation': str,                    # "类比"、"对立"、"互补"、"推理链"等
    'discovered_by': Literal['student', 'system', 'reinforced'],
    'strength': float,                  # 学生对这个关联的牢固程度
    'first_observed_at': datetime,
    'n_reinforcements': int,
}
```

### 2.2 连接发现与强化

```python
def detect_student_connections(
    student_answer: str,
    current_concept: Concept,
    kg: KnowledgeGraph,
    network: StudentKnowledgeNetwork
) -> List[StudentDiscoveredEdge]:
    """
    分析学生的回答，检测是否展现了概念间的关联:
    
    例1: "多元极限就像一元极限，只是多考虑几个方向"
    → detected_edge: (multivariable_limit, single_variable_limit, "类比")
    
    例2: "先用导数定义求出导数，再代入泰勒展开"
    → detected_edge: (derivative_definition, taylor_expansion, "推理链")
    
    检测方法:
    - Entity Linking: 在回答中识别概念名称
    - 共现分析: 在同一上下文中出现的概念对
    - LLM 判定: 学生是否在建立连接
    
    发现后 → 加入 network.edges
    下次复习 concept_A 时 → 自动带入 concept_B 做联合复习
    """
```

### 2.3 跨科目知识关联

```python
CrossSubjectConnection = {
    'concept_a': {'id': str, 'subject': str},
    'concept_b': {'id': str, 'subject': str},
    'connection_type': Literal['same_math', 'application', 'prerequisite', 'analogy'],
    'discovered_at': datetime,
    'utility_score': float,    # 这个关联的实用性评分
}

# 例: 
# 高数·导数 <=> 物理·速度 → 应用(application)
# 高数·矩阵 <=> 线代·线性变换 → 同数学(same_math)
# 复习高数导数时 → 自动引入物理速度题目 → 加深理解
```

---

## 3. 多因子复习调度器

### 3.1 复习优先级公式

```python
def compute_review_priority(user_id: str, concept_id: str, 
                            context: dict) -> float:
    """
    priority = Σ w_i * factor_i
    
    w1 * urgency +            # 遗忘曲线逼近阈值
    w2 * prereq_importance +  # 是当前学习的前置吗
    w3 * exam_weight +        # 考试临近加权（如有设置）
    w4 * downstream_impact +  # 这概念掌握影响多少下游
    w5 * difficulty_weight +  # 困难概念优先
    w6 * student_aversion     # 学生对这概念的情感（厌恶的要更频繁复习）
    """
    
    factors = {}
    
    # Factor 1: 遗忘紧迫度
    predicted_recall = forgetting_curve.predict_recall(user_id, concept_id, 
                                                       days_since_last_review)
    factors['urgency'] = 1.0 - predicted_recall  # 越低 → 越紧迫
    
    # Factor 2: 当前教学的前置重要性
    if context.get('current_focus_concept'):
        prereqs = kg.get_prerequisites(context['current_focus_concept'], depth=3)
        if concept_id in prereqs:
            factors['prereq_importance'] = 1.0 / prereqs.index(concept_id)
    
    # Factor 3: 下游影响（掌握这个概念影响多少后续学习）
    downstream = kg.get_downstream_concepts(concept_id, depth=2)
    factors['downstream_impact'] = min(len(downstream) / 10, 1.0)
    
    # Factor 4: 困难度
    concept = kg.get_concept(concept_id)
    factors['difficulty_weight'] = concept['difficulty']['cognitive_load_estimate']
    
    # Factor 5: 学生情感（厌恶的需要更多复习来克服）
    profile = get_learner_profile(user_id)
    if concept_id in profile.affective.concept_tags:
        if profile.affective.concept_tags[concept_id] == 'dislike':
            factors['student_aversion'] = 0.3  # 增加优先级
    
    # 加权求和
    weights = {'urgency': 3.0, 'prereq_importance': 2.5, 'exam_weight': 3.0,
               'downstream_impact': 1.5, 'difficulty_weight': 1.0, 'student_aversion': 1.0}
    
    return sum(weights[k] * factors.get(k, 0) for k in weights)
```

### 3.2 每日复习计划生成

```python
def generate_daily_review_plan(user_id: str, subject_id: str, 
                               available_time_min: int) -> DailyReviewPlan:
    """
    生成今日的复习微课程。
    """
    
    # (1) 收集所有待复习概念
    all_concepts = get_subject_concepts(subject_id)
    knowledge_state = get_knowledge_snapshot(user_id, subject_id)
    
    # (2) 计算每个概念的复习优先级
    priorities = {
        cid: compute_review_priority(user_id, cid, {})
        for cid in all_concepts
    }
    
    # (3) 排序、过滤
    candidates = [
        (cid, pri) for cid, pri in priorities.items()
        if pri > 0.3  # 过滤不太紧迫的
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    
    # (4) 分配时间（每个复习片断预估耗时 → 从历史数据中学习）
    plan_sections = []
    time_budget = available_time_min
    
    for concept_id, priority in candidates:
        est_time = estimate_review_time(user_id, concept_id)
        if est_time <= time_budget:
            plan_sections.append({
                'concept_id': concept_id,
                'priority': priority,
                'predicted_recall': forgetting_curve.predict_recall(user_id, concept_id, 
                                                                     days_since_last_review),
                'estimated_minutes': est_time,
                'review_mode': select_review_mode(concept_id, knowledge_state),
                'linked_concepts': get_student_connections(concept_id),  # 从知识网络
            })
            time_budget -= est_time
    
    # (5) 排序：先紧急复习，再常规复习，最后"有趣"复习
    plan_sections = interleave_review_order(plan_sections)
    # 交错排序原则: [紧迫A] → [轻松B] → [紧迫C] → [有趣D] → ...
    # 避免连续复习多个困难概念导致认知过载
    
    return DailyReviewPlan(
        user_id=user_id,
        subject_id=subject_id,
        date=date.today(),
        sections=plan_sections,
        total_estimated_min=available_time_min - time_budget,
        tips=[
            "今天的复习包括 2 个易忘概念（建议早上做）",
            "泰勒展开已经10天没复习了，预测正确率已降到53%",
            "先做思维导图完成全局回顾，再做重点概念深入",
        ],
    )
```

### 3.3 复习模式自动选择

```python
def select_review_mode(concept_id: str, 
                       knowledge_state: KnowledgeSnapshot) -> ReviewMode:
    """
    根据掌握度和错误历史选择最佳复习模式:
    
    quick_quiz:       mastery > 0.7 且最近无错误 → 3道快速题
    concept_map:      mastery 0.4~0.7 → 让学生画出关系图
    teach_back:       mastery < 0.4 → 费曼式"教给10岁小孩"
    error_revisit:    有未解决的错误类型 → 重做之前的错题变体
    """
    
    state = knowledge_state.concepts.get(concept_id)
    
    if state.last_error_type and not state.error_resolved:
        return 'error_revisit'
    
    if state.mastery < 0.4:
        return 'teach_back'
    
    if 0.4 <= state.mastery <= 0.7:
        return 'concept_map'
    
    return 'quick_quiz'
```

### 3.4 复习结果反馈

```python
def update_after_review(user_id: str, concept_id: str, 
                        review_result: ReviewResult):
    """
    每次复习后更新:
    1. 遗忘曲线数据点 +1
    2. 重新拟合 λ
    3. 更新下一次复习推荐时间
    4. 如果正确 → review_streak +1, λ 微调（衰减变慢）
       如果错误 → review_streak = 0, λ 微调（衰减变快）
    """
    
    # 写入数据点
    forgetting_curve.collect_data_point(
        user_id, concept_id,
        days_since_last_review=review_result.days_since_last_review,
        recall_accuracy=review_result.accuracy,
    )
    
    # 更新学生知识网络
    network = get_student_network(user_id, review_result.subject_id)
    for edge in review_result.detected_connections:
        network.reinforce_edge(edge, strength_delta=0.1)
    
    # 更新 L5 知识状态（可选：复习检测也可以写入 BKT 更新）
    if review_result.mode == 'quick_quiz' and review_result.accuracy < 0.6:
        # 快速测验结果差 → 该概念可能需要回 L5 重新学习
        flag_for_relearning(user_id, concept_id)
```

---

## 4. 与 L5/L6 的接口

### 4.1 L3 → L6：推送复习建议

```python
# L6 的教学决策循环中:
review_suggestion = l3.get_review_suggestion(student_id, current_concept_id)
# 返回:
# {
#   'should_review': bool,
#   'target_concepts': List[str],    # 需要复习的概念 ID
#   'urgency': float,
#   'suggested_mode': str,           # 复习模式
#   'context': str,                  # "插入这段复习: 偏导数定义(上次复习7天前, 预测正确率61%)"
# }
```

### 4.2 L5 → L3：写入交互记录

```python
# L5 每次更新知识状态后:
l3.record_interaction({
    'user_id': user_id,
    'concept_id': concept_id,
    'action_type': 'learn' | 'practice' | 'quiz' | 'review',
    'correctness': float,
    'timestamp': datetime.now(),
    'error_type': Optional[str],
})
```

---

## 5. 复习数据存储

```python
# SQLite Schema (Postgres 兼容)
CREATE TABLE review_history (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    concept_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    review_date DATE NOT NULL,
    days_since_last INT NOT NULL,
    accuracy FLOAT NOT NULL,
    review_mode TEXT NOT NULL,
    error_types TEXT,  -- JSON array
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE forgetting_curves (
    user_id TEXT NOT NULL,
    concept_id TEXT NOT NULL,
    lambda FLOAT NOT NULL,           -- 拟合衰减速率
    r_squared FLOAT,                 -- 拟合优度
    n_data_points INT DEFAULT 0,
    last_review_at TIMESTAMP,
    next_review_at TIMESTAMP,
    review_streak INT DEFAULT 0,
    PRIMARY KEY (user_id, concept_id)
);

CREATE TABLE review_plans (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    plan_date DATE NOT NULL,
    plan_json TEXT NOT NULL,          -- 完整 DailyReviewPlan JSON
    completion_rate FLOAT DEFAULT 0,  -- 完成率
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. 实现路线

| 阶段 | 内容 | 预估 |
|------|------|------|
| Phase 1 | 遗忘曲线基本模型 + 标准艾宾浩斯间隔 | 3 天 |
| Phase 2 | 个性化 λ 拟合 + 复习优先级计算 | 3 天 |
| Phase 3 | 知识互联网络 + 每日复习计划生成 | 3 天 |
| Phase 4 | 跨科目知识关联 + 复习效果闭环 | 后续 |

总计：约 2 周（与 L5 并行开发）
