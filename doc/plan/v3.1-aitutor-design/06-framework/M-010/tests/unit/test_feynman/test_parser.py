"""tests.unit.test_feynman.test_parser - ScoreParser 单元测试

> 对应模块: M-010
> 被测文件: aitutor/feynman/parser.py
> 测试用例数: 2（核心 1 + 容错 1）
> 来源标注: [DD-001:MD-010 测试策略]

[文件路径]      tests/unit/test_feynman/test_parser.py
[文件职责]      验证 ScoreParser 多层容错解析
[所属模块]      M-010
[创建日期]     2026-06-02
[作者]         DD-M-010-20260602
"""
from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected_score,expected_strategy",
    [
        ('{"score": 4, "reasoning": "ok"}', 4, "json"),
        ("score: 3 - 还可以", 3, "regex"),
    ],
)
def test_parse_supports_json_and_regex(
    raw: str, expected_score: int, expected_strategy: str
) -> None:
    """[测试场景 1: 多格式解析 - JSON 和 Regex 都能命中]
    [被测函数] ScoreParser.parse / _try_json / _try_regex
    [输入] 参数化两种格式
    [Mock] 无
    [断言]
      - result.score == expected_score
      - result.strategy == expected_strategy
      - result.reasoning 非空
    [覆盖] 容错层 1 + 容错层 2
    [来源标注] [DD-001:MD-010 parse(llm_response)]
    """
    raise NotImplementedError  # 由 DD-S/DEV 实现


@pytest.mark.unit
def test_parse_fallback_on_garbage() -> None:
    """[测试场景 2: 三层容错全失败 - fallback 路径]
    [被测函数] ScoreParser.parse / _fallback
    [输入] raw="完全没有分数的随机文本"
    [Mock] 无
    [断言]
      - result.score == 0
      - result.strategy == "fallback"
      - result.reasoning == DEFAULT_REASONING
      - 不抛异常（由上层 Scorer 决定是否重试）
    [覆盖] 容错层 3 / 兜底
    [来源标注] [DD-001:MD-010 E01002] + [DD-M推断:fallback 不抛便于上层重试控制]
    """
    raise NotImplementedError  # 由 DD-S/DEV 实现
