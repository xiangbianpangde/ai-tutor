# L5 学习者建模

> 职责：对学生认知状态进行实时建模 —— 知识掌握度、错误类型诊断、认知负荷估计、学习者画像演化  
> 输入：学生答题记录、交互行为信号  
> 输出：每个概念的掌握概率、错误类型标签、认知负荷指数、多维学习者画像

---

## 1. 双模型知识状态追踪

### 1.1 DKT（深度学习知识追踪）

用于**预测**学生下一个交互点的正确率。

```python
# 输入特征
DKTInput = {
    'student_id': str,
    'concept_id': str,
    'interaction_history': List[{
        'concept_id': str,
        'correct': bool,
        'response_time_sec': float,
        'hint_used': bool,
        'attempt_number': int,
        'timestamp': datetime,
    }],
    'skill_tags': List[str],          # 该题涉及的知识标签
    'question_difficulty': float,     # 0~1
}

# 输出
DKTOutput = {
    'concept_id': str,
    'mastery_prob': float,            # 掌握概率 0~1
    'uncertainty': float,             # 模型不确定性 0~1
    'predicted_correctness': float,   # 预测下一题正确率
    'next_review_at': datetime,       # 最佳复习时间（基于当前衰减速率）
    'predicted_error_type': Optional[str],  # 预测下次最可能的错误类型
}

# 模型架构（简化）
# Embedding(concept_id) + LSTM(interaction_history) → Dense(128) → Dense(1, sigmoid)
# 训练数据：同科目其他学生的历史交互序列
```

### 1.2 BKT（贝叶斯知识追踪）

用于**解释**学生对特定概念的掌握状态。每个概念维护 4 个可解释参数：

```python
BKTParams = {
    'concept_id': str,
    'p_learn': float,          # 从"不会"到"学会"的转移概率
    'p_guess': float,          # 不会但猜对的概率
    'p_slip': float,           # 会了但粗心错的概率
    'p_init': float,           # 初始已掌握概率（先验）
    'p_mastery': float,        # 当前掌握概率（后验，动态更新）
    'last_updated': datetime,
    'n_observations': int,     # 观测次数
}

def update_bkt(params: BKTParams, observation: bool) -> BKTParams:
    """
    贝叶斯更新:
    
    当 observation = True (答对):
        p_mastery_new = 
            p_mastery * (1 - p_slip) /
            [p_mastery * (1 - p_slip) + (1 - p_mastery) * p_guess]
    
    当 observation = False (答错):
        p_mastery_new = 
            p_mastery * p_slip /
            [p_mastery * p_slip + (1 - p_mastery) * (1 - p_guess)]
    
    然后应用学习转移:
        p_mastery_new += (1 - p_mastery_new) * p_learn  # 有概率从"不会"学到"会"
    """
```

### 1.3 双模型协作

```python
class KnowledgeTracer:
    """
    DKT 负责: "这个学生接下来会答对吗？" → 实时预测
    BKT 负责: "这个学生对极限ε-δ定义的掌握概率是多少？为什么？" → 可解释性
    
    协作规则:
    - 当 BKT 的 p_mastery 和 DKT 的 mastery_prob 偏差 > 0.2 时:
      → 标记为"异常模式"，触发诊断流程
      → 可能原因: 学生在猜、题目有歧义、学习转移发生了但模型没捕捉到
    - 当 uncertainty > 0.3 时:
      → DKT 对这个预测没有信心，回退到 BKT 的保守估计
    - BKT 参数（p_learn, p_guess, p_slip）可以从 DKT 的隐状态中推断，
      实现冷启动（新概念不需要历史数据）
    """
```

---

## 2. 错误类型诊断

### 2.1 错误分类体系

```python
ErrorType = Literal[
    'concept_confusion',      # 概念混淆：把 A 当成 B
    'symbol_mistake',         # 符号错误：∀∃ 用反、± 号错
    'logic_gap',              # 逻辑漏洞：不会推导连接步骤
    'syntax_error',           # 语法错误：格式、书写错误
    'prereq_gap',             # 前置知识缺失：根本不懂要用到的前置概念
    'overgeneralization',     # 过度泛化：把只在特例适用的规律推广到全体
    'arithmetic_mistake',     # 计算错误
    'reading_error',          # 阅读错误：理解错题意
    'careless',               # 粗心：会但失误
    'blank',                  # 空白：完全不会
]

ErrorDiagnosis = {
    'error_type': ErrorType,
    'root_concept_id': str,         # 根本原因概念
    'surface_concept_id': str,      # 表面出错的概念
    'confidence': float,            # 诊断置信度
    'evidence': List[str],          # 证据（学生回答中的关键词/模式）
    'remediation_suggestion': str,  # 纠正建议
}
```

### 2.2 诊断规则引擎

```python
# 错误模式匹配表
ERROR_PATTERNS = {
    'symbol_mistake': [
        r'∀.*∃.*反',           # 量词用反
        r'ε.*δ.*顺序',          # ε-δ 顺序错
        r'[+-]\s*[*/+-]',      # 符号连用错误
        r'=\s*≠',              # 等号不等号混淆
    ],
    'concept_confusion': [
        # 命名混淆：极限 vs 连续 vs 可导
        # LLM 判定比正则更准确
    ],
    'prereq_gap': [
        # 检测：学生答案中引用了未在 session 中学习过的概念
        # 或引用的概念其 BKT p_mastery < 0.4
    ],
    'overgeneralization': [
        # 模式：用了只在低维成立的公式在高维场景
        # 例如：把一元可导的求导法则直接用于多元偏导
    ],
}

def diagnose_error(
    student_answer: str, 
    model_answer: str, 
    concept_id: str, 
    kg: KnowledgeGraph
) -> ErrorDiagnosis:
    """
    1. 正则匹配 ERROR_PATTERNS → 初步分类
    2. LLM 深度分析: "学生的错误模式是什么？根本原因可能是哪个前置概念？"
    3. KG 验证: 诊断出的 root_concept 是否真的是 surface_concept 的前置
    4. BKT 交叉验证: root_concept 的 p_mastery 是否确实低
    5. 返回结构化诊断
    """
```

### 2.3 诊断输出示例

```
学生答错了一道多元函数极值题，写道：
"令 f'(x,y)=0，解得驻点..."

诊断结果:
  error_type: concept_confusion
  surface_concept: 多元函数极值
  root_concept: 偏导数定义
  explanation: |
    学生使用了 f'(x,y) 的记号，但这是错误的。
    正确的做法是令 ∂f/∂x = 0 且 ∂f/∂y = 0。
    这说明学生对偏导数的记号还没有真正掌握，
    仍然延续了一元函数的思维习惯。
  remediation: |
    建议先回顾偏导数的定义和记号，
    做 2 道偏导数计算题确认掌握，
    然后再回到极值问题。
```

---

## 3. 认知负荷实时估计

### 3.1 行为信号采集

```python
CognitiveLoadSignals = {
    # 来自交互
    'response_latency': float,          # 当前答题耗时 / 该学生基线答题耗时
    'backtrack_count': int,             # 本次会话中回看前置知识的次数
    'interrupt_count': int,             # 主动打断提问次数
    'answer_revision_rate': float,      # 提交前修改答案的概率
    'hint_request_rate': float,         # 请求提示的概率
    
    # 来自文本分析
    'answer_length_variance': float,    # 答案长度波动（不确定时答得短或乱）
    'question_rephrasing_rate': float,  # "我不太懂，能换个说法吗"的触发率
    
    # 来自概念维度
    'current_concept_cognitive_load': float,  # 当前概念的预估认知负荷（来自L4）
    'prereq_mastery_min': float,        # 前置概念中最差的掌握度
}

def estimate_cognitive_load(signals: CognitiveLoadSignals) -> float:
    """
    组合多个信号，输出 0~1 的认知负荷指数
    0.0 = 轻松，0.5 = 最佳挑战，1.0 = 过载
    
    公式（可调权重）:
    CL = w1 * response_latency_ratio + 
         w2 * backtrack_frequency + 
         w3 * interrupt_frequency +
         w4 * concept_difficulty * (1 - prereq_mastery_min)
    
    阈值:
    CL < 0.3 → 太简单，加速或提高难度
    0.3 ≤ CL < 0.7 → 最佳学习区（Zone of Proximal Development）
    CL ≥ 0.7 → 过载，触发降级策略
    """
```

### 3.2 自适应阈值

```python
# 不同学生对"过载"的敏感度不同
# 初始使用默认阈值，随时间个性化

LearnerCognitiveThreshold = {
    'overload_threshold': 0.7,          # 初始默认
    'personalization_data': List[{
        'cognitive_load': float,
        'subsequent_correctness': float,  # 该负荷下的后续正确率
    }],
    'adjusted_threshold': float,        # 个性化调整后的阈值
}

def personalize_threshold(history: List) -> float:
    """
    拟合: 找出"正确率开始明显下降"的认知负荷拐点
    将该拐点设为该学生的新 overload_threshold
    """
```

---

## 4. 学习者画像

### 4.1 画面维度

```python
LearnerProfile = {
    'user_id': str,
    'created_at': datetime,
    'last_updated': datetime,
    'total_study_hours': float,
    
    # === 认知特征 ===
    'cognitive': {
        'working_memory_span': int,          # 一次能处理几个概念块（2~9）
        'abstract_tolerance': float,         # 抽象内容接受度 0~1
        'transfer_ability': float,           # 举一反三能力 0~1
        'analogical_reasoning': float,       # 类比推理能力 0~1
        'mathematical_maturity': float,      # 数学成熟度 0~1
        'preferred_modality': {              # 随时间变化的多模态偏好
            'text': float,
            'visual': float,
            'interactive': float,
            'audio': float,
        },
        'information_processing_speed': float,  # 相对速度，1.0=平均
    },
    
    # === 元认知特征 ===
    'metacognitive': {
        'self_assessment_accuracy': float,   # 自评准确度（自评 vs 实际成绩）
        'help_seeking_tendency': float,      # 求助倾向 0(独立)~1(频繁)
        'frustration_threshold': int,        # 连续错几道题会崩溃
        'confidence_calibration': float,     # 自信校准度（-1=自卑，0=准确，+1=自负）
        'growth_mindset_score': float,       # 成长性思维得分
    },
    
    # === 行为特征 ===
    'behavioral': {
        'peak_learning_hours': List[int],    # 最佳学习时间段（小时）
        'optimal_session_length_min': int,   # 最佳单次时长
        'attention_decay_rate': float,       # 注意力下降速率 /min
        'streak_momentum': float,            # 连续学习动力 0~1
        'review_compliance_rate': float,     # 复习遵从度
        'preferred_pace': Literal['fast', 'moderate', 'thorough'],
    },
    
    # === 情感特征 ===
    'affective': {
        'subjects': Dict[str, {             # 按科目
            'affinity': float,              # 情感倾向 -1(厌恶)~+1(喜欢)
            'anxiety_level': float,         # 焦虑程度 0~1
            'self_efficacy': float,         # 自我效能感 0~1
        }],
    },
    
    # === 知识特征（聚合）===
    'knowledge': {
        'total_concepts_mastered': int,
        'avg_mastery': float,
        'weakest_domains': List[str],       # 最薄弱的知识域
        'strongest_domains': List[str],
    },
}
```

### 4.2 画像演化机制

```python
class ProfileEvolver:
    """
    画像不是静态问卷，是从数据中逐步推断的人格模型。
    
    推断规则示例:
    
    working_memory_span:
      - 如果在一次教学片断中，连续 3 个概念后正确率明显下降
        → working_memory_span 可能是 3
      - 如果连续 5 个概念后仍保持高正确率
        → working_memory_span ≥ 5
    
    abstract_tolerance:
      - 对 abstract_level > 0.7 的概念，正确率 > 80%
        → abstract_tolerance ↑
      - 对抽象概念频繁求助/回看
        → abstract_tolerance ↓
    
    self_assessment_accuracy:
      - 每次 checkpoint 时学生自评 vs 系统实际评分
      - 自评:"我觉得掌握度70%" vs 系统:BKT p_mastery=0.45
        → self_assessment_accuracy 调整
      - 长期是自负(overconfident) → 增加费曼检测频率
    
    help_seeking_tendency:
      - 遇到难题时主动求问 vs 自己尝试
      - 求问频率高但题目简单 → 不自信 → 减少直接提示，增加鼓励
      - 从不求问但正确率低 → 太独立 → 主动探测是否需要帮助
    
    frustration_threshold:
      - 连续 N 道题错误后，接下来 3 道简单题也错
        → frustration_threshold = N
      - 触发后自动插入"休息建议"或切换简单内容
    """
```

---

## 5. 知识状态快照

```python
KnowledgeSnapshot = {
    'user_id': str,
    'subject_id': str,
    'timestamp': datetime,
    'concepts': Dict[str, {
        'bkt_mastery': float,
        'dkt_mastery': float,
        'n_correct': int,
        'n_incorrect': int,
        'last_error_type': Optional[str],
        'last_interaction_at': datetime,
        'forgetting_rate_lambda': float,    # 个人衰减速率
        'review_streak': int,               # 连续正确答对次数
    }],
    'global_stats': {
        'total_concepts': int,
        'mastered_count': int,              # mastery > 0.85
        'learning_count': int,              # 0.4 < mastery < 0.85
        'unknown_count': int,               # mastery < 0.4
        'avg_mastery': float,
    },
}
```

---

## 6. 与 L6 的接口

L5 为 L6 提供：

```python
TeachingContext = {
    'current_focus': {                     # 当前教学焦点
        'concept_id': str,
        'position_in_plan': int,
        'estimated_time_remaining_min': int,
    },
    'mastery_map': Dict[str, float],       # 当前科目所有概念的掌握度
    'cognitive_load': float,               # 实时认知负荷
    'error_history': List[ErrorDiagnosis], # 本次会话的错误记录
    'learner_profile': LearnerProfile,     # 完整画像
    'weak_points': List[str],              # 当前需要额外关注的薄弱点
}
```

---

## 7. 实现路线

| 阶段 | 内容 | 预估 |
|------|------|------|
| Phase 1 | BKT 实现 + 基本错误分类（规则版） | 1 周 |
| Phase 2 | 认知负荷估计 + 画像骨架（cold-start 默认值） | 0.5 周 |
| Phase 3 | DKT 集成（需要训练数据，初期用 BKT 兜底） | 1 周 |
| Phase 4 | 画像演化引擎 + 自适应阈值 | 0.5 周 |

总计：约 3 周（与 L3 长期记忆并行开发）
