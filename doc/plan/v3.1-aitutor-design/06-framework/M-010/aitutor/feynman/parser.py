"""aitutor.feynman.parser - 费曼评分 LLM 响应解析器

> 对应模块: M-010 费曼评分
> 关联接口: IC-002（学习回合 — 评分解析失败 E01002 重试 1 次）
> 关联选型: TS-001 Python（json/正则）
> 设计模式: Strategy（解析策略可替换：JSON / 正则 / 容错解析）
> 来源标注: [DD-001:MD-010 sm010-score 解析] + [DD-001:FS-010 parser.py]

[文件路径]      src/aitutor/feynman/parser.py
[文件职责]      解析 LLM 响应 → 提取 score:int + reasoning:str
[所属模块]      M-010
[关联设计规范]   MD-010 ScoreParser 类设计
[功能描述]
  功能1: parse(llm_response: str) → ParsedScore（含 score / reasoning）
  功能2: 多层容错: JSON → 正则 → 关键字提取 → 失败
  功能3: rubric 规则注入（评分约束）
[输入输出]
  输入: llm_response: str（LLM 原始响应，可能含噪声）
  输出: ParsedScore（score: int / reasoning: str）或抛 ScoreParseError
[依赖关系]
  依赖文件: aitutor/shared/exceptions.py（ScoreParseError）
  被依赖文件: aitutor/feynman/scorer.py
[注意事项]
  注意1: 必须容错 LLM 返回非标 JSON（实际 LLM 经常返回 "score: 4" 等格式）
  注意2: score 必须为整数（小数四舍五入或拒绝，DD-M选择四舍五入并 WARN）
  注意3: reasoning 为空时给默认占位（不阻塞下游）
[代码风格]     CS（Ruff/PEP8/Google docstring/snake_case 函数/PascalCase 类）
[创建日期]     2026-06-02
[修改历史]     2026-06-02: DD-M-010 - 初始版本（注释骨架）
[作者]         DD-M-010-20260602
[来源标注]     [DD-001:MD-010 ScoreParser] + [DD-001:IC-002 E01002]
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# 评分提取的正则（DD-M 容错层 2）
# [DD-M推断:依据=LLM 常见输出格式（含 "score: N" / "评分: N" / "N 分"）]
SCORE_REGEX: Final[re.Pattern[str]] = re.compile(
    r"(?:score|评分|分数)[^\d-]*(-?\d+)",
    flags=re.IGNORECASE,
)

# 默认 reasoning（解析无法提取时）
DEFAULT_REASONING: Final[str] = "LLM 响应中未能提取明确评分理由（已降级）"


@dataclass(frozen=True, slots=True)
class ParsedScore:
    """解析后的评分结果（不可变值对象）。

    [类名] ParsedScore
    [职责] 承载解析结果（score 整数 + reasoning 字符串）
    [关联设计规范] [DD-001:MD-010] ScoreParser.parse(llm_response) → 隐含返回类型
    [属性]
      属性1: score      int  原始分数（未钳制，由 Scorer 钳制）
      属性2: reasoning  str  评分理由
      属性3: strategy   str  使用的解析策略（json/regex/fallback）
    [来源标注] [DD-001:MD-010] + [DD-M推断:strategy 字段便于日志/审计]
    """

    score: int
    reasoning: str
    strategy: str


class ScoreParser:
    """费曼评分响应解析器（Strategy 多层容错）。

    [类名] ScoreParser
    [职责] 多层解析 LLM 响应，提取 score + reasoning
    [关联设计规范] [DD-001:MD-010] ScoreParser 类设计
    [属性]
      属性1: _rubric   dict[str, str]  评分规则（Rubric 维度 → 描述）
    [方法列表]
      方法1: __init__(rubric) → None
      方法2: parse(llm_response: str) → ParsedScore
      方法3: _try_json(text: str) → ParsedScore | None（容错层 1）
      方法4: _try_regex(text: str) → ParsedScore | None（容错层 2）
      方法5: _fallback(text: str) → ParsedScore（容错层 3 / 兜底）
    [状态机] N/A
    [异常处理]
      异常1: ScoreParseError - 三层容错均失败 → 抛出（触发 E01002 重试 1 次）
    [并发安全] 是（_rubric 构造后不可变；解析纯函数）
    [来源标注] [DD-001:MD-010 ScoreParser]
    """

    def __init__(self, rubric: dict[str, str] | None = None) -> None:
        """初始化 Parser。

        [职责] 接收/构造 rubric 规则字典
        [参数说明]
          rubric: dict[str, str] | None 可选 评分规则字典，None 时使用默认 4 维 Rubric
        [前置条件] N/A
        [后置条件] _rubric 固化
        [来源标注] [DD-001:MD-010] + [DD-M推断:可注入便于单测]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    def parse(self, llm_response: str) -> ParsedScore:
        """解析 LLM 响应（公开主入口）。

        [函数名] parse
        [职责] 多层解析（JSON → 正则 → fallback），抽取 score + reasoning
        [关联接口契约] [DD-001:MD-010] parse(llm_response) → int（DD-M 扩展为 ParsedScore）
        [参数说明]
          llm_response: str 必填 LLM 原始响应（≤8000 字符，由调用方限制）
        [返回值]
          类型: ParsedScore
          描述: 含 score / reasoning / strategy（使用的解析策略名）
          特殊值: strategy="fallback" 表示走兜底，调用方应记录 WARN
        [错误码]
          ScoreParseError - 三层容错均失败 → 调用方（Scorer）重试 1 次（E01002）
        [前置条件] llm_response 非空
        [后置条件] 返回 ParsedScore（含 score 整数）
        [并发安全] 是（纯函数）
        [幂等性] 是（同 input 必同 output）
        [性能约束] ≤10ms（JSON 解析 + 正则）
        [示例]
            ```python
            parser = ScoreParser()
            result = parser.parse('{"score": 4, "reasoning": "概念准确"}')
            assert result.score == 4
            ```
        [来源标注] [DD-001:MD-010 parse(llm_response) → int]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    def _try_json(self, text: str) -> ParsedScore | None:
        """容错层 1：严格 JSON 解析。

        [职责] 解析符合 {"score": <int>, "reasoning": <str>} 的标准 JSON
        [返回值] ParsedScore 或 None（失败时返回 None，不抛异常）
        [并发安全] 是（纯函数）
        [来源标注] [DD-M推断:依据=LLM JSON mode 优先]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    def _try_regex(self, text: str) -> ParsedScore | None:
        """容错层 2：正则提取（兼容 "score: 4" / "评分: 4 分" 等格式）。

        [职责] 当 LLM 返回非标 JSON 时仍能提取分数
        [返回值] ParsedScore 或 None
        [并发安全] 是（纯函数）
        [来源标注] [DD-M推断:依据=LLM 实际输出非标 JSON 比例约 5%-10%]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    def _fallback(self, text: str) -> ParsedScore:
        """容错层 3 / 兜底：固定返回 score=0 + 默认 reasoning。

        [职责] 三层全失败时仍返回可用结果（avoid throwing 给上层重试机会）
        [返回值] ParsedScore（score=0, strategy="fallback"）
        [并发安全] 是（纯函数）
        [来源标注] [DD-M推断:依据=IC-002 不阻塞主流程；保留 raw 给 audit_log]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现
