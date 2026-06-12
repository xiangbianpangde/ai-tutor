# 接口注释清单 — M-010 费曼评分

> 关联接口契约: IC-002（学习回合 — 评分子流程）；M-010 不直接对外暴露 HTTP API，仅供 M-009 内部调用
> 作者: DD-M-010-20260602
> 来源标注: [DD-001:IC-002] + [DD-001:MD-010 函数签名] + [DD-M-010 推断]

---

## API-M-010-01 score_feynman（公开主接口）

| 项 | 值 |
|----|----|
| 接口编号 | API-M-010-01 |
| 关联契约 | IC-002（嵌套调用：M-009 → M-010 → M-007 LLM Stage） |
| 实现文件 | `src/aitutor/feynman/scorer.py` |
| 类 | `FeynmanScorer` |
| 函数 | `async def score_feynman(self, question: str, user_answer: str) -> FeynmanScore` |

**函数签名注释：**

```python
async def score_feynman(
    self,
    question: str,    # 教师/系统问题，非空，长度 [1, 2000]
    user_answer: str, # 用户费曼式回答，非空，长度 [1, 2000]
) -> FeynmanScore:    # 评分结果（score/reasoning/raw/degraded）
    """对用户的费曼式回答进行评分。

    Args:
        question: 教师/系统问题（长度 [1, 2000]）。
        user_answer: 用户的费曼式解释（长度 [1, 2000]）。

    Returns:
        FeynmanScore: 含 score ∈ [0, 5] / reasoning / raw / degraded。

    Raises:
        LLMUnavailableError: 触发 E01001；调用方应将 degraded 视为兜底信号。
        ScoreParseError:     触发 E01002（仅在重试 1 次仍失败时抛出）。

    Example:
        >>> scorer = build_feynman_scorer()
        >>> result = await scorer.score_feynman("Q", "A")
        >>> assert 0 <= result.score <= 5
    """
```

**契约要素：**

| 要素 | 值 |
|------|----|
| 入参完整 | ✅ |
| 出参完整 | ✅ |
| 错误码 | E01001 / E01002 / 上传至 IC-002 E00901 |
| 前置条件 | question / user_answer 均非空 |
| 后置条件 | 返回 score ∈ [0, 5]，degraded 字段标记是否走兜底 |
| 并发安全 | 是 |
| 幂等性 | 语义幂等（LLM 输出非确定，但语义稳定） |
| 性能约束 | P95 ≤1500ms（来自 IC-002 5s 单回合预算分摊） |
| 来源标注 | [DD-001:MD-010] + [DD-001:IC-002 E00901 兜底] |

---

## API-M-010-02 build（PromptBuilder.build）

| 项 | 值 |
|----|----|
| 接口编号 | API-M-010-02 |
| 关联契约 | [DD-001:MD-010 函数签名 build_prompt(question, user_answer) → str] |
| 实现文件 | `src/aitutor/feynman/prompt.py` |
| 类 | `FeynmanPromptBuilder` |
| 函数 | `def build(self, question: str, user_answer: str) -> str` |

**函数签名注释：**

```python
def build(
    self,
    question: str,    # 教师问题，非空
    user_answer: str, # 用户回答，非空
) -> str:             # 完整 Prompt（含 system + Rubric + user 段）
    """渲染费曼评分 Prompt。

    Args:
        question: 教师/系统问题。
        user_answer: 用户回答（内部经 _sanitize 注入防御）。

    Returns:
        str: 完整 Prompt 字符串，长度 ≤8000 字符。

    Raises:
        PromptTemplateError: 自定义模板缺少必需占位符。
    """
```

**契约要素：**

| 要素 | 值 |
|------|----|
| 入参完整 | ✅ |
| 出参完整 | ✅ |
| 错误码 | PromptTemplateError |
| 前置条件 | 模板含 {question} 与 {user_answer} 占位 |
| 后置条件 | 占位符全部替换，user_answer 经清洗 |
| 并发安全 | 是（纯函数） |
| 幂等性 | 是（同 input 必同 output） |
| 性能约束 | ≤5ms |
| 来源标注 | [DD-001:MD-010 build(question, user_answer)] + [DD-M推断:_sanitize] |

---

## API-M-010-03 parse（ScoreParser.parse）

| 项 | 值 |
|----|----|
| 接口编号 | API-M-010-03 |
| 关联契约 | [DD-001:MD-010 函数签名 parse_score(llm_response) → int]（DD-M 扩展为 ParsedScore） |
| 实现文件 | `src/aitutor/feynman/parser.py` |
| 类 | `ScoreParser` |
| 函数 | `def parse(self, llm_response: str) -> ParsedScore` |

**函数签名注释：**

```python
def parse(
    self,
    llm_response: str,  # LLM 原始响应，非空，≤8000 字符
) -> ParsedScore:        # 含 score（未钳制）/ reasoning / strategy
    """解析 LLM 响应抽取评分（三层容错）。

    Args:
        llm_response: LLM 原始输出。

    Returns:
        ParsedScore: 含 score / reasoning / strategy（json|regex|fallback）。

    Raises:
        ScoreParseError: 极端情况下三层全失败且 fallback 被禁用。
    """
```

**契约要素：**

| 要素 | 值 |
|------|----|
| 入参完整 | ✅ |
| 出参完整 | ✅（DD-M 扩展返回类型，向 DD-001 反馈优化建议） |
| 错误码 | ScoreParseError（E01002 重试触发条件） |
| 前置条件 | llm_response 非空 |
| 后置条件 | 返回 ParsedScore；strategy 字段可观测 |
| 并发安全 | 是 |
| 幂等性 | 是 |
| 性能约束 | ≤10ms |
| 来源标注 | [DD-001:MD-010 parse_score] + [DD-M推断:扩展返回类型便于审计] |

---

## API-M-010-04 build_feynman_scorer（工厂函数）

| 项 | 值 |
|----|----|
| 接口编号 | API-M-010-04 |
| 关联契约 | [DD-M推断:依据=DI 装配] |
| 实现文件 | `src/aitutor/feynman/__init__.py` |
| 函数 | `def build_feynman_scorer(prompt_template=None, score_range=(0,5)) -> FeynmanScorer` |

**契约要素：**

| 要素 | 值 |
|------|----|
| 入参完整 | ✅ |
| 出参完整 | ✅ |
| 前置条件 | 无 |
| 后置条件 | 返回可立即调用的 FeynmanScorer |
| 并发安全 | 是 |
| 来源标注 | [DD-001:MD-010 类协作] + [DD-M推断:工厂封装 DI] |

---

## 接口注释覆盖统计

| 设计规范来源 | 公开接口数 | 已注释数 | 覆盖率 |
|--------------|-----------|---------|--------|
| MD-010 score_feynman | 1 | 1 | 100% |
| MD-010 build_prompt | 1 | 1 | 100% |
| MD-010 parse_score | 1 | 1 | 100% |
| DD-M 工厂函数 | 1 | 1 | 100% |
| **合计** | **4** | **4** | **100%** |

**接口契约 IC-002 在 M-010 范围内的注释化率：** 100%（E00901 兜底语义已在 score_feynman 返回值 + degraded 字段中显式体现）。

---

来源标注：[DD-001:IC-002] + [DD-001:MD-010] + [DD-M-010 推断]
