# 学习者画像 Schema

> 完整定义 L5 LearnerProfile 的存储与更新语义

---

## 一、画像 JSON Schema

```json
{
  "user_id": "yhn",
  "version": 3,
  "created_at": "2026-04-01T08:00:00Z",
  "last_updated": "2026-05-19T22:30:00Z",
  "data_points": 1247,
  "total_study_hours": 87.5,

  "cognitive": {
    "working_memory_span": 5,
    "abstract_tolerance": 0.61,
    "transfer_ability": 0.52,
    "analogical_reasoning": 0.58,
    "mathematical_maturity": 0.45,
    "preferred_modality": {
      "text": 0.25,
      "visual": 0.40,
      "interactive": 0.25,
      "audio": 0.10
    },
    "information_processing_speed": 1.15
  },

  "metacognitive": {
    "self_assessment_accuracy": 0.68,
    "help_seeking_tendency": 0.45,
    "frustration_threshold": 4,
    "confidence_calibration": 0.12,
    "growth_mindset_score": 0.70
  },

  "behavioral": {
    "peak_learning_hours": [8, 10, 15, 16],
    "optimal_session_length_min": 55,
    "attention_decay_rate": 0.018,
    "streak_momentum": 0.75,
    "review_compliance_rate": 0.82,
    "preferred_pace": "fast"
  },

  "affective": {
    "subjects": {
      "gaoshu-v8": {
        "affinity": 0.3,
        "anxiety_level": 0.35,
        "self_efficacy": 0.65
      },
      "linear_algebra": {
        "affinity": 0.6,
        "anxiety_level": 0.20,
        "self_efficacy": 0.78
      }
    }
  },

  "knowledge": {
    "total_concepts_mastered": 234,
    "total_subjects_completed": 2,
    "avg_mastery": 0.71,
    "weakest_domains": ["空间解析几何", "级数敛散性判别"],
    "strongest_domains": ["一元微积分", "矩阵运算", "向量代数"]
  },

  "evolution_log": [
    {
      "timestamp": "2026-04-15T10:00:00Z",
      "field": "working_memory_span",
      "old_value": 4,
      "new_value": 5,
      "evidence": "连续4次教学片断中正确率保持>85%，峰值处理6概念"
    },
    {
      "timestamp": "2026-05-10T14:30:00Z",
      "field": "abstract_tolerance",
      "old_value": 0.48,
      "new_value": 0.53,
      "evidence": "对abstract_level>0.7概念的正确率从55%提升到72%"
    }
  ]
}
```

---

## 二、Update Semantics

### 增量更新规则

| 字段 | 更新触发时机 | 更新公式 | 最小数据点要求 |
|------|-------------|----------|--------------|
| `abstract_tolerance` | 每个教学片断结束 | EMA(α=0.1, new_score) | ≥5 个高抽象概念交互 |
| `transfer_ability` | 每次做迁移题 | EMA(α=0.1) | ≥10 次迁移评估 |
| `working_memory_span` | 每个教学片断 | 滑动窗口峰值模式 | ≥3 个教学片断 |
| `self_assessment_accuracy` | 每次 checkpoint | EMA(α=0.2) | ≥5 次自评 |
| `frustration_threshold` | 每次连续错误序列 | 窗口最小值 | ≥3 次崩溃事件 |
| `preferred_modality` | 每次格式选择行为 | 加权频率 | ≥20 次选择 |
| `attention_decay_rate` | 每次会话结束 | 线性回归斜率 | ≥5 个会话 |
| `peak_learning_hours` | 每次会话 | 时间分桶+计数 | ≥20 个会话 |

### 未满数据点阈值时的冷启动值

```python
COLD_START_DEFAULTS = {
    "working_memory_span": 5,        # 中等
    "abstract_tolerance": 0.5,       # 中性
    "transfer_ability": 0.4,         # 保守
    "self_assessment_accuracy": 0.6, # 略微乐观
    "frustration_threshold": 3,      # 中等耐受
    "attention_decay_rate": 0.02,    # 平均
    "preferred_pace": "moderate",
    "preferred_modality": {"text": 0.4, "visual": 0.3, "interactive": 0.2, "audio": 0.1},
}
```

### 存储

- **热路径**: Redis `user:{user_id}:profile` (JSON, TTL 1h, 每次更新时 RENEW)
- **持久层**: SQLite/Postgres `learner_profiles` 表
- **同步**: 每 5 分钟或每次会话结束时 Redis → DB 写入
- **读取**: 先 Redis，miss 则 DB 加载后回写 Redis
