"""stage - 阶段校准模块入口（M-012）

> 对应模块: M-012 阶段校准（Strategy）
> 关联选型: TS-001 Python
> 设计模式: Strategy（阶段评估策略 + 档位转换策略）
> 子模块: sm012-evaluate（评估）/ sm012-transition（转换）
> 关联规范: [DD-001:MD-012/FS-012] + [DD-M推断:依据=M-012 阶段校准 Strategy 模式拆分]

[文件职责] 阶段校准模块公共接口导出
[所属模块] M-012（来自DD-001）
[关联设计规范] FS-012 / MD-012（来自DD-001）
[功能描述]
  功能1: 导出 StageEvaluator 类（阶段评估器，含 hysteresis 2 天窗口）
  功能2: 导出 StageTransition 类（档位转换器，钳制 [1, 5]）
  功能3: 导出 evaluate_stage / transition_stage 公共函数
  功能4: 导出 STAGE_MIN / STAGE_MAX / DEFAULT_HYSTERESIS_DAYS 常量
[输入输出]
  输入: 无（模块初始化）
  输出: 公共 API 符号（类/函数/常量）
[依赖关系]
  依赖文件: ./evaluator.py、./transition.py
  被依赖文件: teaching/orchestrator.py（M-009 教学编排调用阶段校准）
[注意事项]
  注意1: 本模块为纯逻辑模块，无 I/O 依赖，可在 asyncio 协程中安全调用
  注意2: hysteresis 窗口涉及日期计算，需使用 UTC 标准时间避免时区漂移
  注意3: 档位取值范围严格 [1, 5]，越界由 StageTransition.clamp() 钳制
[代码风格] 遵循CS-AITutor-V3.1（4空格缩进、Google风格docstring、snake_case）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-012 - 初始版本，按DD-001 M-012模块细化方案创建
[作者] DD-M-012-2026-06-02
[来源标注] [DD-001:FS-012/MD-012]
"""
from __future__ import annotations

# 模块公共接口导出（按 M-012 模块细化方案）
from .evaluator import (
    StageEvaluator,
    evaluate_stage,
    Performance,
    DEFAULT_WINDOW_DAYS,
    DEFAULT_HYSTERESIS_DAYS,
)
from .transition import (
    StageTransition,
    transition_stage,
    STAGE_MIN,
    STAGE_MAX,
)

__all__ = [
    # 类
    "StageEvaluator",
    "StageTransition",
    # 函数
    "evaluate_stage",
    "transition_stage",
    # 类型
    "Performance",
    # 常量
    "STAGE_MIN",
    "STAGE_MAX",
    "DEFAULT_WINDOW_DAYS",
    "DEFAULT_HYSTERESIS_DAYS",
]
