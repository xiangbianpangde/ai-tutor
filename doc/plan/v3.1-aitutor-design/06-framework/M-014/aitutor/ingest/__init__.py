"""ingest - M-014 数据管线模块入口

> 对应模块: M-014
> 关联接口: IC-004（数据入库，API-004/IF-004）
> 关联选型: TS-008 pdf2zh / TS-004 ChromaDB / TS-006 httpx
> 来源标注: [DD-001:FS-M014/MD-M014] + [DD-M推断:依据=Python src layout 最佳实践]
> 设计模式: Template + ThreadPool（DD-001:MD-M014）

[文件职责] M-014 数据管线模块初始化与公共接口 re-export
[所属模块] M-014
[关联设计规范] FS-M014 / MD-M014
[功能描述]
  功能1: 暴露 PDF 翻译→清洗→分块→入库 4 阶段管线入口（DataPipeline）
  功能2: 暴露 ProcessResult / Chunk / PipelineStage / TranslationBackend 等领域模型
  功能3: 暴露 3 个翻译后端（pdf2zh / pdfplumber / lmstudio）的工厂与基类
  功能4: 暴露 TextCleaner / Chunker / Ingester 等 Stage 子能力类
[输入输出]
  输入: 上游调用方（aitutor/api/v1/ingest.py）通过 from aitutor.ingest import ... 引入
  输出: 暴露 DataPipeline、ProcessResult、TextCleaner、Chunker、Ingester 等公开类
[依赖关系]
  依赖文件: aitutor/ingest/pipeline.py + clean.py + chunk.py + ingester.py + translate/*
  被依赖文件: aitutor/api/v1/ingest.py（M-002 API 网关调用入口）
[注意事项]
  注意1: 本文件仅做 re-export，禁止添加业务逻辑（DD-M推断:依据=soul 4.8 单一职责原则）
  注意2: 模块导出列表必须与 docs/api/openapi.yaml 保持一致（DD-M推断:依据=IC-004 契约）
  注意3: 跨模块依赖仅允许依赖 M-006 事件总线与 M-017 存储（DD-001:MD-M014 来源标注）
[代码风格] 遵循 CS-AITutor-V3.1（来自DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-014 - 初始版本
[作者] DD-M-014-20260602
[来源标注] [DD-001:FS-M014/MD-M014] + [DD-M推断:依据=soul 4.7 文件结构合规]
"""
from aitutor.ingest.clean import TextCleaner
from aitutor.ingest.chunk import Chunker
from aitutor.ingest.exceptions import (
    IngestError,
    TranslationFailedError,
    LLMTimeoutError,
    CleanDedupExceededError,
    FileTooLargeError,
    InvalidFileTypeError,
)
from aitutor.ingest.ingester import Ingester
from aitutor.ingest.models import (
    Chunk,
    PipelineStage,
    ProcessResult,
    ProcessStatus,
    TranslationBackend,
)
from aitutor.ingest.pipeline import DataPipeline
from aitutor.ingest.state_machine import PipelineStateMachine
from aitutor.ingest.translate import (
    BaseTranslator,
    LMStudioTranslator,
    PDF2ZhTranslator,
    PDFPlumberTranslator,
    create_translator,
)

__all__ = [
    # 管线
    "DataPipeline",
    "PipelineStateMachine",
    # 阶段
    "TextCleaner",
    "Chunker",
    "Ingester",
    # 翻译
    "BaseTranslator",
    "PDF2ZhTranslator",
    "PDFPlumberTranslator",
    "LMStudioTranslator",
    "create_translator",
    # 模型
    "Chunk",
    "ProcessResult",
    "ProcessStatus",
    "PipelineStage",
    "TranslationBackend",
    # 异常
    "IngestError",
    "TranslationFailedError",
    "LLMTimeoutError",
    "CleanDedupExceededError",
    "FileTooLargeError",
    "InvalidFileTypeError",
]
