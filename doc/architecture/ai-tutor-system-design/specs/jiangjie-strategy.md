# 降阶法策略 — 实现规格

> 状态：✅ 已实现（Slice J）— `servers/tutoring_mcp/strategies/jiangjie.py`，16 测试全绿。
>        §4 的 strategy_selector 规则已加；§4.2 的 engine flow_regulator 集成仍待 P1 #4。
> 实现者参考：
>   - 已有策略模板：`servers/tutoring_mcp/strategies/reduction.py`
>   - 策略基类：`servers/tutoring_mcp/strategies/base.py`
>   - 策略注册：`servers/tutoring_mcp/strategies/__init__.py`
>   - 策略选择器：`servers/tutoring_mcp/strategy_selector.py`
>   - 心流调节器（已实现）：`servers/tutoring_mcp/flow_regulator.py`
>   - 设计源：`doc/降阶学习法.md`

---

## 1. 概述

降阶法不是现有 `ReductionStrategy`（通用教学状态机）的升级版，而是一种**独立的、全新的教学策略**。

### 核心差异

| 维度 | 现有 ReductionStrategy | 降阶法 (JiangjieStrategy) |
|------|----------------------|--------------------------|
| 教学起点 | 从定义出发（"X 的定义是..."） | 从目标出发（"学完这个你能..."） |
| 理解路径 | 讲解 → 检测 → 练习 | 拆成原子 → 排除错误 → 骨架重构 |
| 错误处理 | 答错 → 重新讲解 | 答错 → 纳入补集枚举 → 排除法确认 |
| 学习产出 | 无结构化产出 | 知识骨架（前提→逻辑→结论→易错点） |
| 心流结合 | 被动（gain_loop_monitor 修复断裂） | 主动（FlowRegulator 调教学参数） |

---

## 2. 状态机定义

### 状态图

```
                    ┌──────────┐
                    │  IDLE    │
                    └────┬─────┘
                         │ start(target, mastery_map, params)
                         ▼
                    ┌──────────┐
                    │  GOAL    │──── 定义高阶目标
                    └────┬─────┘
                         │ goal_understood
                         ▼
                    ┌──────────┐
               ┌───▶│  REDUCE  │──── 降维成 3-5 个原子问题，逐个确认
               │    └────┬─────┘
               │         │ all_atoms_understood
               │         ▼
               │    ┌──────────┐
               │    │COMPLEMENT│──── 列出 5-10 个常见错误，逐一排除
               │    └────┬─────┘
               │         │ all_errors_excluded
               │         ▼
               │    ┌──────────┐
               │    │RECONSTRUCT   ──── 构建知识骨架
               │    └────┬─────┘      （前提→逻辑→结论→易错点）
               │         │ reconstructed
               │         ▼
               │    ┌──────────┐
               │    │  REVIEW  │──── 当堂验证
               │    └────┬─────┘
               │         │
               │  pass───┤───fail──┐
               │         │         │
               │         ▼         │
               │    ┌──────────┐   │
               │    │  NEXT    │   │  (回到 RECONSTRUCT)
               │    └──────────┘   │
               │                   │
               └───────────────────┘
```

### 状态详细定义

#### GOAL — 定义高阶目标

| 属性 | 值 |
|------|-----|
| 进入条件 | `start()` 调用后 |
| 教学动作 | `type="explain"`，说明"学完这个概念你能做什么/解决什么问题" |
| 退出条件 | 学生确认理解目标（`goal_understood` 事件） |
| 脚手架行为 | scaffold_level=3 时：给出目标+为什么重要+前置依赖 |
| 心流结合点 | 清晰目标本身就是心流条件。调节器可微调目标描述的复杂度 |

**get_action() 输出示例（scaffold_level=3）：**
```
"接下来我们要学【偏导数】。
学完这个，你就能算出"曲面在某一点沿某个方向有多陡"。
这是梯度下降法（机器学习核心）的数学基础。
前置要求：你理解一元导数。需要我快速回顾吗？"
```

**get_action() 输出示例（scaffold_level=0）：**
```
"偏导数。一个函数对其中一个变量的变化率。
开始。"
```

---

#### REDUCE — 降维拆解

| 属性 | 值 |
|------|-----|
| 进入条件 | `goal_understood` 事件 |
| 教学动作 | 把概念拆成 sub_step_count 个原子问题，逐一提出 + 确认 |
| 退出条件 | 所有原子问题都被确认理解（逐题 answered+correct） |
| 子步骤管理 | 内部计数器 `_atom_index`，0 → sub_step_count-1 |
| 心流结合点 | 每个原子问题答对 → 即时成就感。调节器控制 sub_step_count 和 confirm_each_step |

**get_action() 行为：**
- `_atom_index < sub_step_count`：提出第 `_atom_index+1` 个原子问题
- 每个问题格式："原子问题 N/M：一句话回答 [问题]"
- `confirm_each_step=True` 时：答完每个原子追问"你确定吗？"

**transition("answered") 行为：**
- correct → `_atom_index += 1`，如果达到 sub_step_count → 发射 `all_atoms_understood`
- partial → `_atom_index += 1`，但标记该原子为 weak（后续补集会用到）
- incorrect → `_atom_index` 不变，重新问（尝试换角度重述问题）

**示例（sub_step_count=4，概念=偏导数）：**
```
原子问题 1/4：偏导数解决什么问题？—— 一句话回答
原子问题 2/4：偏导数符号 ∂f/∂x 怎么读？各部分代表什么？
原子问题 3/4：计算 ∂f/∂x 时，把 y 当常数还是变量？
原子问题 4/4：偏导数和一元导数本质区别是什么？
```

---

#### COMPLEMENT — 补集枚举

| 属性 | 值 |
|------|-----|
| 进入条件 | `all_atoms_understood` 事件 |
| 教学动作 | 逐条列出 error_count 个常见错误理解，每次问"这个错在哪" |
| 退出条件 | 所有错误被正确排除（逐题 answered+correct） |
| 子步骤管理 | 内部计数器 `_error_index`，0 → error_count-1 |
| 心流结合点 | 排除法产生控制感。调节器控制 error_count |

**get_action() 行为：**
- `_error_index < error_count`：展示第 `_error_index+1` 个错误，问"这个为什么错"

**transition("answered") 行为：**
- correct（学生说对了错因）→ `_error_index += 1`
- incorrect → 给出错因解析，然后 `_error_index += 1`（补集教学：让学生知道了为什么错，也算完成）

**示例（concept=偏导数）：**
```
❌ 误解 1/6："∂f/∂x 就是把 f 对 x 求导，和其他变量没关系。"
→ 学生：不对，虽然是把 y 当常数，但"常数"不是不存在，只是暂不变。

❌ 误解 2/6："偏导数存在就一定连续。"
→ 学生：不对，一元可导必连续，但多元偏导存在不能推出连续。

❌ 误解 3/6："∂²f/∂x∂y = ∂²f/∂y∂x 恒成立。"
→ 学生：不对，只有二阶混合偏导连续时才相等，不是无条件。
```

---

#### RECONSTRUCT — 骨架重构

| 属性 | 值 |
|------|-----|
| 进入条件 | `all_errors_excluded` 事件 |
| 教学动作 | 引导学生构建四部分骨架：前提 → 逻辑 → 结论 → 易错点 |
| 退出条件 | 学生完成骨架（`reconstructed` 事件） |
| 产出物 | 知识骨架（前提→逻辑→结论→易错点），持久化到 session |
| 心流结合点 | 完成骨架 → 掌控感。这是降阶法区别于其他策略的关键产出 |

**教学流程（无需 LLM，结构化引导即可）：**
```
引导 1：这个结论成立的前提条件是什么？
引导 2：推理的核心逻辑，三两句话说清楚。
引导 3：最终的结论是什么？
引导 4：最容易在哪犯错？

骨架完成 → 展示给学生看 → 问"这个骨架准确吗？"
```

**示例（concept=偏导数）：**
```
学生产出的骨架：
┌────────────────────────────────────────────────┐
│偏导数                                             │
│前提：函数在这一点附近有定义，其他变量固定             │
│逻辑：只对目标变量求导，其他变量视为常数               │
│结论：∂f/∂x₀ = lim(Δx→0) [f(x₀+Δx,y₀)-f(x₀,y₀)]/Δx │
│易错点：偏导存在≠连续；混合偏导相等需要连续条件         │
│       ∂/∂x 不是除法，是求偏导运算符                 │
└────────────────────────────────────────────────┘
```

---

#### REVIEW — 当堂验证

| 属性 | 值 |
|------|-----|
| 进入条件 | `reconstructed` 事件 |
| 教学动作 | 出一道综合应用题（难度由 difficulty_multiplier 控制） |
| 退出条件 | correct → 发射 `review_passed`，进入 NEXT |
|  | incorrect → 发射 `review_failed`，回到 RECONSTRUCT 修正骨架 |
| 心流结合点 | 难度匹配当前心流，避免太简单（无聊）或太难（焦虑） |

**难度控制：**
- difficulty_multiplier=0.6（SILENT）：直接套公式的基础题
- difficulty_multiplier=1.0（FLUENT）：需要两步推理的标准题
- difficulty_multiplier=1.4（IMMERSED）：需要多步推理 + 概念联系的挑战题

---

#### FLAG_DIFFICULT — 无法推进

| 属性 | 值 |
|------|-----|
| 进入条件 | 同一状态 attempt_count ≥ max_attempts（默认 3） |
| 教学动作 | 建议换策略（`switch_strategy`），或外部决定 |

---

### 完整参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `sub_step_count` | int | 5 | 原子问题数量，由调节器覆盖 |
| `error_count` | int | 7 | 补集枚举错误数量，由调节器覆盖 |
| `confirm_each_step` | bool | True | 是否每步追问确认 |
| `max_attempts` | int | 3 | 同一状态最大重试次数 |
| `scaffold_level` | int | 1 | 脚手架级别，由调节器覆盖 |
| `difficulty_multiplier` | float | 1.0 | 复习题难度系数，由调节器覆盖 |

---

## 3. 与心流调节器的结合

### 调用时序

```python
# 在 TeachingEngine 中：

def next_action(self, session_id):
    # ...
    flow_level = self._get_current_flow_level(ctx)
    
    # 调用调节器拿到教学参数
    pace = self.flow_regulator.recommend_pace(
        flow_level=flow_level,
        cognitive_load=ctx.meta.current_cognitive_load,
        recent_accuracy=self._recent_accuracy(ctx),
    )
    
    # 策略接收 pace 参数
    strat = get_strategy("jiangjie")
    strat.start(target=concept, mastery_map=..., params=pace.to_dict())
    # ...
```

### 调节器如何影响降阶法

| FlowLevel | 调节器输出 | 降阶法行为变化 |
|-----------|----------|---------------|
| SILENT | difficulty=0.6, scaffold=3, sub=3, err=5 | 原子问题最少，脚手架最密，错误最少——重建安全感 |
| SHALLOW | difficulty=0.8, scaffold=2, sub=4, err=6 | 逐步增加挑战 |
| FLUENT | difficulty=1.0, scaffold=1, sub=5, err=7 | 标准教学节奏 |
| DEEP | difficulty=1.2, scaffold=0, sub=5, err=8 | 无脚手架，更多挑战性错误点 |
| IMMERSED | difficulty=1.4, scaffold=0, sub=4, err=10 | 最高难度错误，延伸追问，无确认步骤 |

---

## 4. 集成变更清单

### 新增文件
| 文件 | 内容 |
|------|------|
| `servers/tutoring_mcp/strategies/jiangjie.py` | 降阶法策略实现（本规格的状态机） |

### 已有文件（已实现，无需改动）
| 文件 | 内容 |
|------|------|
| `servers/tutoring_mcp/flow_regulator.py` | 心流调节器（PaceConfig + FlowRegulator） |

### 修改文件
| 文件 | 变更 |
|------|------|
| `servers/tutoring_mcp/strategies/__init__.py` | `_REGISTRY` 加 `"jiangjie": JiangjieStrategy`，`__all__` 加导出 |
| `servers/tutoring_mcp/strategy_selector.py` | 决策树加降阶法规则（见 §4.1） |
| `servers/tutoring_mcp/engine.py` | 在 `respond()` 中增加 flow_regulator 调用（见 §4.2） |

### 4.1 strategy_selector 的降阶法规则

在现有 7 条决策规则之后（或作为 default 的增强），增加：

```python
# 规则 8（新增）：降阶法 — 学生抗拒/焦虑/初次接触
# 触发条件：学生初次接触该科目，或认知负荷高，或心流级别低
if learner_profile.behavioral.preferred_pace == "thorough" or cognitive_load > 0.6:
    return "jiangjie"
```

降阶法的定位：**默认首选策略**，当学生抗拒、焦虑、认知负荷高时，降阶法比 reduction 更有效，因为它的"补集排除"机制让学生感觉在"自己发现答案"而非"被灌输知识"。

### 4.2 engine.py 的 flow_regulator 集成点

当前 engine.py 已有 `compute_flow_signals` + `next_flow_level` + `detect_break`（被动心流），需要增加主动调用：

```python
# 在 respond() 中，大约第 335 行（new_level 计算之后）：
new_level = next_flow_level(current_level=prev_level, signals=signals)
ctx.recent_history[-1]["flow_level"] = int(new_level)

# 新增：主动心流调节 — 更新 pace_config 供 next_action 使用
# （不存到 ctx，每次 next_action 实时计算即可）
```

不需要改动太多：engine 只需要在 `next_action()` 中计算 pace，并传递给策略的 `params`。

---

## 5. 与现有 ReductionStrategy 的关系

| 场景 | 用哪个策略 |
|------|-----------|
| 新概念，学生状态良好 | reduction（现有）或 jiangjie（新）均可 |
| 学生答错多次，焦虑 | **jiangjie**（补集排除法降低焦虑） |
| 学生已经理解但需要巩固 | reduction（pass 更直接） |
| 学生初次接触高难度概念 | **jiangjie**（原子拆分降低门槛） |
| 心流级别 SILENT/SHALLOW | **jiangjie**（温和起步，重建安全感） |
| 心流级别 DEEP/IMMERSED | reduction（快速推进）或 feynman（让学生讲解） |

---

## 6. 验证测试

实现后验证以下场景：

```python
# 测试 1：降阶法完整流程
strategy = JiangjieStrategy()
strategy.start(target=concept, mastery_map={}, params={"
sub_step_count": 3, "error_count": 4})
assert strategy.state == "GOAL"

strategy.transition(event="goal_understood", payload={})
assert strategy.state == "REDUCE"
assert strategy._atom_index == 0

# 全部答对 → 推进到 COMPLEMENT
strategy.transition(event="answered", payload={"correctness": "correct"})
# ...（重复 3 次）
assert strategy.state == "COMPLEMENT"

# 测试 2：REDUCE 答错 → 不推进
old_index = strategy._atom_index
strategy.transition(event="answered", payload={"correctness": "incorrect"})
assert strategy._atom_index == old_index  # 不变

# 测试 3：SCAFFOLD 影响动作文本
# scaffold_level=3 → get_action().content 含引导
# scaffold_level=0 → get_action().content 简洁
```
