"""遗忘曲线模型契约测试。

Wickelgren / 简化版 Ebbinghaus 指数衰减：
    R(t) = exp(-λ * t)
- t 单位：天
- λ：个性化遗忘速率（越大忘得越快）
- 默认 λ_init = 0.3（24h 后召回率 ≈ 0.74）

接口:
    predict_recall(lambda_param, days_elapsed) -> float
    fit_lambda(data_points: list[(days, accuracy)]) -> (lambda, r_squared)
        数据 < 3 个点 → 返回 (默认 lambda, None)
"""
from __future__ import annotations

import math

import pytest


def test_predict_recall_at_zero_is_one() -> None:
    from servers.tutoring_mcp.forgetting_curve import predict_recall

    assert predict_recall(lambda_param=0.3, days_elapsed=0.0) == pytest.approx(1.0)


def test_predict_recall_decays_over_time() -> None:
    from servers.tutoring_mcp.forgetting_curve import predict_recall

    r0 = predict_recall(lambda_param=0.3, days_elapsed=0.0)
    r1 = predict_recall(lambda_param=0.3, days_elapsed=1.0)
    r7 = predict_recall(lambda_param=0.3, days_elapsed=7.0)
    assert 1.0 == r0 > r1 > r7 > 0.0


def test_predict_recall_matches_exponential() -> None:
    from servers.tutoring_mcp.forgetting_curve import predict_recall

    assert predict_recall(lambda_param=0.5, days_elapsed=2.0) == pytest.approx(math.exp(-1.0))


def test_higher_lambda_means_faster_forgetting() -> None:
    from servers.tutoring_mcp.forgetting_curve import predict_recall

    slow = predict_recall(lambda_param=0.1, days_elapsed=3.0)
    fast = predict_recall(lambda_param=0.8, days_elapsed=3.0)
    assert slow > fast


def test_predict_recall_clamps_negative_days_to_zero() -> None:
    """负 days 不合法但不应抛错；返回 1.0（视为刚学过）。"""
    from servers.tutoring_mcp.forgetting_curve import predict_recall

    assert predict_recall(lambda_param=0.3, days_elapsed=-1.0) == pytest.approx(1.0)


def test_fit_lambda_with_few_points_returns_default() -> None:
    """数据 < 3 点 → 默认 lambda + r_squared=None。"""
    from servers.tutoring_mcp.forgetting_curve import (
        DEFAULT_LAMBDA,
        fit_lambda,
    )

    lam, r2 = fit_lambda(data_points=[])
    assert lam == DEFAULT_LAMBDA
    assert r2 is None

    lam2, _ = fit_lambda(data_points=[(1.0, 0.8), (3.0, 0.5)])
    assert lam2 == DEFAULT_LAMBDA  # 仍按默认


def test_fit_lambda_recovers_true_lambda() -> None:
    """生成 R(t)=exp(-0.4t) 的合成数据（6 点，满足完全信任阈值），fit 应回归到 ~0.4。"""
    from servers.tutoring_mcp.forgetting_curve import fit_lambda

    true_lam = 0.4
    days = [0.5, 1.0, 2.0, 3.5, 7.0, 14.0]  # 6 点 → 纯拟合，不混合
    accuracies = [math.exp(-true_lam * t) for t in days]
    lam, r2 = fit_lambda(data_points=list(zip(days, accuracies, strict=False)))
    assert lam == pytest.approx(true_lam, abs=0.05)
    assert r2 is not None
    assert r2 > 0.95  # 几乎完美拟合


@pytest.mark.parametrize("n_points,expected_w", [(3, 0.3), (4, 0.4), (5, 0.5)])
def test_fit_lambda_blends_toward_default_in_transition_zone(
    n_points: int, expected_w: float
) -> None:
    """3-5 点过渡区：返回值应等于 w·λ_fitted + (1-w)·DEFAULT，w=n/10。

    用真 λ=1.0（远离 DEFAULT=0.3）的合成数据，使混合效果明显可测。
    """
    from servers.tutoring_mcp.forgetting_curve import DEFAULT_LAMBDA, fit_lambda

    true_lam = 1.0
    all_days = [0.5, 1.0, 2.0, 3.5, 7.0]
    days = all_days[:n_points]
    accuracies = [math.exp(-true_lam * t) for t in days]
    lam, _ = fit_lambda(data_points=list(zip(days, accuracies, strict=False)))

    # 干净合成数据下 λ_fitted≈true_lam，故混合后应落在 default 与 true 之间，
    # 且约等于 w·true + (1-w)·default。
    blended_expected = expected_w * true_lam + (1.0 - expected_w) * DEFAULT_LAMBDA
    assert lam == pytest.approx(blended_expected, abs=0.05)
    # 混合值必严格介于群体均值与纯拟合值之间
    assert DEFAULT_LAMBDA < lam < true_lam


def test_fit_lambda_six_points_no_blend() -> None:
    """边界：恰好 6 点 → 纯拟合，不向 DEFAULT 收缩。"""
    from servers.tutoring_mcp.forgetting_curve import DEFAULT_LAMBDA, fit_lambda

    true_lam = 1.0
    days = [0.5, 1.0, 2.0, 3.5, 7.0, 14.0]
    accuracies = [math.exp(-true_lam * t) for t in days]
    lam, _ = fit_lambda(data_points=list(zip(days, accuracies, strict=False)))
    assert lam == pytest.approx(true_lam, abs=0.05)
    assert lam > DEFAULT_LAMBDA + 0.3  # 明显未被拉向 0.3


def test_fit_lambda_handles_noisy_data() -> None:
    """带噪声的数据应给出合理 λ + r_squared < 1。"""
    from servers.tutoring_mcp.forgetting_curve import fit_lambda

    # 主体衰减 + 一些偏差
    points = [(1, 0.85), (3, 0.55), (7, 0.30), (14, 0.18), (21, 0.10)]
    lam, r2 = fit_lambda(data_points=points)
    assert 0.05 < lam < 1.5
    assert r2 is not None
    assert 0.0 <= r2 <= 1.0


def test_fit_lambda_clamps_lambda_to_safe_range() -> None:
    """病态输入下 λ 不能爆炸/负值。"""
    from servers.tutoring_mcp.forgetting_curve import fit_lambda

    # 5 天后召回率还是 0.99 → 真 λ 极小，但实现应 clamp 到合理下限
    points = [(1, 0.999), (5, 0.99), (10, 0.999)]
    lam, _ = fit_lambda(data_points=points)
    assert lam > 0.0  # 至少不能负
    assert lam < 5.0  # 也不能爆


def test_next_review_at_higher_lambda_sooner() -> None:
    """同 mastery 目标，λ 高 → 推荐复习时间更早。"""
    from servers.tutoring_mcp.forgetting_curve import recommend_review_days

    fast_forget = recommend_review_days(lambda_param=0.8, target_recall=0.7)
    slow_forget = recommend_review_days(lambda_param=0.1, target_recall=0.7)
    assert fast_forget < slow_forget
    assert fast_forget > 0


def test_recommend_review_days_target_recall_at_unit() -> None:
    """target_recall=1 → 立即复习（0 天）；target_recall→0 → 很久之后。"""
    from servers.tutoring_mcp.forgetting_curve import recommend_review_days

    assert recommend_review_days(lambda_param=0.3, target_recall=1.0) == pytest.approx(0.0, abs=1e-6)
    far = recommend_review_days(lambda_param=0.3, target_recall=0.01)
    soon = recommend_review_days(lambda_param=0.3, target_recall=0.5)
    assert far > soon
