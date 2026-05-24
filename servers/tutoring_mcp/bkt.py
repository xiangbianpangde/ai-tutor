"""BKT (Bayesian Knowledge Tracing) 单概念掌握度更新。

理论参考: Corbett & Anderson 1995.

公式:
  bayes posterior:
    c=1: P(m|c=1) = P*(1-slip) / (P*(1-slip) + (1-P)*guess)
    c=0: P(m|c=0) = P*slip     / (P*slip     + (1-P)*(1-guess))
  transition:
    P_new = P_post + (1 - P_post) * p_learn

输入是 BKTParams（pydantic），输出也是 BKTParams（**新对象**，原对象不变）。
"""
from __future__ import annotations

from datetime import datetime

from shared.schemas import BKTParams


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _safe_div(num: float, den: float, *, fallback: float = 0.5) -> float:
    """除数为 0 时回退到 fallback（避免极端参数下 NaN）。"""
    if den <= 1e-12:
        return fallback
    return num / den


def update(params: BKTParams, *, correct: bool) -> BKTParams:
    """根据一次观察结果更新 BKT 状态。返回新 BKTParams（不修改输入）。"""
    P = params.p_mastery
    g = params.p_guess
    s = params.p_slip
    L = params.p_learn

    if correct:
        # P(mastery | correct)
        posterior = _safe_div(
            P * (1 - s),
            P * (1 - s) + (1 - P) * g,
            fallback=P,
        )
    else:
        # P(mastery | wrong)
        posterior = _safe_div(
            P * s,
            P * s + (1 - P) * (1 - g),
            fallback=P,
        )

    # 学习转移：本次教学使一部分"还不会"的人变会
    new_mastery = posterior + (1 - posterior) * L

    return params.model_copy(
        update={
            "p_mastery": _clamp(new_mastery),
            "n_observations": params.n_observations + 1,
            "last_updated": datetime.utcnow(),
        }
    )
