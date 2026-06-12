"""models - M-014 数据管线领域模型定义

> 对应模块: M-014
> 关联接口: IC-004（数据入库）
> 关联选型: TS-001 Python / TS-018 pydantic
> 来源标注: [DD-001:MD-M014] + [DD-M推断:依据=pydantic v2 dataclass 风格]

[文件职责] 定义 M-014 数据管线运行期间的全部领域模型（Pydantic BaseModel）
[所属模块] M-014
[关联设计规范] MD-M014 / IC-004
[功能描述]
  功能1: 定义 ProcessResult 入库结果模型（IC-004 出参契约对应）
  功能2: 定义 Chunk 分块结果模型（含 token 计数、来源元数据）
  功能3: 定义 PipelineStage / ProcessStatus / TranslationBackend 枚举类型
  功能4: 定义 ThreadPoolConfig 线程池配置
[输入输出]
  输入: 上游 M-014 子能力（clean/chunk/ingester/translate）实例化
  输出: 标准化数据模型，被 DataPipeline 与 API 层（aitutor/api/v1/ingest.py）序列化
[依赖关系]
  依赖文件: 无（仅依赖标准库 typing + pydantic）
  被依赖文件: aitutor/ingest/pipeline.py + clean.py + chunk.py + ingester.py + state_machine.py
[注意事项]
  注意1: 全部模型继承 pydantic.BaseModel，启用 model_config = ConfigDict(frozen=False)
  注意2: ProcessResult.doc_id 必须为 UUIDv4（DD-001:IC-004 强校验）
  注意3: ProcessResult.status 取值受 ProcessStatus 枚举约束
  注意4: ProcessResult.translation_backend 标注实际使用的翻译后端，便于审计
[代码风格] 遵循 CS-AITutor-V3.1（来自DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-014 - 初始版本
[作者] DD-M-014-20260602
[来源标注] [DD-001:MD-M014/IC-004] + [DD-M推断:依据=pydantic 2.x BaseModel]
"""

# ================================
# 1. 标准库导入
# ================================
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

# ================================
# 2. 第三方库导入
# ================================
from pydantic import BaseModel, ConfigDict, Field

# ================================
# 3. 本地模块导入
# ================================
# (本文件为叶节点模型层，不依赖任何业务模块 — 符合 soul 4.7 models 依赖约束)


# ============================================================
# 枚举类型定义
# ============================================================


class ProcessStatus(str, Enum):
    """入库最终状态枚举

    [DD-001:IC-004] 出参 status 字段取值
    """

    READY = "READY"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class PipelineStage(str, Enum):
    """管线运行阶段枚举

    [DD-001:MD-M014] 状态机 7 个节点
    """

    PENDING = "PENDING"
    TRANSLATING = "TRANSLATING"
    CLEANING = "CLEANING"
    CLEANING_PARTIAL = "CLEANING_PARTIAL"
    CHUNKING = "CHUNKING"
    INGESTING = "INGESTING"
    READY = "READY"
    FAILED = "FAILED"


class TranslationBackend(str, Enum):
    """翻译后端枚举（3 次降级链）

    [DD-001:MD-M014] pdf2zh → pdfplumber → lmstudio
    """

    PDF2ZH = "pdf2zh"
    PDFPLUMBER = "pdfplumber"
    LMSTUDIO = "lmstudio"


# ============================================================
# 配置模型
# ============================================================


class ThreadPoolConfig(BaseModel):
    """线程池配置

    [DD-M推断:依据=Template + ThreadPool 模式，pipeline 需并发调度翻译/分块]

    属性:
        max_workers: 最大工作线程数
        translation_concurrency: 翻译阶段并发上限（≤ 2 避免 LM Studio 限流）
    """

    model_config = ConfigDict(frozen=False)

    max_workers: int = Field(default=4, ge=1, le=16, description="最大工作线程数")
    translation_concurrency: int = Field(default=2, ge=1, le=4, description="翻译阶段并发上限")


# ============================================================
# 业务模型
# ============================================================


class Chunk(BaseModel):
    """分块结果

    [DD-001:MD-M014] Chunker.run() 输出
    [DD-001:IC-004] 入库单元（写入 ChromaDB + SQLite）

    属性:
        chunk_id: 块 ID（UUIDv4）
        doc_id: 所属文档 ID
        text: 块文本（已清洗）
        token_count: token 数（≤ chunk_size）
        position: 块在文档中的位置序号
        page_number: 所在 PDF 页码（可空，非 PDF 文档为 None）
        metadata: 附加元数据（来源 PDF、章节、翻译后端等）
    """

    model_config = ConfigDict(frozen=False)

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="块 ID（UUIDv4）")
    doc_id: str = Field(..., description="所属文档 ID（UUIDv4）")
    text: str = Field(..., min_length=1, description="块文本（已清洗）")
    token_count: int = Field(..., ge=1, description="token 数（≤ chunk_size）")
    position: int = Field(..., ge=0, description="块在文档中的位置序号")
    page_number: Optional[int] = Field(default=None, ge=1, description="所在 PDF 页码")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")


class ProcessResult(BaseModel):
    """入库最终结果

    [DD-001:IC-004] POST /api/v1/ingest 出参契约

    属性:
        doc_id: 文档 ID（UUIDv4）— 必填
        status: 状态（READY / FAILED / PARTIAL）— 必填
        chunk_count: chunk 数 — 必填
        translation_backend: 使用的翻译后端（便于审计与降级追溯）— 必填
        duration_ms: 处理耗时（毫秒）— 必填
        trace_id: 追踪 ID（32hex）— 必填
        error_code: 错误码（仅 FAILED 时填充）— 可选
        error_message: 错误描述（仅 FAILED 时填充）— 可选
    """

    model_config = ConfigDict(frozen=False)

    doc_id: str = Field(..., description="文档 ID（UUIDv4）")
    status: ProcessStatus = Field(..., description="入库状态")
    chunk_count: int = Field(..., ge=0, description="chunk 数")
    translation_backend: TranslationBackend = Field(..., description="使用的翻译后端")
    duration_ms: int = Field(..., ge=0, description="处理耗时（毫秒）")
    trace_id: str = Field(..., min_length=32, max_length=32, description="追踪 ID（32hex）")
    error_code: Optional[str] = Field(default=None, description="错误码（E014xx）")
    error_message: Optional[str] = Field(default=None, description="错误描述")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间（UTC）")
    chunks: List[Chunk] = Field(default_factory=list, description="入库的 chunk 列表（用于审计）")


# ============================================================
# 占位辅助类（无业务代码 — 仅注释框架，供 DD-S 后续填充）
# ============================================================


class _PipelineContext(BaseModel):
    """管线运行时上下文（私有，供 DataPipeline 内部使用）

    [DD-M推断:依据=Template 模式需要在阶段间传递共享状态]
    """

    model_config = ConfigDict(frozen=False)

    pdf_id: str = Field(..., description="PDF 任务 ID（UUIDv4）")
    pdf_path: str = Field(..., description="PDF 文件绝对路径")
    user_id: str = Field(..., description="用户 ID（强校验）")
    trace_id: str = Field(..., min_length=32, max_length=32, description="trace_id（32hex）")
    current_stage: PipelineStage = Field(default=PipelineStage.PENDING, description="当前阶段")
    raw_text: Optional[str] = Field(default=None, description="翻译阶段原始输出文本")
    cleaned_text: Optional[str] = Field(default=None, description="清洗阶段输出文本")
    chunks: List[Chunk] = Field(default_factory=list, description="分块阶段输出")
    active_backend: Optional[TranslationBackend] = Field(default=None, description="实际生效的翻译后端")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="启动时间")
