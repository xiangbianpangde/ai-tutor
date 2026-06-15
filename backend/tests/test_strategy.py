"""C4 策略升级测试：M-010 费曼评分 / M-011 FSRS / M-012 阶段校准 + REST。

纯计算模块，不碰网络/LLM/演示资产；REST 用 TestClient。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig
from backend.strategy import (
    Card,
    FeynmanScorer,
    FSRSScheduler,
    Rating,
    StageCalibrator,
    get_default_scheduler,
)


@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(_env_file=None, db_path=tmp_path / "t.db")
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c


# ----------------------------- M-010 费曼 -----------------------------

DEF = "梯度下降是一种沿负梯度方向迭代最小化损失函数的优化方法"


def test_feynman_empty_explanation_fails():
    res = FeynmanScorer().score(explanation="", concept_name="梯度下降", definition=DEF)
    assert res.passed is False
    assert res.coverage == 0.0


def test_feynman_good_coverage_passes():
    expl = "就是顺着坡度往下走，一步步把误差降到最小，朝梯度反方向挪"
    res = FeynmanScorer().score(explanation=expl, concept_name="梯度下降", definition=DEF)
    assert res.coverage > 0
    assert res.method == "heuristic"


def test_feynman_detects_parroting():
    """逐字背定义 → is_parroting，passed=False。"""
    res = FeynmanScorer().score(explanation=DEF, concept_name="梯度下降", definition=DEF)
    assert res.is_parroting is True
    assert res.passed is False


def test_feynman_heuristic_score_capped():
    expl = "沿负梯度方向迭代最小化损失函数优化"
    res = FeynmanScorer().score(explanation=expl, concept_name="梯度下降", definition=DEF)
    assert res.score <= 0.6  # 启发式封顶


def test_feynman_llm_judge_priority():
    def judge(explanation, concept_name, key_terms):
        return {"score": 0.95, "passed": True, "coverage": 0.9, "gaps": []}

    res = FeynmanScorer(llm_judge=judge).score(
        explanation="x", concept_name="c", definition=DEF)
    assert res.method == "llm"
    assert res.score == 0.95


# ----------------------------- M-011 FSRS -----------------------------

def test_fsrs_new_card_first_review():
    sched = FSRSScheduler()
    res = sched.review(Card(), Rating.GOOD, now=datetime(2026, 1, 1))
    assert res.card.state == "review"
    assert res.card.stability is not None and res.card.stability > 0
    assert res.interval_days >= 1
    assert res.card.reps == 1


def test_fsrs_easy_longer_than_again():
    sched = FSRSScheduler()
    now = datetime(2026, 1, 1)
    easy = sched.review(Card(), Rating.EASY, now=now)
    again = sched.review(Card(), Rating.AGAIN, now=now)
    assert easy.interval_days >= again.interval_days


def test_fsrs_retrievability_decays():
    sched = FSRSScheduler()
    r0 = sched.retrievability(0, 10)
    r10 = sched.retrievability(10, 10)
    r100 = sched.retrievability(100, 10)
    assert r0 == pytest.approx(1.0, abs=1e-6)
    assert r0 > r10 > r100 > 0


def test_fsrs_lapse_increments_and_resets():
    sched = FSRSScheduler()
    now = datetime(2026, 1, 1)
    good = sched.review(Card(), Rating.GOOD, now=now)
    # 一段时间后忘了
    later = now + timedelta(days=good.interval_days)
    lapse = sched.review(good.card, Rating.AGAIN, now=later)
    assert lapse.card.lapses == 1
    assert lapse.card.stability <= good.card.stability  # 遗忘后稳定性不增


def test_fsrs_singleton():
    assert get_default_scheduler() is get_default_scheduler()


def test_fsrs_invalid_weights():
    with pytest.raises(ValueError):
        FSRSScheduler(weights=(0.1, 0.2))


# ----------------------------- M-012 阶段校准 -----------------------------

def test_stage_holds_when_insufficient_samples():
    cal = StageCalibrator()
    cal.record(0.95)
    out = cal.recommend(0)
    assert out["action"] == "hold"  # 样本不足滞回


def test_stage_up_on_sustained_high():
    cal = StageCalibrator()
    for _ in range(5):
        cal.record(0.9)
    out = cal.recommend(0)
    assert out["action"] == "up"
    assert out["recommended_stage"] == 1


def test_stage_down_on_sustained_low():
    cal = StageCalibrator()
    for _ in range(5):
        cal.record(0.2)
    out = cal.recommend(1)
    assert out["action"] == "down"
    assert out["recommended_stage"] == 0


def test_stage_hold_in_hysteresis_band():
    cal = StageCalibrator()
    for _ in range(5):
        cal.record(0.6)
    out = cal.recommend(1)
    assert out["action"] == "hold"


def test_stage_clamps_at_max():
    cal = StageCalibrator()
    for _ in range(5):
        cal.record(1.0)
    out = cal.recommend(2)
    assert out["recommended_stage"] == 2  # 已最高，不越界


# ----------------------------- REST -----------------------------

def test_rest_feynman(client):
    r = client.post("/api/tutoring/feynman/score", json={
        "explanation": "顺着坡往下走把误差降到最低",
        "concept_name": "梯度下降", "definition": DEF,
    })
    assert r.status_code == 200
    assert "coverage" in r.json()["data"]


def test_rest_fsrs_new_card(client):
    r = client.post("/api/tutoring/review/schedule", json={"rating": 3})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["interval_days"] >= 1
    assert data["card"]["state"] == "review"


def test_rest_fsrs_followup(client):
    first = client.post("/api/tutoring/review/schedule", json={"rating": 3}).json()["data"]
    second = client.post("/api/tutoring/review/schedule",
                         json={"rating": 4, "card": first["card"]})
    assert second.status_code == 200
    assert second.json()["data"]["card"]["reps"] == 2


def test_rest_stage_calibrate(client):
    r = client.post("/api/tutoring/stage/calibrate",
                    json={"scores": [0.9, 0.9, 0.9, 0.9, 0.9], "current_stage": 0})
    assert r.status_code == 200
    assert r.json()["data"]["action"] == "up"
