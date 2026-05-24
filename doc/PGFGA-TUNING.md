# PGFGA 调参手册

> 正向增益反馈生成算法（PGFGA）在 ai-tutor 里的所有可调参数、词表、阈值，
> 以及它们如何相互影响。
>
> 适用版本：Slice T3 之后（含 FlowSignals + FlowTracker + GainLoopMonitor +
> NonJudgmentFirewall + 增益回路修复）。
>
> 路径基准：`ai-tutor/`

---

## 0. 数据流总览

每次 `respond(session_id, answer)` 触发的完整 PGFGA 链路：

```
┌──────────────────────────────────────────────────────────────────────┐
│ engine.respond(answer)                                               │
│                                                                      │
│  ① LLMScorer.score        → correctness / evidence                   │
│  ② BKTStore.record         → mastery 更新                            │
│  ③ ErrorDiagnoser          → error_analysis（partial/incorrect）    │
│  ④ _build_raw_feedback    → 反馈原文                                │
│  ⑤ NonJudgmentFirewall    → 命中禁词 → 安全模板替换                 │
│  ⑥ Strategy.transition    → CHECK → PRACTICE/EXPLAIN/FLAG          │
│  ⑦ MemoryStore.record     → review_history + λ 拟合                 │
│                                                                      │
│  ── 以下是 T3 新增 PGFGA 链路 ──                                     │
│  ⑧ recent_history += turn (cap 20)                                  │
│  ⑨ compute_flow_signals(history) → FlowSignals（10 信号）           │
│  ⑩ next_flow_level(prev, signals)→ FlowLevel(0..4)                  │
│  ⑪ detect_break(signals, skips)  → GainLoopBreak | None             │
│  ⑫ if break: next_action = repair(break_type) → break_suggestion   │
│                                                                      │
│  return ResponseResult(correctness, feedback, error_analysis,       │
│                        mastery_update, next_action)                 │
└──────────────────────────────────────────────────────────────────────┘
```

调参就是改下面四张表里的数字 / 词表 / 模板。

---

## 1. 参数清单速查表

| 类别 | 文件 | 关键参数 | 默认 | 影响 |
|---|---|---|---|---|
| 心流信号 | `servers/tutoring_mcp/flow_signals.py` | `_CAUSAL_WORDS` | 7 词 | depth_increasing 检出灵敏度 |
| | | `_INITIATIVE_WORDS` | 5 词 | initiative_taking 检出灵敏度 |
| | | `_HESITATION_WORDS` | 6 词 | hesitation_decreasing 灵敏度 |
| | | `_HELP_WORDS` | 5 词 | help_seeking_spike 灵敏度 |
| | | `_EMOTION_MARKERS` | 7 词 | emotional_flatness 反向 |
| | | `_is_short` max_len | 5 | withdrawal_pattern 严格度 |
| | | length growth 比例 | 1.3× | answer_length_growth 灵敏度 |
| | | speed up 比例 | 0.8× | inter_turn_speed_up 灵敏度 |
| | | withdrawal 窗口 | 3 轮 | withdrawal_pattern 反应快慢 |
| | | flatness 窗口 | 5 轮 | emotional_flatness 反应快慢 |
| | | help_spike 窗口 | 2 轮 | help_seeking_spike 反应快慢 |
| | | regression 窗口 | 2 轮 | answer_regression 反应快慢 |
| 心流状态机 | `servers/tutoring_mcp/flow_tracker.py` | `_POSITIVE_FIELDS` | 6 | 升级速度 |
| | | `_NEGATIVE_FIELDS` | 4 | 降级速度 |
| | | 升 1 级阈值 | net ≥ 2 | 进阶难度 |
| | | 跌 2 级阈值 | net ≤ -2 | 退步惩罚 |
| | | 防火墙违规 → | SILENT | 一票否决严重程度 |
| 增益回路 | `servers/tutoring_mcp/gain_loop_monitor.py` | avoidance 阈值 | 跳过 ≥ 3 | 主动放弃检测 |
| | | `_REPAIR_TEMPLATES` | 4 句 | 修复措辞 |
| | | 优先级顺序 | avoidance>surface>withdrawal>flatness | 多重断裂时取舍 |
| 防火墙 | `servers/tutoring_mcp/non_judgment_firewall.py` | `_RULES` | 6 类×N 词 | 反馈过滤严格度 |
| | | `_RULES`.suggested_fallback | 6 句 | 命中后给 prompt 写手的替代建议 |
| 历史窗 | `servers/tutoring_mcp/engine.py` | `_MAX_HISTORY` | 20 | 心流信号能看到多远 |
| BKT 先验 | `servers/tutoring_mcp/bkt.py` 间接由 | `BKTParams.p_*` | 0.05~0.15 | 与心流无直接关系，但影响判分→负信号 |

---

## 2. 心流信号词表调参（`flow_signals.py`）

### 当前词表

```python
_CAUSAL_WORDS     = ("因为", "所以", "原因是", "导致", "因此", "对比", "区别是")
_INITIATIVE_WORDS = ("我能", "我想", "能不能让我", "可不可以", "我来试")
_HESITATION_WORDS = ("嗯...", "嗯…", "可能是", "也许", "不确定", "我猜")
_HELP_WORDS       = ("怎么办", "什么意思", "不懂", "不会", "帮我")
_EMOTION_MARKERS  = ("？", "?", "啊", "哦", "我觉得", "好奇", "为什么", "！")
```

### 调整原则

| 现象 | 调整 | 备注 |
|---|---|---|
| 学生明明在深入思考，但 depth_increasing 总是 False | 加因果/对比词："关键是", "本质上", "区别在于", "重点", "总结来说" | 不要加过长短语 |
| 学生主动延伸了讨论但 initiative_taking 漏检 | 加："我观察到", "好奇为什么", "试着", "另一种" | 留意误伤——不要加普通陈述 |
| 学生频繁说"嗯..."但 hesitation_decreasing 不灵敏 | 减少 `_HESITATION_WORDS`（避免过度过滤）或加更精准词："想想看", "好像" | |
| Emotional_flatness 过敏感（学生在认真但低调答题就被标记）| 把 emotional_flatness 窗口从 5 加到 7-8 轮 | 减慢检出 |
| Emotional_flatness 不敏感（学生明显闭嘴了还不报）| 把窗口从 5 减到 3-4 轮 | 加快检出 |

### 修改步骤

1. 打开 `servers/tutoring_mcp/flow_signals.py`
2. 修改对应 `_*_WORDS` 元组
3. 跑 `uv run pytest servers/tutoring_mcp/tests/test_flow_signals.py` 确保不破坏既有测试
4. 跑 `uv run python scripts/demo_t3.py --mock` 看心流变化

### 何时不该改词表

如果想做语义级判断（"虽然没含 '因为' 但学生在做因果推理"），关键词永远不够准。
往 `flow_signals.py` 加一个 `_llm_augment(turn)` 用 LLM 做二审。但要付出 5-10×
延迟成本，建议留到 Slice T4+。

---

## 3. 心流状态机阈值调参（`flow_tracker.py`）

### 当前规则

```python
def next_flow_level(current_level, signals, firewall_violation=False):
    if firewall_violation:
        return FlowLevel.SILENT
    net = (#positive) - (#negative)
    if   net >=  2:  new = cur + 1     # 升 1 级
    elif net <= -2:  new = cur - 2     # 跌 2 级
    elif net == 1:   new = cur + 1
    elif net == -1:  new = cur - 1
    else:            new = cur         # 维持
    return clamp(new, SILENT, IMMERSED)
```

### 调整原则

| 想要的行为 | 改法 |
|---|---|
| **升级更难**（防止误判进入心流） | 把 `net >= 2` 改成 `net >= 3` |
| **升级更容易**（鼓励早期学生）| 把 `net >= 2` 改成 `net >= 1`（但会让单一信号误升级） |
| **失败惩罚更轻**（让学生不会一答错就被打到 SILENT） | 把 `net <= -2` 跌 2 级改成跌 1 级；或把阈值提到 -3 |
| **失败惩罚更重** | 把跌 2 级改成跌 3 级 |
| **防火墙违规不再一票否决到 SILENT**（在调试期能用）| 改成 `current_level - 2`；生产请保留 SILENT |

### 调参实验方法

1. **基线**：用 `scripts/demo_t3.py --mock` 跑一次，记录 7 轮 flow_level 序列
2. **改阈值**：例如 `net >= 3` 升级
3. **重跑**：对比序列差异。期望：渐入佳境慢一些（4→3 才到 DEEP），更稳健

### 推荐配置

| 场景 | net 升 | net 跌 | 防火墙 |
|---|---|---|---|
| 严格教学（高校 / 考试场景）| 3 | -2 (跌 2 级) | → SILENT |
| 兴趣探索（科普 / 自学）| 1 | -1 (跌 1 级) | → 跌 1 级 |
| 默认（当前）| 2 | -2 (跌 2 级) | → SILENT |

---

## 4. 增益回路阈值调参（`gain_loop_monitor.py`）

### 当前优先级（先匹中先返回）

```
1. avoidance_pattern    if recent_skipped_count >= 3
2. surface_responses    if help_seeking_spike and withdrawal_pattern
3. student_withdrawal   if withdrawal_pattern (emotional_flatness 可选)
4. emotional_flattening if emotional_flatness and not any positive
```

### 调整原则

| 想要的行为 | 改法 |
|---|---|
| 跳过 2 次就报 avoidance | 改 `>= 3` 为 `>= 2`，会更早干预但容易误判 |
| 不希望连续 3 短就被打断 | 在 student_withdrawal 加回 `and signals.emotional_flatness` 条件 |
| 想加新的断裂类型（例：confusion_spike）| 在 `detect_break` 加一段；加对应 `_REPAIR_TEMPLATES[..]`；扩展 spec FlowSignals 增加 confusion 信号 |

### 修复措辞模板（最常被改）

```python
_REPAIR_TEMPLATES = {
    "student_withdrawal":      "我感觉我们走得有点匆忙了。你不需要一次答对——告诉我你的想法...",
    "emotional_flattening":    "我注意到你今天感觉状态不太一样。要不要休息一下...",
    "surface_responses":       "我们一起慢下来。先把这一个概念吃透——不急...",
    "avoidance_pattern":       "这几个概念可能让你觉得有点远。我们换一个你感兴趣的切入点试试...",
}
```

### 改文案的硬性约束（PGFGA 三铁律）

每改一句都必须能通过下面 3 项自检：

1. **话语权检查**：不强行推进 / 不命令学生（"必须 / 应该 / 一定要" → 禁）
2. **接纳半成品**：不含负面判定（"不对 / 你错了 / 想太多" → 禁）
3. **内在动机导向**：不空洞夸奖（"太棒了 / 真聪明" → 禁）
4. **必须能过 `NonJudgmentFirewall.scan(content) is None`**（已有 test 钉死，改完跑测试）

```powershell
uv run pytest servers/tutoring_mcp/tests/test_gain_loop_monitor.py::test_repair_actions_pass_firewall
```

---

## 5. 防火墙词表调参（`non_judgment_firewall.py`）

### 当前 6 类禁词

```python
_RULES: list[tuple[category, pattern, suggested_fallback)] = [
    ("negation",      r"不对|你错了|这不合理|不是这样的", ...),
    ("judgment",      r"想太多|没必要|太幼稚|不成熟|这很简单|你应该知道", ...),
    ("preachy",       r"你应该|正确做法是|要知道|你必须|一定要|记住", ...),
    ("topic_killer",  r"^好的[，。\s]*$|^明白了[，。\s]*$|^了解了[，。\s]*$", ...),
    ("empty_praise",  r"太棒了|你好聪明|你真厉害|你真优秀", ...),
    ("topic_shift",   r"我们回到|还是聊聊|先不说这个", ...),
]
```

### 调整原则

| 现象 | 调整 |
|---|---|
| 学生反馈"AI 太啰嗦/客套"| 加禁词到 `empty_praise`："非常好 / 完美 / 优秀的回答" |
| 误伤合法表达（如概念名"正确做法"作为题目本身）| 用更精确的正则边界，例如 `r"^正确做法是"` 加锚点 |
| 想完全关闭某类（如开发调试期）| 注释掉对应行；记得跑测试看哪些用例破 |
| 想本地化（英文场景）| 复制一份 `_RULES_EN`，根据 LANG 切换 |

### 加新一类的标准流程

1. 在 `_RULES` 列表加一行 `(category, pattern, suggested_fallback)`
2. 在 `shared/schemas.py` 的 `FirewallViolation.category` Literal 加新名（如 "sarcasm"）
3. 写 1 个测试 `test_<category>_caught()` 用一句典型句子检查命中
4. 跑全量 `uv run pytest`

---

## 6. 历史窗口与策略参数

### `engine.py` 顶部：`_MAX_HISTORY = 20`

| 改 | 影响 |
|---|---|
| 调小（如 10）| 心流信号"健忘"，反应灵敏但容易抖动 |
| 调大（如 50）| 状态更稳定但内存占用上升、SessionContext.recent_history 序列化更慢 |

**建议**：保持 20。若做"长会话"模式（>1 小时），加到 40-50。

### 策略选择决策树阈值（`strategy_selector.py`）

虽不在 PGFGA 严格范围，但与心流相关：

```python
_OVERLOAD_THRESHOLD     = 0.75   # cognitive_load > 此值视为过载
_ABSTRACT_AMPLIFIER     = 1.2    # abstract > tolerance * 此值用 analogy
```

- 想让 analogy 更常用 → 把 amplifier 降到 1.1
- 想让认知过载更早触发 → 把 threshold 降到 0.65

---

## 7. 调参实验方法

### 单参数 A/B 流程

```powershell
# 1. 基线
cd C:\Users\yhn\Desktop\ai-tutor
rm -f data/tutor.db
PYTHONIOENCODING=utf-8 uv run python scripts/demo_t3.py --mock > baseline.txt

# 2. 改参数（如 flow_tracker 升级阈值 2 → 3）
#    编辑 servers/tutoring_mcp/flow_tracker.py

# 3. 对照
rm -f data/tutor.db
PYTHONIOENCODING=utf-8 uv run python scripts/demo_t3.py --mock > variant.txt

# 4. 对比
diff baseline.txt variant.txt
```

### 多场景压力测试

写一个"测试集"，每个 case 是一段学生答题序列 + 期望的 flow_level/break_type：

```python
# scripts/pgfga_eval.py（待 Slice T3+）
SCENARIOS = [
    {"name": "渐入佳境", "answers": [...], "expected_final": "DEEP", "expected_break": None},
    {"name": "应付", "answers": ["嗯","不会","..."], "expected_break": "student_withdrawal"},
    {"name": "回避", "answers": [...], "expected_break": "avoidance_pattern"},
    ...
]
# 跑全集 → 报告命中率
```

---

## 8. 监控指标（生产环境）

### 关键日志字段（来自 `engine.respond` 调用）

```
respond.done                concept=X correctness=Y mastery=0.5 flow_level=2 gain_break=None
gain_loop.break_detected    break_type=student_withdrawal session_id=...
scorer.fallback_heuristic   reason=...
```

### SQL 查询模板

```sql
-- 最近 7 天心流分布（取 recent_history 末尾）
SELECT
  json_extract(context_json, '$.recent_history[#-1].flow_level') AS flow,
  COUNT(*) AS n
FROM sessions
WHERE started_at > datetime('now', '-7 days')
GROUP BY flow;

-- 最近 7 天回路断裂统计
SELECT
  json_extract(value, '$.metadata.break_type') AS bt,
  COUNT(*) AS n
FROM sessions, json_each(context_json, '$.recent_history')
WHERE json_extract(value, '$.metadata.break_type') IS NOT NULL
GROUP BY bt;

-- 防火墙触发率（间接：feedback 含安全模板"我看到你在认真思考"）
SELECT COUNT(*) FROM sessions
WHERE json_extract(context_json, '$.recent_history') LIKE '%我看到你在认真思考%';
```

### 期望分布（健康值）

| 指标 | 健康范围 | 红线 |
|---|---|---|
| flow_level=DEEP 的会话占比 | 15-35% | < 5% 说明心流太难达到 |
| flow_level=SILENT 的会话占比 | 10-25% | > 50% 说明启发式太严 |
| GainLoopBreak 触发率（per session）| 0-1 次 | > 3 次说明断裂检测过敏感 |
| 防火墙触发率（per 100 reply）| < 5 | > 20 说明 prompt 模板有系统性问题 |

---

## 9. 常见调优场景处方

### 场景 1：用户反馈"AI 总是问问题，太少讲解"

诊断：可能 ReductionStrategy 的 CHECK → PRACTICE 路径走太频繁；或 `Strategy.transition`
没正确推进。

**不调 PGFGA。** 改 `servers/tutoring_mcp/strategies/reduction.py`，降低 CHECK 触发频率。

### 场景 2：学生几句不顺就被打断说"休息"

诊断：`detect_break` 触发太早。

**处方**：
- `_is_short` max_len 从 5 改成 3（更严的"短答"定义）
- 或：把 `student_withdrawal` 加回 `and signals.emotional_flatness` 双条件

### 场景 3：学生明显走神 AI 没察觉

诊断：emotional_flatness 窗口太大；help_seeking 词太严。

**处方**：
- `_is_short` max_len 改 8（让"嗯"、"知道了"也算短）
- emotional_flatness 窗口 5 → 3

### 场景 4：升级太快（一句"为什么"就到 DEEP）

诊断：状态机阈值过低。

**处方**：
- `flow_tracker.py` 的 `net >= 2` 改 `net >= 3`
- 或：在 `flow_signals.py` 把 `_INITIATIVE_WORDS` 收紧（删"我想"）

### 场景 5：跨语言场景（学生用英文）

**处方**：
- 复制 `flow_signals.py` 为 `flow_signals_en.py`，英文词表
- engine 启动时按 `LANG` 环境变量切换
- 跑测试时加 `LANG=en` 启动

---

## 10. PGFGA 三铁律自检清单（每次调参后必跑）

```powershell
# 1. 防火墙 + 回路修复全部过测试
uv run pytest servers/tutoring_mcp/tests/test_non_judgment_firewall.py
uv run pytest servers/tutoring_mcp/tests/test_gain_loop_monitor.py

# 2. 防火墙拦截率不能为 0（否则可能漏判）— 启发式测试
uv run python -c "
from servers.tutoring_mcp.non_judgment_firewall import NonJudgmentFirewall
fw = NonJudgmentFirewall()
canary = ['不对', '太棒了', '你应该', '你想太多']
for c in canary:
    assert fw.scan(c) is not None, f'拦截失败: {c}'
print('all canary intercepted')
"

# 3. 完整端到端 demo 跑通
PYTHONIOENCODING=utf-8 uv run python scripts/demo_t3.py --mock

# 4. 全量回归
uv run pytest
```

铁律检查（手工 review）：

- [ ] 改完的 `_REPAIR_TEMPLATES` 没有"你应该/必须/想太多"等命令式词
- [ ] 改完的 `_INITIATIVE_WORDS` 不把"我必须"这种否定语作为正面信号
- [ ] 改完的 flow 阈值不会让"AI 一直夸学生"（empty_praise 仍被拦截）
- [ ] 改完的 `_HELP_WORDS` 不把合法的"为什么"打成求助（区分好奇 vs 求救）

---

## 11. 进一步阅读

- `specs/pgfga-integration.md` — 完整 PGFGA 设计（理论 + 7 层映射）
- `ROADMAP.md` §5 (Slice T3) — 当前实现的覆盖范围
- `scripts/demo_t3.py` — 心流升降 + 断裂修复参考脚本
- `INTEGRATION.md` — 在 Claude Desktop 接入后的调参思路（host LLM prompt 也是 PGFGA 的一部分）

---

## 12. 版本与变更日志

| 日期 | 版本 | 调整 |
|---|---|---|
| 2026-05-22 | T3 v1 | 首版 PGFGA 落地：10 信号 + 5 级心流 + 4 类断裂 + 6 类防火墙 |
| - | - | 调参时在此追加：日期、改了什么、为什么、回归测试结果 |
