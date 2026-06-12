"""translate - M-014 翻译子能力命名空间

> 对应模块: M-014
> 关联接口: IC-004（数据入库）
> 关联选型: TS-008 pdf2zh / pdfplumber / LM Studio
> 来源标注: [DD-001:MD-M014 sm014-translate] + [DD-M推断:依据=Strategy 模式]

[文件职责] M-014 翻译子能力命名空间入口（3 个翻译后端 + 工厂方法）
[所属模块] M-014
[关联设计规范] MD-M014
[功能描述]
  功能1: 暴露 BaseTranslator 抽象基类
  功能2: 暴露 3 个具体后端（PDF2ZhTranslator / PDFPlumberTranslator / LMStudioTranslator）
  功能3: 暴露 create_translator() 工厂方法（按 backend 字面量装配）
[输入输出]
  输入: DataPipeline._translate() 调用 create_translator(backend)
  输出: 对应后端的 BaseTranslator 子类实例
[依赖关系]
  依赖文件: translate/base.py + translate/pdf2zh.py + translate/pdfplumber.py + translate/lmstudio.py
  被依赖文件: aitutor/ingest/pipeline.py（DataPipeline 翻译阶段）
[注意事项]
  注意1: 子能力命名空间隔离（与 M-008 RAG 翻译子能力同样模式，DD-001:FS-M008 启示）
  注意2: 三个后端按 [pdf2zh, pdfplumber, lmstudio] 顺序降级（DD-001:MD-M014 E01401）
  注意3: create_translator 工厂返回的实例必须可重入（DD-M推断:依据=Template 模式）
[代码风格] 遵循 CS-AITutor-V3.1（来自DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-014 - 初始版本
[作者] DD-M-014-20260602
[来源标注] [DD-001:MD-M014] + [DD-M推断:依据=Strategy + Factory 模式]
"""

# ================================
# 本地模块导入
# ================================
from aitutor.ingest.translate.base import BaseTranslator
from aitutor.ingest.translate.lmstudio import LMStudioTranslator
from aitutor.ingest.translate.pdf2zh import PDF2ZhTranslator
from aitutor.ingest.translate.pdfplumber import PDFPlumberTranslator

__all__ = [
    "BaseTranslator",
    "PDF2ZhTranslator",
    "PDFPlumberTranslator",
    "LMStudioTranslator",
    "create_translator",
    "FALLBACK_ORDER",
]


# ============================================================
# 工厂方法（仅注释框架）
# ============================================================


# 降级链顺序（DD-001:MD-M014 E01401 强制）
FALLBACK_ORDER: tuple = (
    "pdf2zh",
    "pdfplumber",
    "lmstudio",
)


def create_translator(
    backend: str,
    *,
    config: Optional[dict] = None,
    trace_id: Optional[str] = None,
) -> BaseTranslator:
    """创建翻译后端实例（工厂方法）

    [函数名] create_translator
    [职责] 根据 backend 字面量返回对应的 BaseTranslator 子类实例
    [关联接口契约] IC-004（API-004/IF-004）
    [参数说明]
        backend: 翻译后端标识（"pdf2zh" | "pdfplumber" | "lmstudio"）
        config: 后端特定配置（可空）
        trace_id: 追踪 ID（32hex，可选）
    [返回值]
        类型: BaseTranslator
        描述: 对应后端的翻译器实例
    [错误码]
        E01408: backend 不在合法集合内（DD-M推断:依据=IC-004 错误码体系扩展）
    [前置条件] backend ∈ {"pdf2zh", "pdfplumber", "lmstudio"}
    [后置条件] 返回的实例可立即调用 translate()
    [并发安全] 是（每个实例独立，无共享状态）
    [来源标注] [DD-001:MD-M014]

    Args:
        backend: 翻译后端标识
        config: 后端特定配置
        trace_id: 追踪 ID（32hex，可选）

    Returns:
        BaseTranslator 子类实例

    Raises:
        ValueError: backend 非法
    """
    ...
