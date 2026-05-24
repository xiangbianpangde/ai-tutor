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

# 分量权重（和为 1）
_W_INTRINSIC = 0.35
_W_PERF = 0.35
_W_STRUGGLE = 0.20
_W_WM = 0.10

_STRUGGLE_REF = 3  # 连续失败到此次数即视为满档受挫
_EMA_ALPHA = 0.6   # 新值权重；越大越灵敏，越小越平滑


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def estimate_load(
    *,
    intrinsic: float,
    recent_accuracy: float | None,
    struggle_count: int,
    working_memory_span: int,
    prereq_count: int,
    prev_load: float = 0.0,
) -> float:
    """返回 0-1 的认知负荷估计。

    prev_load>0 时与历史做 EMA 平滑，避免单轮跳变；prev_load<=0 视为首次，直接用 raw。
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

    if prev_load <= 0.0:
        return round(raw, 3)
    return round(_EMA_ALPHA * raw + (1.0 - _EMA_ALPHA) * prev_load, 3)
