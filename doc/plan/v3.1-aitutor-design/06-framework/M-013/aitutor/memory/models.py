"""memory.models - 长期记忆数据模型定义

[文件路径] src/aitutor/memory/models.py
[文件职责] 定义记忆实体 Memory 及其属性/方法的数据模型
[所属模块] M-013（长期记忆）
[关联设计规范] MD-013 / IC-007
[功能描述]
  功能1: 定义 Memory 实体（含 id/user_id/content/importance/last_access/created_at）
  功能2: 定义事实抽取输入输出模型 FactExtractionRequest / FactExtractionResult
  功能3: 定义 LRU 淘汰候选 Victim 模型
[输入输出]
  输入: 业务调用方传入 user_id/content/importance 等字段
  输出: Memory / MemoryQueryResult / FactExtractionResult 等领域对象
[依赖关系]
  依赖文件: aitutor.shared.types（TraceIdType / UserIdType 等共享类型）
  被依赖文件: aitutor.memory.repository / aitutor.memory.service / aitutor.memory.lru
[注意事项]
  注意1: 实体必须为 Pydantic v2 BaseModel（mypy strict + pydantic.mypy 插件）
  注意2: 字段不可变时使用 model_config = ConfigDict(frozen=True)
  注意3: 严格遵循 IC-007 字段语义，importance ∈ [1,5]
[代码风格] 遵循 CS-NNN（PEP8 + Google Docstring + mypy strict）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-013 - 初版注释框架（无业务代码）
[作者] DD-M-013-20260602
[来源标注] [DD-001:MD-013] + [DD-001:IC-007]
"""
from __future__ import annotations

# 1. 标准库（按 isort 强制顺序：标准库 → 第三方 → 本地）
# [DD-M推断:依据=CS-NNN §4.1 导入顺序，标准库先行]
from datetime import datetime
from typing import Optional
from uuid import UUID

# 2. 第三方库
# [DD-M推断:依据=Pydantic v2 官方推荐 + pyproject.toml pydantic==2.9.0]
from pydantic import BaseModel, ConfigDict, Field

# 3. 本地模块
# [DD-M推断:依据=FS-NNN §文件职责矩阵，models 仅依赖 shared/types]
from aitutor.shared.types import TraceIdType, UserIdType


# [类名] Memory
# [职责] 长期记忆领域实体（不可变快照）
# [关联设计规范] MD-013 / IC-007
# [属性]
#   属性1: id UUID 主键（V4）
#   属性2: user_id str 用户标识（强校验，防 CE-003 串号）
#   属性3: content str 事实内容，1~1000 字符
#   属性4: importance int ∈ [1,5]（V4.5 重要性权重）
#   属性5: last_access datetime 最近访问时间（用于 LRU 排序）
#   属性6: created_at datetime 创建时间
#   属性7: trace_id str 32hex 创建时的追踪 ID
# [方法列表]
#   方法1: touch() → None - 刷新 last_access（业务侧调用，DD-S 实施）
#   方法2: is_stale(now: datetime, ttl_seconds: int) → bool - 判断记忆是否过期
# [状态机] N/A
# [异常处理]
#   异常1: ValidationError - importance 越界 / content 超长
# [来源标注] [DD-001:MD-013] + [DD-001:IC-007]
class Memory(BaseModel):
    """长期记忆实体（不可变快照）。"""
    # [DD-M推断:依据=IC-007 入参定义 + 字段语义]
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID = Field(..., description="记忆唯一 ID（UUIDv4）")
    user_id: UserIdType = Field(..., description="所属用户 ID")
    content: str = Field(..., min_length=1, max_length=1000, description="事实内容")
    importance: int = Field(default=1, ge=1, le=5, description="重要性 [1,5]")
    last_access: datetime = Field(..., description="最近访问时间")
    created_at: datetime = Field(..., description="创建时间")
    trace_id: TraceIdType = Field(..., description="32hex 追踪 ID")

    def touch(self) -> None:
        """刷新最近访问时间（业务侧负责更新持久层）。"""
        # [DD-M推断:依据=MD-013 Memory.touch() 设计意图，DD-S 实施时构造新 Memory]
        ...

    def is_stale(self, now: datetime, ttl_seconds: int) -> bool:
        """判断记忆是否过期（基于 last_access + ttl）。"""
        ...


# [类名] FactExtractionRequest
# [职责] LLM 事实抽取请求模型
# [关联设计规范] MD-013 sm013-extract
# [属性]
#   属性1: conversation str 对话全文
#   属性2: user_id str 用户 ID
#   属性3: max_facts int ∈ [1,20] 最大提取条数
# [方法列表] N/A（DTO）
# [状态机] N/A
# [异常处理]
#   异常1: ValidationError - conversation 为空 / max_facts 越界
# [来源标注] [DD-M推断:依据=MD-013 FactExtractor.extract 入参]
class FactExtractionRequest(BaseModel):
    """LLM 事实抽取请求 DTO。"""
    # [DD-M推断:依据=MD-013 sm013-extract 子模块拆分 + httpx 客户端入参]
    model_config = ConfigDict(extra="forbid")

    conversation: str = Field(..., min_length=1, description="对话全文")
    user_id: UserIdType = Field(..., description="用户 ID")
    max_facts: int = Field(default=5, ge=1, le=20, description="最大提取条数")


# [类名] FactExtractionResult
# [职责] LLM 事实抽取结果模型
# [关联设计规范] MD-013 sm013-extract
# [属性]
#   属性1: facts List[str] 抽取出的事实文本
#   属性2: confidence float ∈ [0,1] 抽取置信度
#   属性3: trace_id str 32hex
# [方法列表] N/A（DTO）
# [来源标注] [DD-M推断:依据=MD-013 FactExtractor.extract 返回]
class FactExtractionResult(BaseModel):
    """LLM 事实抽取结果 DTO。"""
    # [DD-M推断:依据=httpx 响应解析约定 + IC-007 出参]
    model_config = ConfigDict(extra="forbid")

    facts: list[str] = Field(default_factory=list, description="事实列表")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="抽取置信度")
    trace_id: TraceIdType = Field(..., description="32hex 追踪 ID")


# [类名] MemoryQueryResult
# [职责] 记忆检索结果包装（含原始记忆与命中度）
# [关联设计规范] MD-013 sm013-store
# [属性]
#   属性1: memories List[Memory] 命中的记忆
#   属性2: total int 总命中数（未分页时）
# [方法列表] N/A
# [来源标注] [DD-M推断:依据=IC-007 出参 List[Memory] 包装]
class MemoryQueryResult(BaseModel):
    """记忆检索结果包装。"""
    # [DD-M推断:依据=IC-007 出参 + 分页预留]
    model_config = ConfigDict(extra="forbid")

    memories: list[Memory] = Field(default_factory=list, description="命中的记忆")
    total: int = Field(default=0, ge=0, description="总命中数")


# [类名] LRU Victim
# [职责] LRU 淘汰候选标识
# [关联设计规范] MD-013 sm013-evict
# [属性]
#   属性1: memory_id UUID 待淘汰的记忆 ID
#   属性2: last_access datetime 最近访问时间（用于排序）
# [方法列表] N/A
# [来源标注] [DD-M推断:依据=MD-013 LRUEviction.select_victims 返回]
class LRUVictim(BaseModel):
    """LRU 淘汰候选标识。"""
    # [DD-M推断:依据=MD-013 LRUEviction 实现接口]
    model_config = ConfigDict(frozen=True, extra="forbid")

    memory_id: UUID = Field(..., description="待淘汰记忆 ID")
    last_access: datetime = Field(..., description="最近访问时间")
