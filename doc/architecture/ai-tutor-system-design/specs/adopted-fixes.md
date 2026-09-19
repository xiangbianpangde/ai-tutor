# 采纳的修正建议

> 来源：2026-05-19 架构审查中识别出的设计漏洞
> 状态：全部已采纳，待开发实施

---

## 修正 1：KG 人工确认节点

**问题**：L4 的 Quality Gate 只检查形式（孤点、循环、覆盖率），不检查语义（定义对不对）。LLM 检查 LLM 的输出不可靠。

**方案**：在 `build_knowledge_graph` 和 `start_learning_session` 之间，加入 `review_kg` 步骤。

### 两种审阅模式

| 模式 | 触发 | 内容 |
|------|------|------|
| **快速审阅** | 默认 | 展示前 20 个最低置信度概念 + Quality Gate warnings + Mermaid 缩略图 |
| **完整审阅** | 用户要求或低置信度概念 > 5% | 交互式浏览全 KG，支持手动补边/修定义/删除 |

### 新增 MCP Tool

```python
# knowledge-mcp
def review_kg(kg_id: str, mode: Literal["quick","full"]="quick") -> ReviewKGResult:
    """返回低置信度概念 + warnings + Mermaid 图 + 建议操作"""

def update_kg(kg_id: str, actions: List[KgEditAction]) -> KgUpdateResult:
    """支持: edit_definition, add_edge, remove_edge, delete_concept, merge_concepts, approve_all"""
```

### 教学流程中的位置

```
acquire_subject → build_knowledge_graph → review_kg (新增) → update_kg → start_learning_session
```

---

## 修正 2：快速摸底测验（Cold-Start Assessment）

**问题**：L5 画像冷启动默认值（abstract_tolerance=0.5）是凭空猜测的。

**方案**：新用户+新科目时，`start_learning_session` 内部先出 10 道跨难度分布的摸底题。

### 题目分布

| 数量 | abstract_level | 目的 |
|------|---------------|------|
| 3 题 | < 0.3 | 测基础掌握 |
| 4 题 | 0.3-0.6 | 测当前水平 |
| 3 题 | > 0.7 | 测抽象耐受度 |

每题后跟自评："你觉得自己答对了吗？(确定/不确定/不知道)"

### 输出

```python
{
    "abstract_tolerance_initial": 0.62,       # 高抽象题准确率
    "transfer_ability_initial": 0.45,         # 类比题表现
    "self_assessment_accuracy_initial": 0.55, # 自评 vs 实际
    "baseline_response_time_ms": 4500,
    "recommended_starting_level": "intermediate",
}
```

---

## 修正 3：时间估计校准

**问题**：`DifficultyScorer.typical_learning_time_min` 的回归系数没有实证校准。

**方案**：分两步。

### 第一步：开发阶段用公共数据校准

用 Khan Academy 的课程数据（已知视频教学时长）训练 XGBoost 回归器，校准特征权重。

### 第二步：48h 验证实验中收集真实数据（见修正 4）

---

## 修正 4：48h 验证实验设计

| 参数 | 值 |
|------|-----|
| 教材 | 简化版 50-80 页（非 400 页） |
| 概念 | 15-30 个核心概念 |
| 学生 | 3-5 人 |
| 测量 | 实际耗时 vs 预测耗时；前后测成绩；心流/焦虑/胜任感主观评分 |

### 验收标准

- 预测时间偏差 < ±30%
- 后测成绩显著高于前测
- 心流体验 ≥ 3/5，焦虑 ≤ 2/5
- 无 KG 定义错误导致教学卡死
- 无非评判防火墙触发（=AI 没说不该说的话）

---

## 实施分组更新

追加到现有 README 实施分组：

```
Phase 0.5 (新增) — KG 人工确认 + 摸底测验 + 校准准备  0.5 周
Phase 4.5 (新增) — 48h 验证实验  1 周
```

### 需更新的设计文件

| 文件 | 更新 |
|------|------|
| `L4-knowledge-engineering.md` | 新增 §7 KG人工确认 + §8 时间校准 |
| `L5-learner-modeling.md` | 新增 cold-start assessment |
| `L7-interaction-layer.md` | knowledge-mcp 增 review_kg/update_kg |
| `specs/server-api-spec.md` | 同上 |
| `specs/testing-strategy.md` | 新增 48h 验证实验作为 E2E |
