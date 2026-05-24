"""学习时长估计 (P1 #8) — 替代恒定 30min。

问题（SYSTEM-AUDIT #6）：所有概念 typical_learning_time_min=30，于是 200 概念 ×30 =
100h，远超 48h，教学计划的时长完全失真、无法分时。

方案（adopted-fixes 修正 3 的两步设计）：
  第一步（本模块 estimate_time_min）：开发期没有真实答题时长数据，用可解释加权特征
    公式给初始估计——与 kg_full 难度校准同一哲学。**只用非时间特征**（认知负荷/公式密度/
    抽象度/前置数/前置深度），避免和 compute_calibrated_difficulty 的 time_norm 形成循环。
  第二步（calibrate_time）：48h 实验/真实使用收集到"实际学完某概念用时"后，把公式估计
    与观测做置信度加权（样本越多越偏向实测）。这是给时间追踪落地后用的纯函数钩子。

时长范围映射到 [TIME_MIN, TIME_MAX]，再 clamp 到 schema 的 [1,120]。
"""
from __future__ import annotations

from shared.schemas import Concept

# 时间特征权重（和为 1.0；不含 time 自身，避免与难度校准循环）
_W_LOAD = 0.30
_W_FORMULA = 0.25
_W_ABSTRACT = 0.20
_W_PREREQ = 0.15
_W_DEPTH = 0.10

_PREREQ_NORM = 8.0   # 前置数 ≥8 视为满
_DEPTH_NORM = 5.0    # 前置链深度 ≥5 视为满

_TIME_MIN = 5.0      # 最简单概念约 5min
_TIME_MAX = 45.0     # 最难单概念约 45min

_CALIB_K = 3.0       # 观测置信度的平滑常数（样本数到 K 时实测权重 0.5）


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _clamp_minutes(x: float) -> int:
    return int(round(max(1.0, min(120.0, x))))


def estimate_time_min(concept: Concept) -> int:
    """基于概念内在特征的学习时长估计（分钟，∈[1,120]）。"""
    d = concept.difficulty
    composite = (
        _W_LOAD * _clip01(d.cognitive_load_estimate)
        + _W_FORMULA * _clip01(d.formula_density)
        + _W_ABSTRACT * _clip01(concept.classification.abstract_level)
        + _W_PREREQ * _clip01(d.prereq_count / _PREREQ_NORM)
        + _W_DEPTH * _clip01(d.prereq_max_depth / _DEPTH_NORM)
    )
    minutes = _TIME_MIN + composite * (_TIME_MAX - _TIME_MIN)
    return _clamp_minutes(minutes)


def calibrate_time(*, estimated_min: int, observed_minutes: list[float]) -> int:
    """把公式估计与真实观测时长做置信度加权（样本越多越偏向实测）。

    无观测 → 原样返回估计。observed 权重 = n/(n+K)，n 越大越接近观测均值。
    供时间追踪落地后调用（当前管道尚未采集 per-concept 实际用时）。
    """
    if not observed_minutes:
        return _clamp_minutes(estimated_min)
    n = len(observed_minutes)
    mean_obs = sum(observed_minutes) / n
    w = n / (n + _CALIB_K)
    blended = (1.0 - w) * estimated_min + w * mean_obs
    return _clamp_minutes(blended)
