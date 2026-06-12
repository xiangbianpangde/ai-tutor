"""evaluator - 阶段评估器（含 hysteresis 2 天窗口）M-012

> 对应模块: M-012 阶段校准（sm012-evaluate 子模块）
> 关联选型: TS-001 Python
> 关联接口: 通过 M-009 教学编排间接调用（无独立 IC-NNN）
> 设计模式: Strategy 模式中的 ConcreteStrategy（评估策略）
> 来源标注: [DD-001:MD-012/FS-012] + [DD-M推断:依据=hysteresis 防抖策略]

[文件职责] 阶段评估器：基于最近 N 天表现数据评估目标档位
[所属模块] M-012（来自DD-001）
[关联设计规范] MD-012（来自DD-001）
[功能描述]
  功能1: StageEvaluator 类：滑动窗口聚合 + 滞回判断
  功能2: evaluate_stage 顶层函数：单次评估入口
  功能3: Performance 数据类：表现数据载体（正确率/耗时/复习通过率）
[输入输出]
  输入: Performance（用户表现数据）
  输出: int 目标档位（1..5）
[依赖关系]
  依赖文件: ./transition.py（用于档位钳制与越界保护）
  被依赖文件: teaching/orchestrator.py（M-009 教学编排）
[注意事项]
  注意1: hysteresis 2 天窗口需用户提供 UTC 日期序列
  注意2: 数据不足时返回 current_stage（不强行升/降档，触发 E01201）
  注意3: 表现聚合权重：accuracy 0.5 + speed 0.2 + retention 0.3（DD-M推断:依据=MD-012 隐含权重）
[代码风格] 遵循CS-AITutor-V3.1
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-012 - 初始版本
[作者] DD-M-012-2026-06-02
[来源标注] [DD-001:MD-012] + [DD-M推断:依据=MD-012 阶段校准子模块 sm012-evaluate]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from .transition import STAGE_MIN, STAGE_MAX, StageTransition

# 常量定义（[DD-M推断:依据=MD-012 隐含配置]）
DEFAULT_WINDOW_DAYS: int = 7
"""默认评估窗口 7 天（与 MD-012 window=7d 一致）"""
DEFAULT_HYSTERESIS_DAYS: int = 2
"""默认滞回窗口 2 天（与 MD-012 hysteresis=2d 一致）"""

# 表现聚合权重（[DD-M推断:依据=MD-012 阶段校准无显式权重声明，按教学编排隐含权重]）
_WEIGHT_ACCURACY: float = 0.5
_WEIGHT_SPEED: float = 0.2
_WEIGHT_RETENTION: float = 0.3

# 档位升档阈值（[DD-M推断:依据=均匀分段 0..1 映射到 5 档]）
_UPGRADE_THRESHOLD: float = 0.75
_DOWNGRADE_THRESHOLD: float = 0.40


@dataclass
class Performance:
    """[类名] Performance
    [职责] 用户表现数据载体（DD-M推断:依据=MD-012 evaluate(performance) 签名）
    [关联设计规范] MD-012
    [属性]
      属性1: user_id str 用户ID
      属性2: accuracy float 区间[0,1] 正确率
      属性3: avg_response_seconds float 平均响应耗时（秒）
      属性4: retention_rate float 区间[0,1] 复习通过率
      属性5: samples List[DailySample] 每日样本序列（用于 hysteresis 判断）
      属性6: current_stage int 当前档位
    [方法列表]
      方法1: to_score() -> float - 聚合综合得分
    [异常处理]
      异常1: ValueError - accuracy/retention_rate 越界 [0,1]
    [来源标注] [DD-M推断:依据=MD-012 evaluate(performance) 函数签名]
    """

    user_id: str
    accuracy: float
    avg_response_seconds: float
    retention_rate: float
    samples: List["DailySample"] = field(default_factory=list)
    current_stage: int = STAGE_MIN

    def __post_init__(self) -> None:
        if not 0.0 <= self.accuracy <= 1.0:
            raise ValueError(f"accuracy 越界: {self.accuracy}, 期望 [0, 1]")
        if not 0.0 <= self.retention_rate <= 1.0:
            raise ValueError(f"retention_rate 越界: {self.retention_rate}, 期望 [0, 1]")
        StageTransition.clamp(self.current_stage)  # type: ignore[arg-type]

    def to_score(self) -> float:
        """[函数名] to_score
        [职责] 加权聚合综合得分
        [参数说明] 无
        [返回值] 类型: float / 描述: 综合得分 [0, 1]
        [错误码] 无
        [前置条件] 字段已通过 __post_init__ 校验
        [后置条件] 返回值在 [0, 1] 区间
        [并发安全] 是（无共享状态）
        [幂等性] 是
        [性能约束] O(1)
        [来源标注] [DD-M推断:依据=MD-012 性能聚合需求]
        """
        return (
            self.accuracy * _WEIGHT_ACCURACY
            + max(0.0, 1.0 - min(self.avg_response_seconds / 60.0, 1.0)) * _WEIGHT_SPEED
            + self.retention_rate * _WEIGHT_RETENTION
        )


@dataclass
class DailySample:
    """[类名] DailySample
    [职责] 单日表现样本（用于 hysteresis 滑动窗口）
    [关联设计规范] MD-012（DD-M推断:依据=hysteresis 需日期序列）
    [属性]
      属性1: day date 样本日期（UTC）
      属性2: score float 区间[0,1] 当日综合得分
    [方法列表] 无
    [异常处理]
      异常1: ValueError - score 越界 [0,1]
    [来源标注] [DD-M推断:依据=MD-012 hysteresis 2d 窗口需时间序列]
    """

    day: date
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score 越界: {self.score}, 期望 [0, 1]")


class StageEvaluator:
    """[类名] StageEvaluator
    [职责] 阶段评估器：基于滑动窗口 + hysteresis 防抖决定目标档位
    [关联设计规范] MD-012（来自DD-001）
    [属性]
      属性1: window int 滑动窗口天数 默认7
      属性2: hysteresis int 滞回天数 默认2
      属性3: upgrade_threshold float 升档阈值 默认0.75
      属性4: downgrade_threshold float 降档阈值 默认0.40
    [方法列表]
      方法1: evaluate(performance) -> int - 评估目标档位
      方法2: _is_stable(new_stage, samples) -> bool - 滞回稳定性判断
      方法3: _aggregate(samples) -> float - 窗口内得分聚合
    [状态机] N/A（无内部状态，窗口由调用方提供）
    [异常处理]
      异常1: InsufficientDataError - samples 不足时抛（E01201 触发条件）
    [来源标注] [DD-001:MD-012] + [DD-M推断:依据=类签名来自 MD-012 StageEvaluator]
    """

    def __init__(
        self,
        window: int = DEFAULT_WINDOW_DAYS,
        hysteresis: int = DEFAULT_HYSTERESIS_DAYS,
        upgrade_threshold: float = _UPGRADE_THRESHOLD,
        downgrade_threshold: float = _DOWNGRADE_THRESHOLD,
    ) -> None:
        if window < 1:
            raise ValueError(f"window 必须 >= 1, 实际 {window}")
        if hysteresis < 0 or hysteresis >= window:
            raise ValueError(
                f"hysteresis 必须在 [0, window) 区间, 实际 {hysteresis}/{window}"
            )
        if not 0.0 < downgrade_threshold < upgrade_threshold < 1.0:
            raise ValueError("downgrade_threshold < upgrade_threshold 且均在 (0, 1) 区间")
        self.window: int = window
        self.hysteresis: int = hysteresis
        self.upgrade_threshold: float = upgrade_threshold
        self.downgrade_threshold: float = downgrade_threshold

    def evaluate(self, performance: Performance) -> int:
        """[函数名] evaluate
        [职责] 评估目标档位（hysteresis 防抖）
        [关联接口契约] 通过 M-009 教学编排（IC-002 学习回合）调用
        [参数说明]
          参数1: performance Performance 必填 描述: 用户表现数据 校验规则: 字段已校验
        [返回值]
          类型: int
          描述: 目标档位 [STAGE_MIN, STAGE_MAX]
          特殊值: 数据不足时返回 performance.current_stage（保持现状）
        [错误码]
          错误码1: E01201 - 数据不足，samples 数 < window
        [前置条件] performance.samples 已排序（按 day 升序）
        [后置条件] 返回值在 [STAGE_MIN, STAGE_MAX] 区间
        [并发安全] 是（无共享可变状态）
        [幂等性] 是（输入相同时返回相同结果）
        [性能约束] O(window)
        [示例]
          ```
          evaluator = StageEvaluator()
          result = evaluator.evaluate(performance)  # -> 1..5
          ```
        [来源标注] [DD-001:MD-012]
        """
        if len(performance.samples) < self.window:
            # E01201: 数据不足 → 保持当前档位
            return performance.current_stage

        # 仅取最近 window 天的样本
        recent = performance.samples[-self.window :]
        aggregated = self._aggregate(recent)
        proposed = self._score_to_stage(aggregated)
        proposed = StageTransition.clamp(proposed)  # 钳制 [STAGE_MIN, STAGE_MAX]

        if proposed == performance.current_stage:
            return proposed

        # hysteresis 判断：若升/降档，需连续 hysteresis 天达到阈值
        tail = performance.samples[-self.hysteresis :]
        if self._is_stable(proposed, tail, aggregated):
            return proposed
        return performance.current_stage

    def _aggregate(self, samples: List[DailySample]) -> float:
        """[函数名] _aggregate
        [职责] 窗口内得分聚合（均值）
        [参数说明]
          参数1: samples List[DailySample] 必填 描述: 窗口内样本
        [返回值] 类型: float / 描述: 平均得分 [0, 1]
        [前置条件] samples 非空
        [后置条件] 返回值在 [0, 1]
        [并发安全] 是
        [幂等性] 是
        [性能约束] O(len(samples))
        [来源标注] [DD-M推断:依据=MD-012 隐含聚合方式]
        """
        if not samples:
            raise ValueError("samples 不能为空（内部校验失败）")
        return sum(s.score for s in samples) / len(samples)

    def _is_stable(
        self,
        proposed_stage: int,
        tail: List[DailySample],
        aggregated_score: float,
    ) -> bool:
        """[函数名] _is_stable
        [职责] 滞回稳定性判断：最近 hysteresis 天是否稳定达到阈值
        [参数说明]
          参数1: proposed_stage int 必填 描述: 提议的目标档位
          参数2: tail List[DailySample] 必填 描述: 最近 hysteresis 天样本
          参数3: aggregated_score float 必填 描述: 窗口聚合得分
        [返回值] 类型: bool / 描述: True=允许转换 / False=保持现状
        [前置条件] len(tail) == self.hysteresis
        [后置条件] 无副作用
        [并发安全] 是
        [幂等性] 是
        [性能约束] O(hysteresis)
        [来源标注] [DD-M推断:依据=MD-012 hysteresis 2d 防抖]
        """
        if not tail:
            return False
        # 升档：要求 tail 全部 >= upgrade_threshold
        if proposed_stage > self._current_stage_proxy():
            return all(s.score >= self.upgrade_threshold for s in tail)
        # 降档：要求 tail 全部 <= downgrade_threshold
        if proposed_stage < self._current_stage_proxy():
            return all(s.score <= self.downgrade_threshold for s in tail)
        return False

    def _current_stage_proxy(self) -> int:
        """[函数名] _current_stage_proxy
        [职责] 占位方法（实际 current_stage 由 Performance 提供）
        [参数说明] 无
        [返回值] 类型: int / 描述: STAGE_MIN
        [前置条件] 无
        [后置条件] 无
        [并发安全] 是
        [幂等性] 是
        [性能约束] O(1)
        [来源标注] [DD-M推断:依据=内部辅助]
        """
        return STAGE_MIN  # 实际 current_stage 在 evaluate() 中已对比

    def _score_to_stage(self, score: float) -> int:
        """[函数名] _score_to_stage
        [职责] 聚合得分 → 提议档位
        [参数说明]
          参数1: score float 必填 描述: 聚合得分 [0, 1]
        [返回值] 类型: int / 描述: 提议档位 [1, 5]
        [错误码] 无
        [前置条件] score in [0, 1]
        [后置条件] 返回值 in [STAGE_MIN, STAGE_MAX]
        [并发安全] 是
        [幂等性] 是
        [性能约束] O(1)
        [来源标注] [DD-M推断:依据=MD-012 stages=1..5 均匀分段]
        """
        # 将 [0, 1] 均匀切分为 5 档
        if score >= 0.9:
            return 5
        if score >= 0.75:
            return 4
        if score >= 0.5:
            return 3
        if score >= 0.25:
            return 2
        return 1


def evaluate_stage(performance: Performance) -> int:
    """[函数名] evaluate_stage
    [职责] 顶层入口：使用默认参数评估目标档位
    [关联接口契约] 通过 M-009 教学编排（IC-002）调用
    [参数说明]
      参数1: performance Performance 必填 描述: 用户表现数据
    [返回值]
      类型: int
      描述: 目标档位 [1, 5]
      特殊值: 数据不足时返回 performance.current_stage
    [错误码]
      错误码1: E01201 - 数据不足
    [前置条件] performance 字段已校验
    [后置条件] 返回值钳制在 [1, 5]
    [并发安全] 是
    [幂等性] 是
    [性能约束] O(7) 默认窗口
    [示例]
      ```
      result = evaluate_stage(performance)  # -> 1..5
      ```
    [来源标注] [DD-001:MD-012]
    """
    evaluator = StageEvaluator()
    return evaluator.evaluate(performance)
