"""backend.strategy —— 教学策略升级（C4，对应 v2 #10 拆分）。

- M-010 费曼讲解评分（feynman）
- M-011 FSRS-5 间隔重复调度（fsrs）
- M-012 阶段校准（stage_calibration，滑动窗口 + 滞回防抖）
"""
from __future__ import annotations

from .feynman import FeynmanScore, FeynmanScorer, extract_key_terms
from .fsrs import Card, FSRSScheduler, Rating, ScheduleResult, get_default_scheduler
from .stage_calibration import StageCalibrator, StageEvaluator

__all__ = [
    "FeynmanScorer",
    "FeynmanScore",
    "extract_key_terms",
    "FSRSScheduler",
    "Card",
    "Rating",
    "ScheduleResult",
    "get_default_scheduler",
    "StageCalibrator",
    "StageEvaluator",
]
