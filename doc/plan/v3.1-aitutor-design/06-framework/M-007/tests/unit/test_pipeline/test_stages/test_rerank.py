"""test_rerank - RerankStage 单元测试

> 对应模块: M-007
> 来源标注: [DD-001:MD-M-007 子模块 sm007-rerank]
[文件职责]  RerankStage 测试
[测试策略]  单元 / 3 用例（核心 1 + 边界 1 + 异常 1）/ Mock[NLI Scorer]

[测试场景清单]
  - 测试场景1: 正常重排序（按 score 降序）
    断言: chunks 顺序与 score 降序一致
    Mock: NLI Scorer 返回 [0.9, 0.7, 0.5]
  - 测试场景2: NLI 不可用降级 LLM 法官
    断言: rerank 仍完成（不抛异常）
    Mock: NLI 抛 OSError
  - 测试场景3: 空 chunks 列表返回空列表
    断言: 返回 []
    Mock: 无

[来源标注]  [DD-001:MD-M-007 sm007-rerank]
"""
import pytest

# [DD-001:MD-M-007 sm007-rerank] 阶段 3 测试
# [DD-001:IC-003 E00802] NLI 不可用降级
