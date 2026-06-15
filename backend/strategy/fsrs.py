"""backend.strategy.fsrs —— FSRS-5 间隔重复调度（M-011，对应 v2 #10 拆分）。

设计包 FDR-M011 要 py-fsrs 单例。py-fsrs 未安装且死代理下装不上——FSRS-5 算法本身完全
公开、纯数学，**纯 Python 实现**（无外部依赖，确定性，可测）。相对 v1 forgetting_curve
的单参指数衰减，FSRS 维护每卡 (stability, difficulty) 双状态，是现代遗忘曲线升级。

FDR-M011-001 的单例诉求：`get_default_scheduler()` 返回进程内唯一实例（参数不漂移）。

参考：FSRS-5 默认 19 权重 + 标准更新公式（github.com/open-spaced-repetition）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import IntEnum

# FSRS-5 默认 19 权重
_DEFAULT_W: tuple[float, ...] = (
    0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575,
    0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621,
)
_DECAY = -0.5
_FACTOR = 19 / 81  # = 0.9 ** (1/_DECAY) - 1
_MIN_D, _MAX_D = 1.0, 10.0


class Rating(IntEnum):
    """复习评分：1 忘了 / 2 困难 / 3 良好 / 4 容易。"""

    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


@dataclass(frozen=True)
class Card:
    """一张复习卡的 FSRS 状态。new 卡 stability/difficulty 为 None（首评后初始化）。"""

    stability: float | None = None
    difficulty: float | None = None
    due: datetime | None = None
    last_review: datetime | None = None
    reps: int = 0
    lapses: int = 0
    state: str = "new"  # new / review

    def to_dict(self) -> dict:
        return {
            "stability": self.stability,
            "difficulty": self.difficulty,
            "due": self.due.isoformat() if self.due else None,
            "last_review": self.last_review.isoformat() if self.last_review else None,
            "reps": self.reps,
            "lapses": self.lapses,
            "state": self.state,
        }


@dataclass(frozen=True)
class ScheduleResult:
    card: Card
    interval_days: int
    retrievability: float = field(default=0.0)

    def to_dict(self) -> dict:
        return {
            "card": self.card.to_dict(),
            "interval_days": self.interval_days,
            "retrievability": round(self.retrievability, 4),
        }


class FSRSScheduler:
    """FSRS-5 调度器。无状态（参数不可变），可全进程共享。"""

    def __init__(
        self, *, weights: tuple[float, ...] = _DEFAULT_W,
        desired_retention: float = 0.9, maximum_interval: int = 36500,
    ) -> None:
        if len(weights) < 19:
            raise ValueError("FSRS 需 19 权重")
        self.w = weights
        self.desired_retention = desired_retention
        self.maximum_interval = maximum_interval

    # ---------- 初值 ----------
    def _init_stability(self, rating: Rating) -> float:
        return max(self.w[rating - 1], 0.1)

    def _init_difficulty(self, rating: Rating) -> float:
        d = self.w[4] - math.exp(self.w[5] * (rating - 1)) + 1
        return self._clamp_d(d)

    @staticmethod
    def _clamp_d(d: float) -> float:
        return min(max(d, _MIN_D), _MAX_D)

    # ---------- 核心数学 ----------
    def retrievability(self, elapsed_days: float, stability: float) -> float:
        """t 天后保持率 R = (1 + FACTOR*t/S)^DECAY。"""
        if stability <= 0:
            return 0.0
        return (1 + _FACTOR * elapsed_days / stability) ** _DECAY

    def _next_interval(self, stability: float) -> int:
        """达到 desired_retention 的间隔（天，至少 1）。"""
        ivl = (stability / _FACTOR) * (self.desired_retention ** (1 / _DECAY) - 1)
        return int(min(max(round(ivl), 1), self.maximum_interval))

    def _next_difficulty(self, d: float, rating: Rating) -> float:
        # linear damping + 向 easy 初值均值回归
        d_delta = -self.w[6] * (rating - 3)
        d_prime = d + d_delta * (10 - d) / 9
        d_new = self.w[7] * self._init_difficulty(Rating.EASY) + (1 - self.w[7]) * d_prime
        return self._clamp_d(d_new)

    def _next_stability_recall(self, d: float, s: float, r: float, rating: Rating) -> float:
        hard_penalty = self.w[15] if rating == Rating.HARD else 1.0
        easy_bonus = self.w[16] if rating == Rating.EASY else 1.0
        alpha = (
            math.exp(self.w[8]) * (11 - d) * (s ** -self.w[9])
            * (math.exp(self.w[10] * (1 - r)) - 1) * hard_penalty * easy_bonus
        )
        return s * (1 + alpha)

    def _next_stability_lapse(self, d: float, s: float, r: float) -> float:
        s_lapse = (
            self.w[11] * (d ** -self.w[12]) * ((s + 1) ** self.w[13] - 1)
            * math.exp(self.w[14] * (1 - r))
        )
        return min(s_lapse, s)  # 遗忘后稳定性不增

    # ---------- 调度入口 ----------
    def review(self, card: Card, rating: Rating, *, now: datetime | None = None) -> ScheduleResult:
        """对一张卡施加一次评分，返回更新后的卡 + 下次间隔。"""
        rating = Rating(int(rating))
        now = now or datetime.utcnow()

        if card.state == "new" or card.stability is None or card.difficulty is None:
            stability = self._init_stability(rating)
            difficulty = self._init_difficulty(rating)
            r = 0.0
        else:
            elapsed = max((now - card.last_review).total_seconds() / 86400, 0) \
                if card.last_review else 0.0
            r = self.retrievability(elapsed, card.stability)
            difficulty = self._next_difficulty(card.difficulty, rating)
            if rating == Rating.AGAIN:
                stability = self._next_stability_lapse(card.difficulty, card.stability, r)
            else:
                stability = self._next_stability_recall(card.difficulty, card.stability, r, rating)

        interval = self._next_interval(stability)
        new_card = replace(
            card,
            stability=stability,
            difficulty=difficulty,
            due=now + timedelta(days=interval),
            last_review=now,
            reps=card.reps + 1,
            lapses=card.lapses + (1 if rating == Rating.AGAIN and card.state != "new" else 0),
            state="review",
        )
        return ScheduleResult(card=new_card, interval_days=interval, retrievability=r)


_DEFAULT_SCHEDULER: FSRSScheduler | None = None


def get_default_scheduler() -> FSRSScheduler:
    """进程内唯一 FSRSScheduler（FDR-M011-001：参数不漂移）。"""
    global _DEFAULT_SCHEDULER
    if _DEFAULT_SCHEDULER is None:
        _DEFAULT_SCHEDULER = FSRSScheduler()
    return _DEFAULT_SCHEDULER
