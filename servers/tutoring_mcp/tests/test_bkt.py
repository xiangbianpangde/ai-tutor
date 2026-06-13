"""BKT 贝叶斯知识追踪契约测试。

理论参考: Corbett & Anderson 1995。
四个参数:
  p_init   — 学习前掌握度
  p_learn  — 一次教学后从"不会"→"会"的转移概率
  p_guess  — 不会但猜对的概率
  p_slip   — 会但答错的概率

观察 c (1=对/0=错) 后的更新:
  bayes posterior:
    c=1: P(mastery|correct) = P*(1-slip) / (P*(1-slip) + (1-P)*guess)
    c=0: P(mastery|wrong)   = P*slip / (P*slip + (1-P)*(1-guess))
  transition:
    P_new = P_post + (1 - P_post) * p_learn
"""
from __future__ import annotations

from shared.schemas import BKTParams


def _p() -> BKTParams:
    return BKTParams(concept_id="x:1.1:a")  # 默认参数


def test_update_correct_raises_mastery() -> None:
    from servers.tutoring_mcp.bkt import update

    before = _p()
    after = update(before, correct=True)
    assert after.p_mastery > before.p_mastery
    assert after.n_observations == 1
    assert after.last_updated is not None


def test_update_incorrect_lowers_posterior_then_learn_recovers_partly() -> None:
    """答错先把后验拉低，再由 p_learn 微涨。整体应小于答对版。"""
    from servers.tutoring_mcp.bkt import update

    wrong = update(_p(), correct=False)
    right = update(_p(), correct=True)
    assert wrong.p_mastery < right.p_mastery


def test_many_correct_approaches_one() -> None:
    from servers.tutoring_mcp.bkt import update

    p = _p()
    for _ in range(30):
        p = update(p, correct=True)
    assert p.p_mastery > 0.99
    assert p.n_observations == 30


def test_many_wrong_stays_low_but_above_zero() -> None:
    """连续答错时 p_learn>0 保证 mastery 不会塌到 0。"""
    from servers.tutoring_mcp.bkt import update

    p = _p()
    for _ in range(30):
        p = update(p, correct=False)
    # p_learn=0.15 兜底，下限大约在 p_learn 量级
    assert 0.0 < p.p_mastery < 0.5


def test_high_guess_dampens_single_correct() -> None:
    """p_guess 接近 1 时，一次答对几乎不提供信息。"""
    from servers.tutoring_mcp.bkt import update

    high_guess = BKTParams(concept_id="x:1.1:a", p_guess=0.95, p_learn=0.01)
    normal = BKTParams(concept_id="x:1.1:a")
    delta_high = update(high_guess, correct=True).p_mastery - high_guess.p_mastery
    delta_normal = update(normal, correct=True).p_mastery - normal.p_mastery
    assert delta_high < delta_normal


def test_high_slip_dampens_single_wrong() -> None:
    """p_slip 接近 1 时，一次答错也不算很负面（学生'手抖'）。"""
    from servers.tutoring_mcp.bkt import update

    high_slip = BKTParams(concept_id="x:1.1:a", p_slip=0.7, p_mastery=0.8)
    drop_high = high_slip.p_mastery - update(high_slip, correct=False).p_mastery

    low_slip = BKTParams(concept_id="x:1.1:a", p_slip=0.05, p_mastery=0.8)
    drop_low = low_slip.p_mastery - update(low_slip, correct=False).p_mastery

    assert drop_high < drop_low


def test_n_observations_accumulates() -> None:
    from servers.tutoring_mcp.bkt import update

    p = _p()
    for _ in range(5):
        p = update(p, correct=True)
    assert p.n_observations == 5


def test_last_updated_is_monotonic() -> None:
    from servers.tutoring_mcp.bkt import update

    p1 = update(_p(), correct=True)
    p2 = update(p1, correct=True)
    assert p2.last_updated is not None
    assert p1.last_updated is not None
    assert p2.last_updated >= p1.last_updated


def test_p_mastery_stays_in_unit_interval() -> None:
    """fuzzing：任何参数组合下 p_mastery 都应该 ∈ [0,1]。"""
    from servers.tutoring_mcp.bkt import update

    edge_cases = [
        BKTParams(concept_id="x:1.1:a", p_mastery=0.0),
        BKTParams(concept_id="x:1.1:a", p_mastery=1.0),
        BKTParams(concept_id="x:1.1:a", p_guess=0.0, p_slip=0.0),
        BKTParams(concept_id="x:1.1:a", p_guess=0.5, p_slip=0.5, p_learn=0.5),
    ]
    for p in edge_cases:
        for correct in (True, False):
            updated = update(p, correct=correct)
            assert 0.0 <= updated.p_mastery <= 1.0, f"out of range: {updated.p_mastery}"


def test_update_does_not_mutate_input() -> None:
    """update 必须返回新对象，不能改输入。"""
    from servers.tutoring_mcp.bkt import update

    p = _p()
    original_mastery = p.p_mastery
    _ = update(p, correct=True)
    assert p.p_mastery == original_mastery
    assert p.n_observations == 0
