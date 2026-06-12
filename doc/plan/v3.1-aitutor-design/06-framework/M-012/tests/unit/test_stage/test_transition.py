"""test_transition - M-012 StageTransition / transition_stage 单元测试

> 对应模块: M-012 阶段校准（transition）
> 关联选型: TS-017 pytest
> 测试策略: 6 用例（核心 3 + 边界 2 + 异常 1）/ 覆盖率≥80%
> 来源标注: [DD-001:MD-012 测试策略] + [DD-M推断:依据=M-012 测试场景拆分]

[文件职责] 阶段档位转换器测试
[所属模块] M-012（来自DD-001）
[关联设计规范] MD-012 / FS-012（来自DD-001）
[输入输出]
  输入: pytest 框架调用
  输出: 测试结果
[依赖关系]
  依赖文件: src/aitutor/stage/transition.py
  被依赖文件: 无
[注意事项]
  注意1: clamp 越界场景需覆盖 0 / 7 / -1 三种越界
  注意2: 转换跨度 > 1 应被拒绝（防档位跳跃）
[代码风格] 遵循CS-AITutor-V3.1
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-012 - 初始版本
[作者] DD-M-012-2026-06-02
[来源标注] [DD-001:MD-012]
"""
from __future__ import annotations

import pytest

from aitutor.stage.transition import (
    STAGE_MAX,
    STAGE_MIN,
    StageTransition,
    transition_stage,
)


# ---------- 核心测试场景 ----------

# [测试场景1: 正常-可升档判定] [断言: STAGE_MAX-1 可升, STAGE_MAX 不可升] [Mock: 无]
def test_can_up_returns_true_when_below_max() -> None:
    """[测试场景] 中间档位可升档
    [断言] can_up(3) == True; can_up(5) == False
    [Mock] 无
    [来源标注] [DD-001:MD-012 can_up]
    """
    t = StageTransition()
    assert t.can_up(STAGE_MAX - 1) is True
    assert t.can_up(STAGE_MAX) is False


# [测试场景2: 正常-可降档判定] [断言: STAGE_MIN+1 可降, STAGE_MIN 不可降] [Mock: 无]
def test_can_down_returns_true_when_above_min() -> None:
    """[测试场景] 中间档位可降档
    [断言] can_down(2) == True; can_down(1) == False
    [Mock] 无
    [来源标注] [DD-001:MD-012 can_down]
    """
    t = StageTransition()
    assert t.can_down(STAGE_MIN + 1) is True
    assert t.can_down(STAGE_MIN) is False


# [测试场景3: 正常-顶层 transition_stage] [断言: 跨度 1 合法, 跨度 2 非法, 相同档位幂等] [Mock: 无]
def test_transition_stage_rules() -> None:
    """[测试场景] transition_stage 转换规则
    [断言] 跨度 1 合法 / 跨度 2 非法 / 相同档位返回 True
    [Mock] 无
    [来源标注] [DD-001:MD-012 transition_stage]
    """
    assert transition_stage(3, 4) is True  # 升一档
    assert transition_stage(3, 5) is False  # 跳两档 → 拒绝
    assert transition_stage(3, 1) is False  # 跳两档 → 拒绝
    assert transition_stage(3, 3) is True   # 幂等


# ---------- 边界测试场景 ----------

# [测试场景4: 边界-clamp 越界] [断言: 0→1, 7→5, -1→1] [Mock: 无]
def test_clamp_out_of_range() -> None:
    """[测试场景] clamp 越界处理（E01202）
    [断言] 下越界返回 STAGE_MIN；上越界返回 STAGE_MAX
    [Mock] 无
    [来源标注] [DD-001:MD-012 E01202] + [DD-M推断:依据=clamp 实现]
    """
    assert StageTransition.clamp(0) == STAGE_MIN
    assert StageTransition.clamp(-1) == STAGE_MIN
    assert StageTransition.clamp(7) == STAGE_MAX
    assert StageTransition.clamp(100) == STAGE_MAX
    assert StageTransition.clamp(3) == 3


# [测试场景5: 边界-transition_stage 越界钳制] [断言: 3→100 应被拒绝（钳制后跨度 2）] [Mock: 无]
def test_transition_stage_clamps_inputs() -> None:
    """[测试场景] transition_stage 自动钳制越界
    [断言] 输入越界时按钳制值计算跨度
    [Mock] 无
    [来源标注] [DD-001:MD-012 E01202]
    """
    # current=3, new=100 → 钳制 new=5 → 跨度 2 → 拒绝
    assert transition_stage(3, 100) is False
    # current=0, new=2 → 钳制 current=1 → 跨度 1 → 允许
    assert transition_stage(0, 2) is True


# ---------- 异常测试场景 ----------

# [测试场景6: 异常-StageTransition 构造异常] [断言: 不抛异常（仅校验 stages 非空）] [Mock: 无]
def test_stage_transition_construct_default() -> None:
    """[测试场景] 默认构造不抛异常
    [断言] StageTransition() 实例化成功
    [Mock] 无
    [来源标注] [DD-M推断:依据=__init__ 校验]
    """
    t = StageTransition()
    assert t is not None
    assert t._stages == (1, 2, 3, 4, 5)
