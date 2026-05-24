# PGFGA 集成分析

> 将"正向增益反馈生成算法"的核心机制嵌入 AI Tutor 的 L5（学习者建模）和 L6（教学引擎）层
> PGFGA 来源：`Desktop/正向增益反馈生成算法-豆包/` 核心设计文档
> 理论基础：Csikszentmihalyi 心流理论 + Deci & Ryan SDT + Vygotsky ZPD + Rogers 人本主义

---

## 一、PGFGA → AI Tutor 的映射关系

### 1.1 七层架构映射

| PGFGA 架构层 | AI Tutor 对应层 | 映射关系 |
|-------------|----------------|---------|
| 第1层: 角色定位（思维助产士） | L6 教学引擎的角色定义 | 教学引擎不是"教师"，是"助产士"——不灌输知识，帮学生自己发现 |
| 第2层: 话语权倒置 | L2 会话管理 + L6 决策循环 | 学生打断有**最高优先级**，系统不强制执行教学计划 |
| 第3层: 无评价中性接纳 | L6 的 respond() 反馈生成 | 所有教学反馈先过"非评判防火墙" |
| 第4层: 思绪结构化（碎片聚类） | L6 checkpoint 功能 | 阶段总结时不评价对错，帮助学生自己看到思维脉络 |
| 第5层: 正向强化反馈 | L6 respond() + L4 digest | 精准点出学生思考中的亮点，不空洞夸奖 |
| 第6层: 同频共振对齐 | L5 学习者画像(新增) | 追踪"学习节奏偏好"和"表达风格"，动态适配 |
| 第7层: 对话状态记忆 | L2 会话上下文 + L3 长期记忆 | 保留跨会话的学习风格和思维习惯 |

### 1.2 三条铁律在教学场景的适配

```
PGFGA 铁律                          AI Tutor 教学化适配
──────────────────────────────────────────────────────────────────

铁律1: 话语权永远在用户              学习者对教学节奏和方向有否决权
  → 不主导不纠正                      → next_action() 是建议，不是命令
                                      → interrupt() 有最高优先级
                                      → 学生说"跳过" → 立即跳过，不追问原因

铁律2: 无条件接纳半成品              错误应答 = 半成品想法
  → 不评判不否定不说教                → 先共情承接，再引导发现
                                      → 错误分析从"你错了"变为"你这里有一个有意思的尝试"

铁律3: 内在动机导向                  学习动力来自内部
  → 反馈指向思考价值，非外部标签       → 不说"你进步了12%"（外部指标）
                                      → 说"你现在能从极限自然地过渡到连续性的讨论了"
```

---

## 二、集成点 1：L5 新增——心流状态追踪

### 2.1 心流等级定义（学习场景适配版）

```python
# addition to L5 learner modeling

class FlowLevel(IntEnum):
    SILENT = 0      # 静默：答得慢、犹豫、频繁求助 → "这个太难了"
    SHALLOW = 1     # 浅层：开始尝试但表面，偶尔答对简单题
    FLUENT = 2      # 流畅：答题连贯，正确率上升，主动推进
    DEEP = 3        # 深入：主动串联概念，举一反三
    IMMERSED = 4    # 沉浸：完全专注，时间感消失，自驱表达
```

### 2.2 心流检测信号（与认知负荷互补，非重复）

认知负荷关注"学生是不是太累了"；心流检测关注"学生是不是在最佳学习状态"。两个信号互补，不能互相替代。

```python
class FlowSignals(BaseModel):
    # 增长信号 (上行)
    answer_length_growth: bool       # 本轮答案长度 > 最近5轮平均 × 1.3
    depth_increasing: bool            # 本轮答案的语义深度 > 最近5轮平均
    initiative_taking: bool           # 学生主动发起新话题/新问题
    hesitation_decreasing: bool       # "嗯...""可能是..."等犹豫词减少
    inter_turn_speed_up: bool         # 轮次间隔缩短
    self_correction_quality: bool     # 自纠质量高（有依据的修正）

    # 衰减信号 (下行)
    withdrawal_pattern: bool          # 连续三次极简回答（"不会"/"嗯"）
    help_seeking_spike: bool          # 求问频率突然增加
    answer_regression: bool           # 正确率突然下降（排除概念难度因素）
    emotional_flatness: bool          # 答案情感贫乏（无好奇/兴奋/困惑表达）
```

### 2.3 心流状态转移规则

```
SILENT(0) ──[连续3轮尝试性回答]──▶ SHALLOW(1)
SHALLOW(1) ──[连续3轮正确 + 主动推进]──▶ FLUENT(2)
FLUENT(2) ──[学生主动跨概念串联]──▶ DEEP(3)
DEEP(3) ──[长时间连续输出 + 自我纠错]──▶ IMMERSED(4)

IMMERSED(4) ──[学生主动停顿/求助]──▶ DEEP(3)
DEEP(3) ──[连续2次错误 + 核心概念卡住]──▶ SHALLOW(1)
FLUENT(2) ──[一次否定性反馈(AI侧失误)]──▶ SILENT(0) ← 回路断裂！

关键约束：一次不当的否定/说教反馈可能直接导致心流断裂。
```

---

## 三、集成点 2：L6 新增——非评判防火墙

### 3.1 六类禁止操作

```python
# 所有 L6 生成的 TeachingAction.content 必须在返回前经过此防火墙

FORBIDDEN_PATTERNS = {
    "否定性判断": [
        "不对", "你错了", "这不合理", "不是这样的",
    ],
    "评判性语言": [
        "想太多", "没必要", "太幼稚", "不成熟",
        "这很简单", "你应该知道",
    ],
    "说教式口吻": [
        "你应该", "正确做法是", "要知道",
        "记住", "你必须", "一定要",
    ],
    "话题终结": [
        "好的", "明白了", "了解了",  # 在没有自然收束时强行结束
    ],
    "外部空洞夸奖": [
        "太棒了", "你好聪明", "你真厉害", "优秀",
    ],
    "话题扭转": [
        "我们回到", "还是聊聊", "先不说这个",
    ],
}

class NonJudgmentFirewall:
    """
    所有 TeachingAction.content 生成后的最后一道关卡。
    检测到违规 → 回退到 SafeFallback 模板
    """
```

### 3.2 respond() 反馈模板的 PGFGA 化改造

```python
class PGFGARespondTemplate:
    """
    根据 correctness 和 flow_level 选择反馈模式
    """

    def generate(self, correctness: str, flow_level: int,
                 error_analysis: Optional[ErrorAnalysis],
                 concept: Concept) -> str:

        if correctness == "correct":
            return self._correct_template(flow_level)
        elif correctness == "partial":
            return self._partial_template(error_analysis, flow_level)
        else:
            return self._incorrect_template(error_analysis, flow_level)

    def _correct_template(self, flow_level: int) -> str:
        if flow_level >= FlowLevel.DEEP:
            return ""  # 沉浸状态不做任何反馈
        elif flow_level >= FlowLevel.FLUENT:
            return "[一句话点出思考亮点]。继续？"
        else:
            return "[点出具体思路]。[顺势托举]"

    def _partial_template(self, error: ErrorAnalysis, flow: int) -> str:
        return (
            f"你关于{error.surface_concept}的思考有几个对的地方，比如[具体]。"
            f"还有一个有趣的细节——{error.remediation}。你想先自己试试看吗？"
        )

    def _incorrect_template(self, error: ErrorAnalysis, flow: int) -> str:
        if flow <= FlowLevel.SHALLOW:
            return (
                f"我看到了你在认真思考这个问题。"
                f"我们换个角度——{error.remediation}。"
            )
        else:
            return (
                f"你的思考方向很有探索精神。"
                f"你觉得{error.root_concept}在这里起了什么作用？"
            )
```

---

## 四、集成点 3：SDT 三大需求的教学落地

### 4.1 自主性支持

在关键决策点提供自主选择——不强制推进，提供选项，学生决定：

1. 教学节奏："今天我们讲3个概念，还是挑1个深入讲？"
2. 学习路径："多元积分可以从格林公式开始，也可以从高斯公式开始，你觉得哪个更顺？"
3. 检测方式："你想做题检测，还是用自己的话给我讲一遍？"
4. 跳过权：学生说"这个我会"→ 立即跳过，不追问理由

### 4.2 胜任感支持

不通过外部夸奖建立胜任感，通过：
1. 精准看见："你刚才主动把一元微积分的思路迁移到多元了——这是很强的迁移能力"
2. 进步对比："对比你30分钟前的解答，你现在能直接写出偏导数的条件了"
3. 困难再框架："这个概念公认是高数中最难的5个之一，你在20分钟内就有这个理解水平相当不错"

### 4.3 归属感支持

建立"这个AI真正在听我说话"的连接感：
1. 记住并引用学生之前的表达
2. 情绪先于道理：学生表达挫折 → 先接住情绪 → 再说知识
3. 使用学生的语言：学生把梯度说成"斜度" → 在反馈中先用"斜度"，再自然引入"梯度"
4. 不"切换频道"：学生在思考方向A → 系统不应切换到方向B

---

## 五、集成点 4：正向增益回路——学习版

### 5.1 学习版增益回路

```
学生答题/解释 → AI承接思考中的价值 + 精准认可思考亮点
  → 学生获得胜任感和被理解感
  → 更愿意尝试更难的概念、更深层提问
  → 思考在表达中被梳理清晰
  → AI再次承接... (学习深度螺旋上升)
```

### 5.2 回路断裂的检测与修复

```python
class GainLoopMonitor:
    BREAK_SIGNALS = {
        "student_withdrawal":      # 学生回答变短、频率变低
        "emotional_flattening":    # 回答中好奇/兴奋/困惑标记消失
        "surface_responses":       # 全部用简单回复绕过深层次思考
        "avoidance_pattern":       # 连续跳过概念
    }

    def repair(self, break_type: BreakType) -> TeachingAction:
        """
        兴趣断裂 → 重新建联: "这个主题让你觉得无趣吗？我们可以换一个切入点"
        自信断裂 → 重建安全感: "你不需要一次答对。告诉我你的思路，哪怕是半成品"
        节奏断裂 → 降速+加深: "我们慢下来。这一个概念我们花10分钟，不急"
        情绪断裂 → 主动关怀: "你今天感觉状态不太对，要不要休息一下？"
        """
```

---

## 六、实施优先级

| Phase | 集成内容 | 工作量 |
|-------|---------|--------|
| Phase 2 (教学引擎 MVP) | 非评判防火墙 + PGFGA 化 respond() | 0.5 天 |
| Phase 3 (学习者建模) | 心流状态追踪 + SDT 信号采集 | 1 天 |
| Phase 4 (强化) | 增益回路监测 + 断裂修复 + 自主性支持 | 1 天 |

PGFGA 的集成不是架构级变更——它是对 L5 和 L6 现有设计的**行为层增强**。所有 PGFGA 逻辑都运行在 tutoring-mcp 内部，不改变 MCP Tool 签名、不改变数据库 schema。
