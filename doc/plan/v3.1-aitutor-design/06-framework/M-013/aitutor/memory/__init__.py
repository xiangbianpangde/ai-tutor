"""memory - 长期记忆模块入口（M-013）

> 对应模块: M-013（长期记忆）
> 关联接口: IC-007（长期记忆 API-007/IF-007）
> 关联选型: TS-003 SQLite / TS-006 httpx
> 设计模式: Repository + LRU
> 来源标注: [AR:API-007] + [AR:TD-AR-006] + [DD-001:FS-NNN/MD-NNN]
> 作者: DD-M-013-20260602
> 模块边界: 本文件仅可被 M-013 内或上层路由引用，禁止被其他业务模块直接依赖
"""
from __future__ import annotations

# 模块导出占位（仅注释说明，DD-S 实施时由结构设计师按接口契约填充）
# - Memory：记忆数据模型（详见 models.py）
# - MemoryRepository：记忆持久化（详见 repository.py）
# - LRUEviction：LRU 淘汰策略（详见 lru.py）
# - FactExtractor：LLM 事实提取器（详见 extractor.py）
# - MemoryService：业务编排入口（详见 service.py）
#
# Import Linter 约束（来自 CS-NNN .importlinter.toml contract:3）：
#   - 本包禁止依赖 aitutor.api
#   - 本包禁止反向依赖 aitutor.session.service / aitutor.teaching.service
__all__ = [
    "Memory",
    "MemoryRepository",
    "LRUEviction",
    "FactExtractor",
    "MemoryService",
]
