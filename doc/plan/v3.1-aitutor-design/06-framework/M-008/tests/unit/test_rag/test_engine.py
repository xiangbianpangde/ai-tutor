"""test_engine - RAGEngine 测试

> 对应模块: M-008
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD推断:依据=pytest 测试规范]
"""
from __future__ import annotations

import pytest

# 本地模块
from aitutor.rag.engine import RAGEngine


# ========== 测试场景注释 ==========

# [测试场景1: 正常检索]
# 断言: 返回 List[Chunk] 非空且按 NLI 分数降序
# Mock: IndexAdapter.query / NLIScorer.score / RoutingAdapter.route
# 性能: ≤10s

# [测试场景2: NLI 评分 < 0.7 触发重检索]
# 断言: round 计数 + 1；最终 score >= 0.7 或抛 RAGCannotConfirmError
# Mock: NLIScorer.score 连续 2 次返回 0.5 / 0.8

# [测试场景3: 重检索 3 轮仍 < 0.7 抛 RAGCannotConfirmError]
# 断言: 抛 RAGCannotConfirmError；trace_id 关联
# Mock: NLIScorer.score 始终返回 0.5

# [测试场景4: validate_answer 验证答案]
# 断言: 返回 ValidationResult.is_supported == True
# Mock: NLIScorer.score 返回 0.95

# [测试场景5: 并发检索线程安全]
# 断言: 100 个并发 retrieve() 不产生重复 query_hash 写入
# Mock: IndexAdapter + NLIScorer

# [测试场景6: query 为空抛 ValidationError]
# 断言: 抛 ValidationError
# Mock: 无
