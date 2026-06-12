"""test_fallback - FallbackStrategy 单元测试

> 对应模块: M-007
> 来源标注: [DD-001:MD-M-007 异常处理 E00702]
[文件职责]  FallbackStrategy 单元测试
[测试策略]  单元 / 4 用例（核心 2 + 边界 1 + 异常 1）/ Mock[LLM, audit_log]

[测试场景清单]
  - 测试场景1: 触发条件：FSM 卡死
    断言: should_fallback(state) == True
    Mock: state.is_stuck == True
  - 测试场景2: 兜底成功：fsm_fallback=True, sources=[]
    断言: result.fsm_fallback == True; result.sources == []
    Mock: LLM Stage 返回 "fallback answer"
  - 测试场景3: write_audit 写入 audit_log
    断言: audit_log 表新增 1 条
    Mock: SQLite in-memory
  - 测试场景4: 兜底也失败抛 PipelineFallbackError
    断言: 抛 E00702
    Mock: LLM Stage 抛 ConnectionError

[来源标注]  [DD-001:MD-M-007 异常处理 E00702]
"""
import pytest

# [DD-001:MD-M-007 异常处理 E00702] 兜底成功场景
# [DD-001:MD-M-007 异常处理 E00703] 兜底写 audit
# [DD-001:IC-002 fsm_fallback 字段] 输出标记
