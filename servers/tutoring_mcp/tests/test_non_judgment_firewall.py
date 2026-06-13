"""非评判防火墙契约测试（PGFGA 集成点 2）。

合同来源: ai-tutor-system-design/specs/pgfga-integration.md §三

约束:
- scan(text) 检测六类禁止模式：negation / judgment / preachy / topic_killer / empty_praise / topic_shift
- 命中 → 返回 FirewallViolation
- 未命中 → 返回 None
- safe_fallback(violation) → 给出回退到 PGFGA 原则的替代措辞建议
"""
from __future__ import annotations


def test_negation_pattern_caught() -> None:
    from servers.tutoring_mcp.non_judgment_firewall import NonJudgmentFirewall

    fw = NonJudgmentFirewall()
    v = fw.scan("不对，你错了。正确答案是 X。")
    assert v is not None
    assert v.category == "negation"
    assert "不对" in v.matched_pattern or "错了" in v.matched_pattern


def test_empty_praise_caught() -> None:
    from servers.tutoring_mcp.non_judgment_firewall import NonJudgmentFirewall

    fw = NonJudgmentFirewall()
    v = fw.scan("太棒了！你好聪明！")
    assert v is not None
    assert v.category == "empty_praise"


def test_preachy_pattern_caught() -> None:
    from servers.tutoring_mcp.non_judgment_firewall import NonJudgmentFirewall

    fw = NonJudgmentFirewall()
    v = fw.scan("你应该多练习，要知道这个很重要。")
    assert v is not None
    assert v.category == "preachy"


def test_neutral_text_passes() -> None:
    from servers.tutoring_mcp.non_judgment_firewall import NonJudgmentFirewall

    fw = NonJudgmentFirewall()
    assert fw.scan("你刚才主动把一元微积分的思路迁移到多元了，这是很强的能力。") is None
    assert fw.scan("我们继续看下一个概念。") is None
    assert fw.scan("") is None


def test_violation_has_fallback_suggestion() -> None:
    from servers.tutoring_mcp.non_judgment_firewall import NonJudgmentFirewall

    fw = NonJudgmentFirewall()
    v = fw.scan("不对。")
    assert v is not None
    assert v.suggested_fallback  # 必须有非空建议


def test_scan_first_returns_first_match_only() -> None:
    """文本里多个违规时，scan 返回第一个；想要全部用 scan_all。"""
    from servers.tutoring_mcp.non_judgment_firewall import NonJudgmentFirewall

    fw = NonJudgmentFirewall()
    text = "不对。太棒了！"
    v = fw.scan(text)
    assert v is not None
    all_violations = fw.scan_all(text)
    assert len(all_violations) >= 2
