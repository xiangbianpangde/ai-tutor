"""test_nli - NLI 评分子能力测试

> 对应模块: M-008 子模块 sm008-nli
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008]
"""
from __future__ import annotations

import pytest

# 本地模块
from aitutor.rag.nli.scorer import NLIScorer
from aitutor.rag.nli.model import NLIModelLoader


# ========== 测试场景注释 ==========

# [测试场景1: NLI 正常评分返回 [0, 1]]
# 断言: 0.0 <= score <= 1.0
# Mock: NLIModelLoader.get_model 返回 mock transformers pipeline

# [测试场景2: 评分 < threshold 标记为低分]
# 断言: 0.5 < 0.7 (threshold) → 触发重检索
# Mock: NLIModelLoader 返回固定 0.5

# [测试场景3: NLI 不可用降级 LLM 法官]
# 断言: 抛 NLIUnavailableError 后，fallback_to_llm=True 时返回 LLM 评分
# Mock: NLIModelLoader.get_model 抛 NLIUnavailableError + httpx mock

# [测试场景4: NLI 不可用且不降级时抛 NLIUnavailableError]
# 断言: 直接抛 NLIUnavailableError
# Mock: NLIModelLoader 不可用 + fallback_to_llm=False

# [测试场景5: CPU 亲和性绑定]
# 断言: bind_cpu_affinity(0) 调用后 os.sched_getaffinity 包含 0
# Mock: psutil

# [测试场景6: 模型加载幂等性]
# 断言: 重复 load() 不重新加载
# Mock: NLIModelLoader mock
