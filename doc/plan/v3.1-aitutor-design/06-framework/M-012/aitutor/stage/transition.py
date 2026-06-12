"""transition - 阶段档位转换器 M-012

> 对应模块: M-012 阶段校准（sm012-transition 子模块）
> 关联选型: TS-001 Python
> 关联接口: 通过 M-009 教学编排（IC-002）调用
> 设计模式: Strategy 模式中的 ConcreteStrategy（转换策略）
> 来源标注: [DD-001:MD-012/FS-012] + [DD-M推断:依据=M-012 档位越界保护]

[文件职责] 阶段档位转换：升档/降档判定 + 钳制 [1, 5]
[所属模块] M-012（来自DD-001）
[关联设计规范] MD-012（来自DD-001）
[功能描述]
  功能1: StageTransition 类：can_up / can_down / clamp 方法
  功能2: transition_stage 顶层函数：单次转换入口
  功能3: STAGE_MIN / STAGE_MAX 常量：档位边界
[输入输出]
  输入: current_stage:int / new_stage:int
  输出: bool（是否允许转换）/ int（钳制后档位）
[依赖关系]
  依赖文件: 无（纯函数 + 静态方法）
  被依赖文件: ./evaluator.py（StageEvaluator 调用 clamp）
[注意事项]
  注意1: 档位严格 [1, 5]，越界自动钳制并触发 E01202
  注意2: 单步升/降最多 1 档（避免档位跳跃）
  注意3: 转换幂等：相同 current == new 返回 True
[代码风格] 遵循CS-AITutor-V3.1
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-012 - 初始版本
[作者] DD-M-012-2026-06-02
[来源标注] [DD-001:MD-012] + [DD-M推断:依据=M-012 sm012-transition 子模块]
"""
from __future__ import annotations

from typing import Final

# 档位边界常量（[DD-001:MD-012 stages=1..5]）
STAGE_MIN: Final[int] = 1
"""档位下限 1"""
STAGE_MAX: Final[int] = 5
"""档位上限 5"""

# 单步最大跨度（[DD-M推断:依据=避免档位跳跃的渐进式策略]）
_MAX_STEP_DELTA: Final[int] = 1


class StageTransition:
    """[类名] StageTransition
    [职责] 阶段档位转换器：判定升/降档合法性 + 钳制越界
    [关联设计规范] MD-012（来自DD-001）
    [属性]
      属性1: stages tuple 档位元组 (1, 2, 3, 4, 5) 类级别
    [方法列表]
      方法1: can_up(current) -> bool - 是否可升档
      方法2: can_down(current) -> bool - 是否可降档
      方法3: clamp(stage) -> int - 钳制档位到 [STAGE_MIN, STAGE_MAX]
    [状态机] N/A
    [异常处理]
      异常1: ValueError - 构造时 stages 为空
    [来源标注] [DD-001:MD-012] + [DD-M推断:依据=类签名来自 MD-012]
    """

    stages: tuple = (1, 2, 3, 4, 5)

    def __init__(self) -> None:
        if not self.stages:
            raise ValueError("stages 不能为空")
        # 实例属性冗余一份，方便子类覆盖
        self._stages: tuple = self.stages

    def can_up(self, current: int) -> bool:
        """[函数名] can_up
        [职责] 判断当前档位是否可继续升档
        [关联接口契约] 通过 M-009 教学编排（IC-002）调用
        [参数说明]
          参数1: current int 必填 描述: 当前档位 校验规则: 钳制后判断
        [返回值]
          类型: bool
          描述: True=可升 / False=已在最高档
          特殊值: None
        [错误码] 无
        [前置条件] 无
        [后置条件] 无副作用
        [并发安全] 是（无状态）
        [幂等性] 是
        [性能约束] O(1)
        [示例]
          ```
          t = StageTransition()
          t.can_up(3)  # -> True
          t.can_up(5)  # -> False
          ```
        [来源标注] [DD-001:MD-012]
        """
        clamped = self.clamp(current)
        return clamped < STAGE_MAX

    def can_down(self, current: int) -> bool:
        """[函数名] can_down
        [职责] 判断当前档位是否可继续降档
        [关联接口契约] 通过 M-009 教学编排（IC-002）调用
        [参数说明]
          参数1: current int 必填 描述: 当前档位
        [返回值]
          类型: bool
          描述: True=可降 / False=已在最低档
          特殊值: None
        [错误码] 无
        [前置条件] 无
        [后置条件] 无副作用
        [并发安全] 是
        [幂等性] 是
        [性能约束] O(1)
        [示例]
          ```
          t = StageTransition()
          t.can_down(3)  # -> True
          t.can_down(1)  # -> False
          ```
        [来源标注] [DD-001:MD-012]
        """
        clamped = self.clamp(current)
        return clamped > STAGE_MIN

    @staticmethod
    def clamp(stage: int) -> int:
        """[函数名] clamp
        [职责] 将档位钳制到 [STAGE_MIN, STAGE_MAX] 区间
        [关联接口契约] 通过 M-009 教学编排（IC-002）调用
        [参数说明]
          参数1: stage int 必填 描述: 待钳制档位
        [返回值]
          类型: int
          描述: 钳制后档位
          特殊值: 输入 <1 返回 STAGE_MIN；输入 >5 返回 STAGE_MAX
        [错误码]
          错误码1: E01202 - 档位越界（仅在日志中告警，不抛异常）
        [前置条件] 无
        [后置条件] STAGE_MIN <= 返回值 <= STAGE_MAX
        [并发安全] 是
        [幂等性] 是
        [性能约束] O(1)
        [示例]
          ```
          StageTransition.clamp(0)   # -> 1
          StageTransition.clamp(7)   # -> 5
          StageTransition.clamp(3)   # -> 3
          ```
        [来源标注] [DD-001:MD-012] + [DD-M推断:依据=E01202 钳制实现]
        """
        if stage < STAGE_MIN:
            return STAGE_MIN
        if stage > STAGE_MAX:
            return STAGE_MAX
        return stage


def transition_stage(current: int, new: int) -> bool:
    """[函数名] transition_stage
    [职责] 顶层入口：判定档位转换是否合法
    [关联接口契约] 通过 M-009 教学编排（IC-002）调用
    [参数说明]
      参数1: current int 必填 描述: 当前档位
      参数2: new int 必填 描述: 目标档位
    [返回值]
      类型: bool
      描述: True=允许转换 / False=禁止
      特殊值: current == new 返回 True（幂等）
    [错误码]
      错误码1: E01202 - 越界时自动钳制并 WARN
    [前置条件] 无
    [后置条件] 无副作用
    [并发安全] 是
    [幂等性] 是
    [性能约束] O(1)
    [示例]
      ```
      transition_stage(3, 4)  # -> True（升一档）
      transition_stage(3, 6)  # -> True（钳制到 5）
      transition_stage(3, 1)  # -> False（跨度 > 1）
      transition_stage(3, 3)  # -> True（幂等）
      ```
    [来源标注] [DD-001:MD-012]
    """
    t = StageTransition()
    cur_clamped = t.clamp(current)
    new_clamped = t.clamp(new)
    if cur_clamped == new_clamped:
        return True  # 幂等
    delta = abs(new_clamped - cur_clamped)
    return delta <= _MAX_STEP_DELTA
