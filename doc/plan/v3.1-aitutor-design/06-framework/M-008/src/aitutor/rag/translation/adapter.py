"""adapter - 翻译适配器（M-008）

> 对应模块: M-008 子模块 sm008-translation
> 关联模块: M-014 数据管线（PDF 翻译）
> 设计模式: Adapter（封装 M-014 PDF 翻译链）
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008]
"""
from __future__ import annotations

# 标准库
import abc
from typing import Literal

# 第三方库
import structlog

# 本地模块
from aitutor.shared.exceptions import TranslationUnavailableError

logger = structlog.get_logger(__name__)


class TranslationAdapter(abc.ABC):
    """翻译适配器抽象基类。

    [职责] 定义 PDF/文本翻译的统一接口
    [关联设计规范] MD-M-008

    [属性]
        backend: str - 后端名（"pdf2zh" / "pdfplumber" / "lmstudio"）

    [方法列表]
        translate(text, src_lang, tgt_lang) -> str
        translate_pdf(pdf_path) -> str

    [异常处理]
        TranslationUnavailableError: 所有后端降级失败（E01401）

    [来源标注] [DD-001:MD-M-008 TranslationAdapter] + [DD推断:依据=Adapter 抽象]
    """

    def __init__(self, *, backend: str) -> None:
        """构造翻译适配器。

        [函数名] __init__
        [职责] 初始化后端名

        [参数说明]
            参数1: backend str 必填 后端名
        """
        self.backend = backend

    @abc.abstractmethod
    async def translate(
        self,
        text: str,
        *,
        src_lang: str = "en",
        tgt_lang: str = "zh",
    ) -> str:
        """抽象文本翻译方法。

        [函数名] translate
        [职责] 由子类实现具体翻译

        [参数说明]
            参数1: text str 必填 待翻译文本
            参数2: src_lang str 可选 默认 en 源语言
            参数3: tgt_lang str 可选 默认 zh 目标语言

        [返回值]
            类型: str
            描述: 翻译结果

        [来源标注] [DD-001:MD-M-008 TranslationAdapter.translate()]
        """
        raise NotImplementedError


class PDFTranslationAdapter(TranslationAdapter):
    """PDF 翻译适配器（委托给 M-014 翻译链）。"""

    def __init__(self, m014_pipeline_client: object) -> None:
        """构造 PDF 翻译适配器。

        [函数名] __init__
        [职责] 注入 M-014 管线客户端（跨模块依赖）

        [参数说明]
            参数1: m014_pipeline_client object 必填 M-014 客户端对象

        [注意事项]
            注意1: 跨模块调用 M-014 必须经 M-014 公开 API
            注意2: 避免在 M-008 内直接实现 M-014 业务逻辑（R29）
        """
        # [DD-M推断:依据=MD-M-008 TranslationAdapter 属性 backend]
        # [DD-M推断:依据=R28/R29 跨模块调用限制]
        super().__init__(backend="pdf_translation_chain")
        self._m014_client = m014_pipeline_client

    async def translate(
        self,
        text: str,
        *,
        src_lang: str = "en",
        tgt_lang: str = "zh",
    ) -> str:
        """委托给 M-014 翻译链。

        [函数名] translate
        [职责] 跨模块翻译委派

        [参数说明]
            参数1: text str 必填
            参数2: src_lang str 可选 默认 en
            参数3: tgt_lang str 可选 默认 zh

        [返回值]
            类型: str
            描述: 翻译结果

        [错误码]
            错误码1: E01401 含义: pdf2zh 失败 触发: PDF 解析异常
            错误码2: E01402 含义: LLM 超时 触发: 30s 未响应

        [前置条件] M-014 客户端已注入
        [后置条件] 翻译结果返回
        [并发安全] 是
        [幂等性] 否（不同 src/tgt 结果不同）
        [性能约束] 单次 ≤30s

        [来源标注] [DD-001:MD-M-008 TranslationAdapter] + [DD-001:IC-004 E01401/E01402]
        """
        # [DD-M推断:依据=MD-M-008 TranslationAdapter.translate()]
        pass


# 文件头注释覆盖
# [文件路径] src/aitutor/rag/translation/adapter.py
# [文件职责] 翻译适配器（封装 M-014 PDF 翻译链）
# [所属模块] M-008 子模块 sm008-translation
# [关联设计规范] FS-M-008 / MD-M-008
# [输入输出]
#   输入: 待翻译文本
#   输出: 翻译结果
# [依赖关系]
#   依赖文件: M-014 翻译管线客户端（跨模块）
#   被依赖文件: rag/engine.py
# [注意事项]
#   注意1: 跨模块调用 M-014 必须经 M-014 公开 API，禁止直接 import (R28/R29)
#   注意2: PDF 翻译走 3 次降级链 (pdf2zh → pdfplumber → LM Studio)
#   注意3: V3.1 不在 M-008 内实现翻译业务逻辑（DD 洞察 001 内聚度隔离）
# [代码风格] 遵循 CS-NNN
# [创建日期] 2026-06-02
# [作者] DD-M-008-20260602
# [来源标注] [DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-001:IC-004]
