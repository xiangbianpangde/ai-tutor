"""aitutor.feynman.prompt - 费曼评分 Prompt 模板构造器

> 对应模块: M-010 费曼评分
> 关联接口: IC-002（学习回合 — 评分环节）
> 关联选型: TS-001 Python（模板字符串）
> 设计模式: Strategy（同一模板抽象下可替换 / Builder 思想）
> 来源标注: [DD-001:MD-010 sm010-prompt] + [DD-001:FS-010]

[文件路径]      src/aitutor/feynman/prompt.py
[文件职责]      实现 FeynmanPromptBuilder，将 question + user_answer 装配为 LLM Prompt
[所属模块]      M-010
[关联设计规范]   MD-010 类设计 / FS-010 文件依赖
[功能描述]
  功能1: 默认费曼评分 Prompt 模板（Rubric: 表达清晰度/概念准确性/类比恰当性/深度）
  功能2: 模板参数化 build(question, user_answer) → 完整 Prompt
  功能3: 支持自定义模板（DI 注入）
[输入输出]
  输入: question: str / user_answer: str / 可选 template: str
  输出: 完整 Prompt 字符串（≤ LLM context window）
[依赖关系]
  依赖文件: aitutor/shared/types.py（DD-M推断: 类型别名 PromptStr）
  被依赖文件: aitutor/feynman/scorer.py
[注意事项]
  注意1: 必须对 user_answer 做 prompt-injection 防御（CS 8. 安全规范）
  注意2: 模板版本化 → 升级 LLM 时回归测试
  注意3: 严格区分 system / user 段（避免越权指令）
[代码风格]     CS（Ruff/PEP8/Google docstring/snake_case 函数/PascalCase 类）
[创建日期]     2026-06-02
[修改历史]     2026-06-02: DD-M-010 - 初始版本（注释骨架）
[作者]         DD-M-010-20260602
[来源标注]     [DD-001:MD-010 sm010-prompt] + [DD-001:FS-010 prompt.py]
"""
from __future__ import annotations

from typing import Final

# 默认 Prompt 模板（Rubric 评分 0-5）
# [DD-M推断:依据=MD-010 ScoreParser.rubric 属性 + 费曼学习法通用评估维度]
# [来源标注] [DD-M推断:依据=费曼学习法四维评估 + IC-002 评分语义]
DEFAULT_FEYNMAN_PROMPT_TEMPLATE: Final[str] = (
    "你是一名严格的费曼学习法评分官。请按 0-5 整数评分：\n"
    "0 = 完全错误 / 5 = 完美\n"
    "评估维度: 表达清晰度 / 概念准确性 / 类比恰当性 / 深度\n"
    "\n"
    "[问题]\n{question}\n"
    "\n"
    "[用户回答]\n{user_answer}\n"
    "\n"
    "请仅以 JSON 输出: {{\"score\": <int>, \"reasoning\": <str>}}\n"
)

# 防注入分隔符（DD-M 安全洞察）
# [DD-M推断:依据=CS 8 安全规范 + 调研报告 prompt injection 防御]
USER_INPUT_DELIMITER: Final[str] = "---USER-INPUT-START---"
USER_INPUT_END_DELIMITER: Final[str] = "---USER-INPUT-END---"


class FeynmanPromptBuilder:
    """费曼评分 Prompt 构造器（Builder 思想）。

    [类名] FeynmanPromptBuilder
    [职责] 将 question + user_answer 渲染为完整 LLM Prompt
    [关联设计规范] [DD-001:MD-010] FeynmanPromptBuilder 类设计
    [属性]
      属性1: _template   str  Prompt 模板（带 {question} / {user_answer} 占位）
    [方法列表]
      方法1: __init__(template: str | None) → None
      方法2: build(question: str, user_answer: str) → str
      方法3: _sanitize(text: str) → str（DD-M推断：注入防御）
    [状态机] N/A
    [异常处理]
      异常1: PromptTemplateError - 模板缺少必需占位符时抛出
    [并发安全] 是（构造后 _template 不可变）
    [来源标注] [DD-001:MD-010 FeynmanPromptBuilder]
    """

    def __init__(self, template: str | None = None) -> None:
        """初始化 PromptBuilder。

        [职责] 接收模板（None 时使用 DEFAULT_FEYNMAN_PROMPT_TEMPLATE）
        [参数说明]
          template: str | None 可选 自定义模板，必须包含 {question} 和 {user_answer}
        [前置条件] 若 template 非 None，必须含两个占位符
        [后置条件] _template 固化
        [错误码] PromptTemplateError 模板格式非法
        [来源标注] [DD-001:MD-010] + [DD-M推断:支持自定义模板 DI]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    def build(self, question: str, user_answer: str) -> str:
        """渲染 Prompt（公开主方法）。

        [函数名] build
        [职责] 模板渲染 + 输入清洗 → 返回完整 Prompt
        [关联接口契约] [DD-001:MD-010] build(question, user_answer) → str
        [参数说明]
          question:    str 必填 教师问题（长度 [1, 2000]）
          user_answer: str 必填 用户费曼式回答（长度 [1, 2000]）
        [返回值]
          类型: str
          描述: 完整 Prompt（含 system + user 段 + Rubric）
          特殊值: 总长度 ≤8000 字符（默认 LLM context safe margin）
        [错误码]
          PromptTemplateError - 渲染时占位符替换失败
        [前置条件] question / user_answer 均非空（由调用方保证）
        [后置条件] 返回 Prompt 字符串
        [并发安全] 是（纯函数）
        [幂等性] 是（同 input 必返回同 output）
        [性能约束] ≤5ms（纯字符串拼接）
        [示例]
            ```python
            builder = FeynmanPromptBuilder()
            prompt = builder.build(
                question="解释牛顿第二定律",
                user_answer="力=质量*加速度",
            )
            assert "牛顿第二定律" in prompt
            ```
        [来源标注] [DD-001:MD-010 build(question, user_answer)]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    def _sanitize(self, text: str) -> str:
        """私有：用户输入清洗（防 prompt injection）。

        [职责] 去除/转义可能误导 LLM 的指令片段
        [参数说明] text: str 用户原始输入
        [返回值] 清洗后的安全文本
        [并发安全] 是（纯函数）
        [来源标注] [DD-M推断:依据=CS 8 安全规范 + LLM prompt injection 防御]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现
