"""base - M-014 翻译器抽象基类

> 对应模块: M-014
> 关联接口: IC-004
> 来源标注: [DD-001:MD-M014] + [DD-M推断:依据=Strategy 模式抽象基类]

[文件职责] 定义 3 个翻译后端共享的抽象基类
[所属模块] M-014
[关联设计规范] MD-M014
[功能描述]
  功能1: 定义 BaseTranslator 抽象基类
  功能2: 声明 translate() / health_check() 抽象方法
  功能3: 暴露后端标识（backend 属性）
[输入输出]
  输入: 子类实现（PDF2ZhTranslator 等）
  输出: 统一的 BaseTranslator 协议
[依赖关系]
  依赖文件: aitutor/ingest/exceptions.py
  被依赖文件: translate/pdf2zh.py + translate/pdfplumber.py + translate/lmstudio.py
[注意事项]
  注意1: 抽象方法必须由子类实现（DD-001:CS-AITutor-V3.1 §抽象基类）
  注意2: 子类必须声明 backend 类属性（DD-M推断:依据=Factory 模式）
[代码风格] 遵循 CS-AITutor-V3.1（来自DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-014 - 初始版本
[作者] DD-M-014-20260602
[来源标注] [DD-001:MD-M014] + [DD-M推断:依据=Strategy 模式]
"""

# ================================
# 1. 标准库导入
# ================================
from abc import ABC, abstractmethod
from typing import Optional

# ================================
# 2. 第三方库导入
# ================================
# (无)

# ================================
# 3. 本地模块导入
# ================================
from aitutor.ingest.exceptions import IngestError


# ============================================================
# 抽象基类
# ============================================================


class BaseTranslator(ABC):
    """M-014 翻译器抽象基类

    [类] BaseTranslator
    [职责] 定义 3 个翻译后端共享的协议
    [关联设计规范] MD-M014

    属性:
        backend: 后端标识（子类必须声明，如 "pdf2zh"）
        trace_id: 追踪 ID（32hex）
    方法列表:
        方法1: translate(pdf_path: str) → str - 翻译 PDF 为文本
        方法2: health_check() → bool - 健康检查（用于降级决策）
    异常处理:
        异常1: TranslationFailedError - 翻译失败
        异常2: LLMTimeoutError - LM Studio 超时
    [来源标注] [DD-001:MD-M014]
    """

    backend: str = ""  # 子类必须覆盖

    def __init__(self, *, trace_id: Optional[str] = None, config: Optional[dict] = None) -> None:
        """初始化 BaseTranslator。

        Args:
            trace_id: 追踪 ID（32hex，可选）
            config: 后端特定配置（可空）
        """
        ...

    @abstractmethod
    def translate(self, pdf_path: str) -> str:
        """翻译 PDF 为纯文本

        [函数名] translate
        [职责] 抽象方法，将 PDF 文件翻译为纯文本
        [参数说明]
            pdf_path: PDF 文件绝对路径
        [返回值]
            类型: str
            描述: 翻译后的纯文本
        [错误码]
            E01401: 翻译失败（子类抛出 TranslationFailedError）
            E01402: LM Studio 超时（LMStudioTranslator 抛出 LLMTimeoutError）
        [前置条件] pdf_path 存在且可读
        [后置条件] 返回非空字符串
        [并发安全] 子类自行实现（默认否）
        [性能约束] 10 页 PDF ≤30s
        [来源标注] [DD-001:MD-M014]

        Args:
            pdf_path: PDF 文件绝对路径

        Returns:
            翻译后的纯文本
        """
        ...

    def health_check(self) -> bool:
        """健康检查（默认实现）

        子类可覆盖以实现更精细的健康检查（如 ping LM Studio 服务）。

        Returns:
            True 表示后端可用
        """
        ...
