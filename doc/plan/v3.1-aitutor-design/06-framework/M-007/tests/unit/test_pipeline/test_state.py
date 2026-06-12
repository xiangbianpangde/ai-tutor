"""test_state - PipelineState FSM 单元测试

> 对应模块: M-007
> 来源标注: [DD-001:MD-M-007 状态机段]
[文件职责]  PipelineState FSM 测试
[测试策略]  单元 / 6 用例（核心 3 + 边界 2 + 异常 1）/ Mock[无] / 覆盖率≥80%

[测试场景清单]
  - 测试场景1: 正常状态转换 INIT→PREPROCESS→...→DONE
    断言: stage_history 包含全部 7 状态
    Mock: 无
  - 测试场景2: 非法转换（INIT→LLM）抛 InvalidTransition
    断言: 抛 InvalidTransition; current_stage 不变
    Mock: 无
  - 测试场景3: round>3 触发 is_stuck=True
    断言: is_stuck(state) == True
    Mock: 无
  - 测试场景4: snapshot() 序列化完整字段
    断言: 包含 round / current_stage / stage_history / trace_id
    Mock: 无
  - 测试场景5: to_fallback() 切到 LLM_FALLBACK
    断言: current_stage == LLM_FALLBACK
    Mock: 无
  - 测试场景6: 状态机卡死（重复 PREPROCESS）触发 E00703
    断言: transition 抛 InvalidTransition
    Mock: 无

[来源标注]  [DD-001:MD-M-007 状态机段]
"""
import pytest

# [DD-001:MD-M-007 状态机段] 7 状态转换测试
# [DD-001:MD-M-007 异常处理 E00703] 卡死场景
# [DD-M推断:依据=FSM 模式] 转换表 + 终止条件
