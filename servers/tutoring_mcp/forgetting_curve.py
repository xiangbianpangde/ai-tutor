"""L3 个性化遗忘曲线 — 简化 Wickelgren / Ebbinghaus 指数模型。

核心模型:
    R(t) = exp(-λ * t)
- R: 召回率 (0..1)
- t: 距上次复习的天数
- λ: 个性化遗忘速率（每个 user × concept 一份）

接口:
    predict_recall(λ, days)            → 0..1 召回率
    fit_lambda(points)                 → (λ, r_squared)
    recommend_review_days(λ, target)   → 几天后召回率衰减到 target

群体均值兜底 + 过渡区加权混合:
    数据 < 3 个点      → 返回 DEFAULT_LAMBDA（=0.3，约对应每天忘 26%）
    数据 3-5 个点      → λ = w·λ_fitted + (1-w)·DEFAULT_LAMBDA，w = n/10
                         （点少时不完全信任拟合，向群体均值收缩）
    数据 ≥ 6 个点      → 纯拟合值（样本足够，完全个性化）

后续切片可加:
- power-law / log-law 模型选择
- 跨概念耦合（相邻 mastered 给本概念 +recall）
- 复习强化反馈（每次成功复习降低 λ）
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import curve_fit

DEFAULT_LAMBDA: float = 0.3
_MIN_FIT_POINTS: int = 3
_FULL_TRUST_POINTS: int = 6   # ≥ 此点数用纯拟合；[3, 6) 与群体均值加权混合
_LAMBDA_LOWER: float = 0.01   # 防 λ→0 时复习推荐无穷远
_LAMBDA_UPPER: float = 3.0    # 防极端噪声拟合出爆炸值


def predict_recall(*, lambda_param: float, days_elapsed: float) -> float:
    """R(t) = exp(-λ * t)，clamp 到 [0, 1]，负 days 视为 0。"""
    t = max(0.0, float(days_elapsed))
    lam = max(0.0, float(lambda_param))
    return math.exp(-lam * t)


def fit_lambda(
    *,
    data_points: list[tuple[float, float]],
) -> tuple[float, float | None]:
    """对 (days, accuracy) 数据点拟合 R(t)=exp(-λt) 中的 λ。

    数据 < 3 点 → 返回 (DEFAULT_LAMBDA, None)
    拟合失败 → 同上 + warning
    """
    if len(data_points) < _MIN_FIT_POINTS:
        return DEFAULT_LAMBDA, None

    days = np.array([float(d) for d, _ in data_points], dtype=float)
    acc = np.array([float(a) for _, a in data_points], dtype=float)
    # accuracy 必须在 (0,1] 才能 log；clamp 一下
    acc = np.clip(acc, 1e-6, 1.0)

    def _model(t: np.ndarray, lam: float) -> np.ndarray:
        return np.exp(-lam * t)

    try:
        popt, _ = curve_fit(
            _model, days, acc,
            p0=[DEFAULT_LAMBDA],
            bounds=(_LAMBDA_LOWER, _LAMBDA_UPPER),
            maxfev=2000,
        )
    except Exception:  # noqa: BLE001 — 拟合可能因病态数据失败
        return DEFAULT_LAMBDA, None

    lam = float(popt[0])
    # R^2
    pred = _model(days, lam)
    ss_res = float(np.sum((acc - pred) ** 2))
    ss_tot = float(np.sum((acc - acc.mean()) ** 2))
    if ss_tot < 1e-12:
        r2 = 1.0 if ss_res < 1e-12 else 0.0
    else:
        r2 = max(0.0, 1.0 - ss_res / ss_tot)

    # 过渡区加权混合：点数在 [3, 6) 时拟合尚不可靠，按 w=n/10 向群体均值收缩。
    # n=3→0.3（七成信群体），n=5→0.5（半信半疑），n≥6 完全信拟合。
    # r2 仍反映原始拟合质量（诊断信号），不随混合改变。
    n = len(data_points)
    if n < _FULL_TRUST_POINTS:
        w = n / 10.0
        lam = w * lam + (1.0 - w) * DEFAULT_LAMBDA
        lam = max(_LAMBDA_LOWER, min(_LAMBDA_UPPER, lam))

    return lam, r2


def recommend_review_days(
    *,
    lambda_param: float,
    target_recall: float = 0.7,
) -> float:
    """求 R(t) = target → t = -ln(target) / λ。

    target_recall=1 → 0（立即复习）
    target_recall→0 → 很大的数（很久之后）
    """
    target = max(1e-6, min(1.0, float(target_recall)))
    if target >= 1.0 - 1e-9:
        return 0.0
    lam = max(_LAMBDA_LOWER, float(lambda_param))
    return -math.log(target) / lam
