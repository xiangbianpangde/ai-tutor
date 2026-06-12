"""test_retrieve - RetrieveStage 单元测试

> 对应模块: M-007
> 来源标注: [DD-001:MD-M-007 子模块 sm007-retrieve] + [DD-001:IC-003]
[文件职责]  RetrieveStage 测试
[测试策略]  单元+集成 / 5 用例（核心 2 + 边界 2 + 异常 1）/ Mock[RAG Engine] / 覆盖率≥80%

[测试场景清单]
  - 测试场景1: 正常检索返回 top_k chunks
    断言: len(result) == 5; 每项含 score 字段
    Mock: RAG Engine 返回 5 chunks
  - 测试场景2: 重检索 3 轮仍<0.7 触发 E00801
    断言: 抛 E00801; route_decision == "cannot_confirm"
    Mock: NLI 评分恒为 0.5
  - 测试场景3: RAG 超时（>10s）触发 E00705
    断言: 抛 PipelineStageError
    Mock: RAG Engine 阻塞 11s
  - 测试场景4: ChromaDB 集合不存在抛 StorageError
    断言: 抛 StorageError
    Mock: ChromaDB client.collection 为 None
  - 测试场景5: 重路由 1 次仍败触发 E00803
    断言: 抛 E00803
    Mock: RAG Engine 连续 2 次失败

[来源标注]  [DD-001:MD-M-007 sm007-retrieve] + [DD-001:IC-003]
"""
import pytest
import respx
import httpx

# [DD-001:MD-M-007 sm007-retrieve] 阶段 2 测试
# [DD-001:IC-003 E00705] RAG 超时
# [DD-001:IC-003 E00801] 重检索失败
# [DD-001:IC-003 E00803] 重路由失败
# [DD-M推断:依据=CS-AITutor-V3.1 测试规范] respx 模拟 HTTP
