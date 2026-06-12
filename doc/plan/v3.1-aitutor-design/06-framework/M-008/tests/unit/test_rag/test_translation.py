"""test_translation - 翻译子能力测试

> 对应模块: M-008 子模块 sm008-translation
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008]
"""
from __future__ import annotations

import pytest

# 本地模块
from aitutor.rag.translation.adapter import (
    PDFTranslationAdapter,
    TranslationAdapter,
)


# ========== 测试场景注释 ==========

# [测试场景1: 正常翻译返回字符串]
# 断言: isinstance(result, str) 且长度 > 0
# Mock: M-014 翻译管线客户端

# [测试场景2: pdf2zh 失败 → pdfplumber 降级]
# 断言: 调用 M-014 客户端的 translate() 并返回降级结果
# Mock: M-014 客户端 mock 抛 pdf2zh 失败

# [测试场景3: 3 次降级链全部失败抛 TranslationUnavailableError]
# 断言: 抛 TranslationUnavailableError（对应 E01401）
# Mock: M-014 客户端 3 次降级全失败

# [测试场景4: src_lang/tgt_lang 参数传递]
# 断言: 传入 "en"/"ja" 后 M-014 客户端收到正确参数
# Mock: M-014 客户端 spy

# [测试场景5: M-008 不直接实现 PDF 翻译（模块边界 R28/R29 验证）]
# 断言: PDFTranslationAdapter.translate() 不内嵌 pdf2zh / pdfplumber / lmstudio 代码
# Mock: AST 检查

# [测试场景6: 跨模块调用仅走 M-014 公开 API]
# 断言: PDFTranslationAdapter 仅注入 m014_pipeline_client 不直接 import
# Mock: 无
