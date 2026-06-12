"""test_llm - LLMStage 单元测试

> 对应模块: M-007
> 来源标注: [DD-001:MD-M-007 子模块 sm007-llm] + [DD-001:IC-002]
[文件职责]  LLMStage 测试
[测试策略]  单元+集成 / 5 用例（核心 2 + 边界 2 + 异常 1）/ Mock[httpx respx]

[测试场景清单]
  - 测试场景1: 正常 LLM 调用返回原始答案
    断言: result 非空字符串
    Mock: httpx MockProvider 返回 "answer"
  - 测试场景2: 流式 LLM 调用
    断言: 多次 yield chunk
    Mock: httpx 流式响应
  - 测试场景3: LLM 不可用（503）抛 LLMUnavailableError
    断言: 抛 E00702
    Mock: httpx 返回 503
  - 测试场景4: LLM 超时（>4s）抛 LL MTimeoutError
    断言: 抛 E00704
    Mock: httpx 阻塞 5s
  - 测试场景5: prompt 构造含引用源
    断言: prompt 含 [1]/[2] 占位符
    Mock: 无

[来源标注]  [DD-001:MD-M-007 sm007-llm] + [DD-001:IC-002]
"""
import pytest
import respx
import httpx

# [DD-001:MD-M-007 sm007-llm] 阶段 4 测试
# [DD-001:IC-002 E00702] LLM 不可用
# [DD-001:IC-002 E00704] LLM 超时
# [DD-M推断:依据=TS-006 httpx] 异步 HTTP 客户端 Mock
