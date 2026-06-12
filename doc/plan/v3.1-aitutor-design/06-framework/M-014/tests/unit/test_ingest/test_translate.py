"""test_translate - M-014 翻译子能力测试

> 对应模块: M-014
> 来源标注: [DD-001:MD-M014 sm014-translate]

[文件职责] 3 个翻译后端 + 工厂方法单元测试
[所属模块] M-014
[测试策略] 单元测试
[用例规划] 8 用例
[来源标注] [DD-001:MD-M014]
"""

# from aitutor.ingest.translate import (
#     PDF2ZhTranslator,
#     PDFPlumberTranslator,
#     LMStudioTranslator,
#     create_translator,
#     FALLBACK_ORDER,
# )


# ============================================================
# 工厂方法测试
# ============================================================


def test_create_translator_pdf2zh() -> None:
    """场景 1: create_translator("pdf2zh") 返回 PDF2ZhTranslator"""
    ...


def test_create_translator_pdfplumber() -> None:
    """场景 2: create_translator("pdfplumber") 返回 PDFPlumberTranslator"""
    ...


def test_create_translator_lmstudio() -> None:
    """场景 3: create_translator("lmstudio") 返回 LMStudioTranslator"""
    ...


def test_create_translator_invalid_backend_raises() -> None:
    """场景 4: 非法 backend 抛 ValueError"""
    ...


# ============================================================
# 降级链测试
# ============================================================


def test_fallback_order_is_pdf2zh_pdfplumber_lmstudio() -> None:
    """场景 5: 降级链顺序固定

    断言: FALLBACK_ORDER == ("pdf2zh", "pdfplumber", "lmstudio")
    """
    ...


# ============================================================
# 后端特定测试
# ============================================================


def test_pdf2zh_translate_failure_raises_translation_failed() -> None:
    """场景 6: pdf2zh 失败抛 TranslationFailedError"""
    ...


def test_lmstudio_timeout_raises_llm_timeout_error() -> None:
    """场景 7: LM Studio 超时抛 LLMTimeoutError"""
    ...


def test_pdfplumber_scan_pdf_raises_translation_failed() -> None:
    """场景 8: pdfplumber 处理扫描版 PDF 抛 TranslationFailedError"""
    ...
