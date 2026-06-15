"""backend.strategy.stage_calibration —— 阶段校准（M-012，对应 v2 #16 阶段过渡太猛）。

22 问题 #16「阶段过渡太猛」的根因：升降阶只看单次表现，抖动。本模块用**滑动窗口聚合 +
滞回（hysteresis）**平滑升降阶：连续若干次表现都过线才升/降，避免一次失误就降阶、一次
侥幸就升阶。

按 FDR-M012-001 拆评估（evaluator）与转换（transition）两职责；此处合于单文件（均 <100 行，
合计 2 类，不触 4.7 文件职责红线），保留两类边界。
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

# 档位：0 入门 / 1 进阶 / 2 精通（与 v1 PaceController scaffold 思路一致，但独立成校准信号）
MIN_STAGE, MAX_STAGE = 0, 2
_UP_THRESHOLD = 0.8  # 窗口均分 ≥ 此值才够升
_DOWN_THRESHOLD = 0.4  # 窗口均分 ≤ 此值才够降
_WINDOW = 5  # 滑动窗口大小
_MIN_SAMPLES = 3  # 不足此样本不轻易升降（冷启动滞回）


@dataclass
class StageEvaluator:
    """滑动窗口聚合表现分（[0,1]），给出窗口均分与样本数。"""

    window: int = _WINDOW

    def __post_init__(self) -> None:
        self._scores: deque[float] = deque(maxlen=self.window)

    def record(self, score: float) -> None:
        self._scores.append(max(0.0, min(1.0, score)))

    @property
    def samples(self) -> int:
        return len(self._scores)

    @property
    def mean(self) -> float:
        return sum(self._scores) / len(self._scores) if self._scores else 0.0


class StageCalibrator:
    """带滞回的升降阶决策：连续窗口表现过线才动档，且每次最多动一档。"""

    def __init__(
        self, *, up: float = _UP_THRESHOLD, down: float = _DOWN_THRESHOLD,
        min_samples: int = _MIN_SAMPLES, window: int = _WINDOW,
    ) -> None:
        self.up = up
        self.down = down
        self.min_samples = min_samples
        self.evaluator = StageEvaluator(window=window)

    def record(self, score: float) -> None:
        self.evaluator.record(score)

    def recommend(self, current_stage: int) -> dict:
        """返回 {recommended_stage, action, mean, samples, reason}。

        action ∈ {up, down, hold}。样本不足 → hold（滞回，防抖）。
        """
        mean = self.evaluator.mean
        samples = self.evaluator.samples
        stage = max(MIN_STAGE, min(MAX_STAGE, current_stage))

        if samples < self.min_samples:
            return self._result(stage, "hold", mean, samples,
                                 f"样本 {samples}<{self.min_samples}，滞回防抖不动档")
        if mean >= self.up and stage < MAX_STAGE:
            return self._result(stage + 1, "up", mean, samples,
                                f"窗口均分 {mean:.2f}≥{self.up} 连续达标，升一档")
        if mean <= self.down and stage > MIN_STAGE:
            return self._result(stage - 1, "down", mean, samples,
                                f"窗口均分 {mean:.2f}≤{self.down}，降一档巩固")
        return self._result(stage, "hold", mean, samples,
                            f"窗口均分 {mean:.2f} 在滞回带内，保持当前档")

    @staticmethod
    def _result(stage: int, action: str, mean: float, samples: int, reason: str) -> dict:
        return {
            "recommended_stage": stage,
            "action": action,
            "mean": round(mean, 4),
            "samples": samples,
            "reason": reason,
        }
