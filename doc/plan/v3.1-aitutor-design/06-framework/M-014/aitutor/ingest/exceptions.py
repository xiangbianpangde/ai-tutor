"""exceptions - M-014 数据管线自定义异常类型

> 对应模块: M-014
> 关联接口: IC-004（数据入库）
> 来源标注: [DD-001:MD-M014] + [DD-M推断:依据=soul CS-AITutor-V3.1 §5.3 异常转换]

[文件职责] 定义 M-014 数据管线运行期间的自定义异常类型（继承 BusinessError / SystemError）
[所属模块] M-014
[关联设计规范] MD-M014 / IC-004
[功能描述]
  功能1: 定义 IngestError 根异常
  功能2: 定义 TranslationFailedError（E01401 翻译后端全部失败）
  功能3: 定义 LLMTimeoutError（E01402 LM Studio 超时）
  功能4: 定义 CleanDedupExceededError（E01403 清洗后重复率>30%）
  功能5: 定义 FileTooLargeError（E01404 文件>100MB）
  功能6: 定义 InvalidFileTypeError（E01405 文件类型非 PDF）
[输入输出]
  输入: M-014 各阶段（translate/clean/chunk/ingest）抛出
  输出: 被 DataPipeline 捕获后转换为 ProcessResult.status=FAILED
[依赖关系]
  依赖文件: aitutor/shared/exceptions.py（BusinessError / SystemError 根类）
  被依赖文件: aitutor/ingest/pipeline.py + translate/* + clean.py + chunk.py + ingester.py
[注意事项]
  注意1: 全部异常继承 aitutor.shared.exceptions.BusinessError 或 SystemError
  注意2: 异常消息必须含 trace_id（DD-001:CS-AITutor-V3.1 §5.2 日志记录）
  注意3: 异常链保留 raise ... from e（DD-001:CS-AITutor-V3.1 §5.3）
[代码风格] 遵循 CS-AITutor-V3.1（来自DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-014 - 初始版本
[作者] DD-M-014-20260602
[来源标注] [DD-001:MD-M014] + [DD-M推断:依据=CS-AITutor-V3.1 §5.3 异常体系]
"""

# ================================
# 1. 标准库导入
# ================================
from typing import Optional

# ================================
# 2. 第三方库导入
# ================================
# (无)

# ================================
# 3. 本地模块导入
# ================================
# (本文件为异常层，依赖 shared 层 — 符合 soul 4.7 models 依赖约束)
# DD-M推断:shared.exceptions 包含 BusinessError / SystemError 根类
# from aitutor.shared.exceptions import BusinessError, SystemError


# ============================================================
# 异常类定义（仅注释框架，无业务代码）
# ============================================================


class IngestError(Exception):
    """M-014 数据管线根异常

    [DD-001:MD-M014] 所有 M-014 自定义异常的基类
    [DD-M推断:依据=soul CS §5.3 业务异常 → BusinessError]

    属性:
        error_code: 错误码（E014xx 格式）
        trace_id: 追踪 ID（32hex）
        message: 异常描述
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "E01400",
        trace_id: Optional[str] = None,
    ) -> None:
        """初始化 IngestError。

        Args:
            message: 异常描述
            error_code: 错误码（默认 E01400）
            trace_id: 追踪 ID（32hex，可选）
        """
        ...


class TranslationFailedError(IngestError):
    """翻译后端全部失败异常

    [DD-001:MD-M014] E01401 — pdf2zh → pdfplumber → lmstudio 3 次降级均失败

    属性:
        attempted_backends: 已尝试的翻译后端列表
    """

    def __init__(
        self,
        message: str,
        *,
        attempted_backends: list[str],
        trace_id: Optional[str] = None,
    ) -> None:
        """初始化 TranslationFailedError。

        Args:
            message: 异常描述
            attempted_backends: 已尝试的翻译后端列表（按尝试顺序）
            trace_id: 追踪 ID（32hex，可选）
        """
        ...


class LLMTimeoutError(IngestError):
    """LLM 调用超时异常

    [DD-001:MD-M014] E01402 — LM Studio 调用 >30s

    属性:
        timeout_seconds: 超时阈值（秒）
        retried: 是否已重试 1 次
    """

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: int = 30,
        retried: bool = False,
        trace_id: Optional[str] = None,
    ) -> None:
        """初始化 LLMTimeoutError。

        Args:
            message: 异常描述
            timeout_seconds: 超时阈值（默认 30s）
            retried: 是否已重试 1 次
            trace_id: 追踪 ID（32hex，可选）
        """
        ...


class CleanDedupExceededError(IngestError):
    """清洗后重复率超阈值异常（不阻塞）

    [DD-001:MD-M014] E01403 — 清洗后重复率仍 >30%，仅 WARN

    属性:
        dedup_ratio: 实际重复率
        threshold: 重复率阈值（默认 0.3）
    """

    def __init__(
        self,
        message: str,
        *,
        dedup_ratio: float,
        threshold: float = 0.3,
        trace_id: Optional[str] = None,
    ) -> None:
        """初始化 CleanDedupExceededError。

        Args:
            message: 异常描述
            dedup_ratio: 实际重复率
            threshold: 重复率阈值（默认 0.3）
            trace_id: 追踪 ID（32hex，可选）
        """
        ...


class FileTooLargeError(IngestError):
    """文件超限异常

    [DD-001:IC-004] E01404 — 文件大小 >100MB

    属性:
        file_size_bytes: 实际文件大小
        max_size_bytes: 最大允许大小（默认 100MB）
    """

    def __init__(
        self,
        message: str,
        *,
        file_size_bytes: int,
        max_size_bytes: int = 100 * 1024 * 1024,
        trace_id: Optional[str] = None,
    ) -> None:
        """初始化 FileTooLargeError。

        Args:
            message: 异常描述
            file_size_bytes: 实际文件大小（字节）
            max_size_bytes: 最大允许大小（默认 100MB）
            trace_id: 追踪 ID（32hex，可选）
        """
        ...


class InvalidFileTypeError(IngestError):
    """文件类型非法异常

    [DD-001:IC-004] E01405 — 上传文件非 PDF 格式

    属性:
        actual_mime: 实际 MIME 类型
        allowed_mime: 允许的 MIME 类型列表
    """

    def __init__(
        self,
        message: str,
        *,
        actual_mime: str,
        allowed_mime: list[str],
        trace_id: Optional[str] = None,
    ) -> None:
        """初始化 InvalidFileTypeError。

        Args:
            message: 异常描述
            actual_mime: 实际 MIME 类型
            allowed_mime: 允许的 MIME 类型列表
            trace_id: 追踪 ID（32hex，可选）
        """
        ...
