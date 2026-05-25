"""认知负荷在线估计 (P1 #6)。

问题（SYSTEM-AUDIT #7）：ctx.meta.current_cognitive_load 恒 0.0，于是
strategy_selector 的负荷分支（>0.6→jiangjie / >0.75→analogy/reduction）和
flow_regulator 的负荷修正（>0.7 降难度+加脚手架）永远不触发。

做法：确定性加权公式 + EMA 平滑（与 kg_full 难度校准同一哲学——无标注数据时用
可解释的加权公式，将来有学习者数据可换学习模型）。四个分量（均 0-1）：
- 内在难度 intrinsic：概念本身的 cognitive_load_estimate（认知负荷理论的 intrinsic load）
- 表现 perf：1 - 最近正确率（答错越多→负荷越高；无数据时中性 0.5）
- 受挫 struggle：当前概念上的连续失败次数 / 参考阈值（element interactivity 累积）
- 工作记忆压力 wm：前置概念数 / 工作记忆容量（同时要 hold 的元素超过容量→负荷）

引擎在每次 respond 后（数据最丰富）+ 进入新概念时更新 ctx.meta.current_cognitive_load。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

# 分量权重（和为 1）
_W_INTRINSIC = 0.35
_W_PERF = 0.35
_W_STRUGGLE = 0.20
_W_WM = 0.10

_STRUGGLE_REF = 3  # 连续失败到此次数即视为满档受挫
_EMA_ALPHA = 0.6   # 新值权重；越大越灵敏，越小越平滑

# 文本信号（设计中的 answer_length_variance / question_rephrasing_rate）
_W_TEXT_VAR = 0.5       # 答案长度波动在 text_pressure 中的权重
_W_TEXT_REPHRASE = 0.5  # 「换种说法」请求率的权重
_TEXT_BOOST = 0.15      # text_pressure 对最终负荷的最大加成（附加项，不参与基础权重）

# 学生表达「没听懂 / 换种说法」的求助信号——出现即提示理解受阻。
_REPHRASE_RE = re.compile(
    r"换(个|种)?(说法|方式|讲法)|没(听|看)懂|不(太)?(明白|懂|理解)"
    r"|再(说|讲)一(遍|次)|能不能再讲|听不懂|看不懂"
)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class TextLoadSignals:
    """从最近若干轮学生答案抽取的文本层认知负荷信号。"""

    answer_length_variance: float   # 答案长度变异系数（0-1，clamp）
    question_rephrasing_rate: float # 请求「换种说法/没听懂」的轮次占比（0-1）
    text_pressure: float            # 上述两者聚合的文本压力（0-1）


def compute_text_signals(*, recent_answers: list[str]) -> TextLoadSignals:
    """从最近答案计算文本信号。空/单条历史时返回 0 压力（不影响早期负荷）。

    - answer_length_variance：答案长度忽长忽短（变异系数高）→ 思路不稳、负荷高
    - question_rephrasing_rate：频繁请求换种说法 → 当前讲法超出理解带宽
    """
    answers = [a for a in recent_answers if isinstance(a, str)]
    n = len(answers)

    if n == 0:
        rephrase_rate = 0.0
    else:
        hits = sum(1 for a in answers if _REPHRASE_RE.search(a))
        rephrase_rate = hits / n

    lengths = [len(a) for a in answers]
    if len(lengths) < 2:
        var_norm = 0.0
    else:
        mean = sum(lengths) / len(lengths)
        if mean <= 0:
            var_norm = 0.0
        else:
            variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
            var_norm = _clamp01(math.sqrt(variance) / mean)  # 变异系数 CV，clamp 到 1

    pressure = _clamp01(_W_TEXT_VAR * var_norm + _W_TEXT_REPHRASE * rephrase_rate)
    return TextLoadSignals(
        answer_length_variance=round(var_norm, 3),
        question_rephrasing_rate=round(rephrase_rate, 3),
        text_pressure=round(pressure, 3),
    )


def estimate_load(
    *,
    intrinsic: float,
    recent_accuracy: float | None,
    struggle_count: int,
    working_memory_span: int,
    prereq_count: int,
    prev_load: float = 0.0,
    text_pressure: float | None = None,
) -> float:
    """返回 0-1 的认知负荷估计。

    prev_load>0 时与历史做 EMA 平滑，避免单轮跳变；prev_load<=0 视为首次，直接用 raw。
    text_pressure（可选，来自 compute_text_signals）作为附加项最多上抬 _TEXT_BOOST；
    不传或为 0 时结果与四分量公式完全一致（向后兼容，既有调用不受影响）。
    """
    perf = 0.5 if recent_accuracy is None else (1.0 - _clamp01(recent_accuracy))
    struggle = _clamp01(struggle_count / _STRUGGLE_REF)
    wm_span = max(1, working_memory_span)
    wm_pressure = _clamp01(prereq_count / wm_span)

    raw = (
        _W_INTRINSIC * _clamp01(intrinsic)
        + _W_PERF * perf
        + _W_STRUGGLE * struggle
        + _W_WM * wm_pressure
    )
    raw = _clamp01(raw)

    # 文本压力：仅在提供且 >0 时附加上抬（不改变基础四分量的相对权重）
    if text_pressure is not None and text_pressure > 0.0:
        raw = _clamp01(raw + _TEXT_BOOST * _clamp01(text_pressure))

    if prev_load <= 0.0:
        return round(raw, 3)
    return round(_EMA_ALPHA * raw + (1.0 - _EMA_ALPHA) * prev_load, 3)
