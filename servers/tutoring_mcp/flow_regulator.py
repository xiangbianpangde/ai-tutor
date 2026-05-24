"""心流调节器 — 主动调节教学参数以维持心流状态。

与 PGFGA 心流追踪的关系：
  flow_tracker.py     — 被动检测：10 个信号 → FlowLevel（事后评估）
  gain_loop_monitor   — 断裂修复：检测 4 种断裂 → 修复 action（被动响应）
  flow_regulator.py   — 主动调节：FlowLevel → PaceConfig（课前/课中调参）
                                    ↑ 本文件是新增的"主动调控"层

设计原理：
  心流理论要求挑战与技能保持动态平衡。
  调节器在教学动作前调用，根据当前心流级别 + 认知负荷 + 最近正确率，
  推荐一组教学参数，策略用这些参数生成适配的教学内容。

FlowLevel → PaceConfig 映射：
  SILENT (0)  ：难度 0.6，脚手架最多，拆分最细 → 重建安全感
  SHALLOW (1) ：难度 0.8，部分脚手架 → 逐步建立信心
  FLUENT (2)  ：难度 1.0，少量脚手架 → 维持舒适区
  DEEP (3)    ：难度 1.2，无脚手架 → 增加挑战深度
  IMMERSED (4)：难度 1.4，无脚手架 + 延伸追问 → 保持巅峰体验
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.schemas import FlowLevel


@dataclass
class PaceConfig:
    """调节器输出的教学参数，策略根据这些参数生成教学内容。"""

    # 难度系数（0.5 = 最简单，1.5 = 最难）
    difficulty_multiplier: float = 1.0
    # 脚手架级别（3 = 最详细指引，0 = 自主探索）
    scaffold_level: int = 1
    # 原子问题的数量（越大拆得越细）
    sub_step_count: int = 4
    # 补集枚举的错误数量
    error_count: int = 6
    # 是否在原子问题间插入 mini 确认
    confirm_each_step: bool = True
    # 简要描述（用于日志和反馈）
    label: str = "标准"

    def to_dict(self) -> dict[str, Any]:
        return {
            "difficulty_multiplier": self.difficulty_multiplier,
            "scaffold_level": self.scaffold_level,
            "sub_step_count": self.sub_step_count,
            "error_count": self.error_count,
            "confirm_each_step": self.confirm_each_step,
            "label": self.label,
        }


# 心流级别 → PaceConfig 映射表
_FLOW_PACE_MAP: dict[FlowLevel, PaceConfig] = {
    FlowLevel.SILENT: PaceConfig(
        difficulty_multiplier=0.6,
        scaffold_level=3,
        sub_step_count=3,
        error_count=5,
        confirm_each_step=True,
        label="温和起步",
    ),
    FlowLevel.SHALLOW: PaceConfig(
        difficulty_multiplier=0.8,
        scaffold_level=2,
        sub_step_count=4,
        error_count=6,
        confirm_each_step=True,
        label="逐步建立",
    ),
    FlowLevel.FLUENT: PaceConfig(
        difficulty_multiplier=1.0,
        scaffold_level=1,
        sub_step_count=5,
        error_count=7,
        confirm_each_step=True,
        label="舒适推进",
    ),
    FlowLevel.DEEP: PaceConfig(
        difficulty_multiplier=1.2,
        scaffold_level=0,
        sub_step_count=5,
        error_count=8,
        confirm_each_step=False,
        label="深度挑战",
    ),
    FlowLevel.IMMERSED: PaceConfig(
        difficulty_multiplier=1.4,
        scaffold_level=0,
        sub_step_count=4,
        error_count=10,
        confirm_each_step=False,
        label="巅峰冲刺",
    ),
}


class FlowRegulator:
    """心流调节器。无状态，输出只由输入决定。可在 server 模块级单例。"""

    def recommend_pace(
        self,
        *,
        flow_level: FlowLevel | int,
        cognitive_load: float = 0.0,
        recent_accuracy: float | None = None,
    ) -> PaceConfig:
        """根据当前状态推荐教学参数。

        输入：
          flow_level     — 当前心流级别（从 flow_tracker 获得）
          cognitive_load — 当前认知负荷（0-1）
          recent_accuracy — 最近 3 轮正确率（用于微调）

        返回：
          PaceConfig — 策略用这些参数生成教学内容
        """
        if isinstance(flow_level, int):
            try:
                flow_level = FlowLevel(flow_level)
            except ValueError:
                flow_level = FlowLevel.FLUENT

        # 基础配置
        config = _FLOW_PACE_MAP.get(flow_level, _FLOW_PACE_MAP[FlowLevel.FLUENT])

        # 认知负荷修正
        if cognitive_load > 0.7:
            # 负荷过高 → 降低难度 + 增加脚手架
            config = PaceConfig(
                difficulty_multiplier=round(config.difficulty_multiplier * 0.85, 2),
                scaffold_level=min(3, config.scaffold_level + 1),
                sub_step_count=max(3, config.sub_step_count - 1),
                error_count=config.error_count,
                confirm_each_step=True,
                label=f"{config.label}（负荷修正）",
            )

        # 准确率修正
        if recent_accuracy is not None:
            if recent_accuracy < 0.3:
                # 持续答错 → 降低难度
                config = PaceConfig(
                    difficulty_multiplier=round(config.difficulty_multiplier * 0.8, 2),
                    scaffold_level=min(3, config.scaffold_level + 1),
                    sub_step_count=config.sub_step_count,
                    error_count=min(8, config.error_count + 2),
                    confirm_each_step=True,
                    label=f"{config.label}（正确率修正）",
                )
            elif recent_accuracy > 0.9 and flow_level in (FlowLevel.FLUENT, FlowLevel.DEEP):
                # 持续答对 + 中等以上心流 → 增加挑战
                config = PaceConfig(
                    difficulty_multiplier=round(config.difficulty_multiplier * 1.15, 2),
                    scaffold_level=max(0, config.scaffold_level - 1),
                    sub_step_count=config.sub_step_count,
                    error_count=config.error_count,
                    confirm_each_step=config.confirm_each_step,
                    label=f"{config.label}（加速修正）",
                )

        return config


# 单例
_regulator: FlowRegulator | None = None


def get_regulator() -> FlowRegulator:
    global _regulator
    if _regulator is None:
        _regulator = FlowRegulator()
    return _regulator
