# 教学策略原语形式化定义

> 对 L6 六种策略原语的完整状态机、参数、触发条件和退出条件的形式化定义

---

## 1. 降阶法 (Reduction of Order)

### 形式定义

```
名称: ReductionOfOrder
类型: 教学策略（系统讲解+检测）
输入: KG, target_concept_id, mastery_map, params
输出: TeachingPath (有序教学片断列表)
```

### 状态机

```
                    ┌─────────┐
                    │  IDLE   │
                    └────┬────┘
                         │ start
                         ▼
                    ┌─────────┐
              ┌────▶│  PLAN   │────── 路径构建失败 ──▶ ERROR
              │     └────┬────┘
              │          │ plan_ready
              │          ▼
              │     ┌─────────┐
              │     │  INTRO  │
              │     └────┬────┘
              │          │ intro_done
              │          ▼
              │     ┌─────────┐
              │  ┌─▶│ EXPLAIN │◀──────────────┐
              │  │  └────┬────┘               │
              │  │       │ explain_done        │
              │  │       ▼                     │
              │  │  ┌─────────┐     mastery<0.4, attempt<2
              │  │  │  CHECK  │───────────────┘
              │  │  └────┬────┘
              │  │       │
              │  │       ├── mastery>0.85 ──▶ NEXT
              │  │       ├── mastery>0.6  ──▶ PRACTICE
              │  │       └── mastery<0.4, attempt≥2 ──▶ FLAG_DIFFICULT
              │  │                                         │
              │  │                    ┌────────────────────┘
              │  │                    ▼
              │  │               ┌──────────────┐
              │  │               │FLAG_DIFFICULT│──▶ switch_strategy
              │  │               └──────────────┘
              │  │
              │  │           ┌─────────┐
              │  └───────────│PRACTICE │
              │              └────┬────┘
              │                   │
              │    accuracy>0.8   ├──▶ NEXT
              │    accuracy<0.5   ├──▶ EXPLAIN (retry)
              │    0.5~0.8        └──▶ NEXT (with review flag)
              │
              │     ┌─────────┐
              └─────│  NEXT   │
                    └────┬────┘
                         │
              more_concepts├──▶ INTRO
              no_more      └──▶ SESSION_END
```

### 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `topology` | 'bottom_up' \| 'top_down' | 'bottom_up' | 教学方向 |
| `skip_threshold` | float (0~1) | 0.85 | mastery > 此值跳过 |
| `fast_mention_threshold` | float | 0.1 | 琐碎概念嵌入讲解的阈值 |
| `max_concepts_per_session` | int | 8 | 单次会话最多概念数 |
| `review_interleave_ratio` | float | 0.25 | 每 N 个新概念插入 1 个复习 |

### 触发条件

```
1. 新学科首次学习 (total_mastered < 20%)
2. preferred_pace == 'thorough'
3. 作为其他策略失败后的fallback
```

### 退出条件

```
1. 所有概念 mastery >= skip_threshold → SESSION_END
2. 外部策略切换信号（认知负荷过高）→ switch_strategy
3. 学生主动终止
```

---

## 2. 费曼法 (Feynman Technique)

### 状态机

```
                    ┌─────────┐
                    │  IDLE   │
                    └────┬────┘
                         │ start
                         ▼
                    ┌─────────┐
              ┌────▶│ PROMPT  │◀──────────────┐
              │     └────┬────┘               │
              │          │ prompt_sent         │
              │          ▼                     │
              │     ┌──────────────┐           │
              │     │WAIT_EXPLAIN  │           │
              │     └──────┬───────┘           │
              │            │ received          │
              │            ▼                   │
              │     ┌─────────┐                │
              │     │EVALUATE │                │
              │     └────┬────┘                │
              │          │                     │
              │   fidelity≥threshold ──▶ PASS ──▶ exit
              │   fidelity<threshold, attempt<max ──▶ GUIDED_CORRECTION
              │   fidelity<threshold, attempt≥max/2 ──▶ SIMPLIFY
              │   attempt≥max ──▶ MODEL ──▶ PROMPT
              │                        │
              │     ┌──────────────────┘
              │     ▼
              │ ┌──────────────────┐
              │ │GUIDED_CORRECTION │────▶ PROMPT (retry)
              │ └──────────────────┘
              │
              │        ┌──────────┐
              └────────│ SIMPLIFY │──▶ PROMPT (降级后retry)
                       └──────────┘
```

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `fidelity_threshold` | 0.80 | 关键要素覆盖率阈值 |
| `max_attempts` | 3 | 最多重试次数 |
| `guidance_level` | 2 | 提示详细程度 (0~3) |
| `simplify_trigger` | 2 | 第几次失败后降级 |

### 触发条件

```
1. self_assessment_accuracy < 0.5 (自评不准的学生)
2. concept.abstract_level > 0.7 (高抽象概念)
3. 上次该概念 mastery < 0.4 (检视是否真懂了)
```

---

## 3. 苏格拉底法 (Socratic Method)

### 状态机

```
                    ┌─────────┐
                    │  IDLE   │
                    └────┬────┘
                         │ start
                         ▼
                    ┌──────────┐
              ┌────▶│ QUESTION │◀──────────────┐
              │     └────┬─────┘               │
              │          │ asked                │
              │          ▼                      │
              │     ┌──────────────┐            │
              │     │WAIT_ANSWER   │            │
              │     └──────┬───────┘            │
              │            │ received           │
              │            ▼                    │
              │     ┌──────────────┐            │
              │     │ANALYZE_ANSWER│            │
              │     └──────┬───────┘            │
              │            │                    │
              │  correct_direction ──▶ QUESTION (下一层)
              │  close_but_off     ──▶ NUDGE ──▶ WAIT_ANSWER
              │  far_off           ──▶ HINT  ──▶ WAIT_ANSWER
              │  stuck(depth>max)  ──▶ REVEAL ──▶ REFLECT ──▶ exit
              │  wrong_answer      ──▶ NUDGE (深度1) / HINT (深度2+) ──▶ WAIT_ANSWER
```

### 触发条件

```
1. transfer_ability > 0.5 (有余力自己发现)
2. concept.mastery 在 0.3~0.6 (不是完全不会，也不是完全会)
3. 概念属于"推理/推导"型 (proves/computed_from 边较多)
```

---

## 4. 项目驱动法 (PBL)

### 状态机

```
                    ┌─────────┐
                    │  ASSIGN │
                    └────┬────┘
                         │ assigned
                         ▼
                    ┌─────────────┐    不合格
              ┌────▶│ PLAN_REVIEW │──────────▶ ASSIGN (re-scope)
              │     └──────┬──────┘
              │            │ approved
              │            ▼
              │     ┌────────────────┐
              │     │MILESTONE_CHECK │◀─────────┐
              │     └───────┬────────┘          │
              │             │                    │
              │    received ├──▶ FEEDBACK ──────┘ (next milestone)
              │             │
              │             └──▶ FINAL_REVIEW ──▶ exit
```

### 参数

| 参数 | 说明 |
|------|------|
| `milestones` | 里程碑列表，每个包含所需概念、交付物、预估时间 |
| `scaffolding_level` | 'full' \| 'partial' \| 'minimal' — 支架程度 |

### 触发条件

```
1. 该科目 mastered_count > 60% (有一定基础)
2. transfer_ability > 0.5
3. 学生请求"实际应用"场景
```

---

## 5. 类比桥接 (Analogical Bridging)

### 状态机

```
                    ┌───────────────────┐
                    │ESTABLISH_SOURCE   │
                    └────────┬──────────┘
                             │ source_confirmed
                             ▼
                    ┌───────────────────┐
                    │  DRAW_ANALOGY     │
                    └────────┬──────────┘
                             │ mapping_shown
                             ▼
                    ┌───────────────────┐
                    │  APPLY_ANALOGY    │
                    └────────┬──────────┘
                             │ explained
                             ▼
                    ┌───────────────────┐
                    │IDENTIFY_LIMITS    │── 必须标记类比失效点！
                    └────────┬──────────┘
                             │
                             ▼
                    ┌───────────────────┐
                    │   TRANSITION      │── 过渡到精确（非类比）定义
                    └───────────────────┘
```

### 触发条件

```
1. concept.abstract_level > learner.abstract_tolerance * 1.2
2. concept 有 cross_domain_tags 且在 learner.strongest_domains 中
3. 前两次降阶法讲解后 mastery 仍 < 0.4
```

---

## 6. 间隔复习 (Spaced Repetition)

### 触发条件

```
1. L3 复习调度器推送（每日计划或教学内联复习）
2. 响应学生的"帮我复习"请求
3. 检测到前置概念的 mastery 下降影响当前学习
```

### 复习模式

| 模式 | 适用 mastery | 内容 |
|------|-------------|------|
| `quick_quiz` | > 0.7 | 3 道快速题，1 分钟内完成 |
| `concept_map` | 0.4~0.7 | 让学生画出与其他概念的关系图 |
| `teach_back` | 0.2~0.4 | 费曼式"把这个教给零基础的人" |
| `error_revisit` | 有未解决错误 | 重做之前的错题变体 |
| `mixed_practice` | — | 交错复习多个概念（提升迁移能力） |

---

## 策略选择决策树

```
输入: concept, teaching_context

1. cognitive_load > profile.overload_threshold
   → abstract_level > 0.5 ? AnalogousBridging : ReductionOfOrder(slower)
   
2. concept.abstract_level > profile.abstract_tolerance * 1.2
   → AnalogousBridging

3. mastery < 0.2
   → ReductionOfOrder

4. 0.3 <= mastery < 0.6 且 transfer_ability > 0.5
   → SocraticMethod

5. 0.4 <= mastery < 0.7 且 self_assessment_accuracy < 0.5
   → FeynmanTechnique

6. mastered_count > 0.6*total 且 学生能力足够
   → PBL

7. default
   → ReductionOfOrder
```
