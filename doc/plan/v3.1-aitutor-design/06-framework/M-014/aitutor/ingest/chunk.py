"""chunk - M-014 文本分块阶段

> 对应模块: M-014
> 关联接口: IC-004（数据入库）
> 关联选型: TS-001 Python（tiktoken 选配）
> 来源标注: [DD-001:MD-M014 sm014-chunk] + [DD-M推断:依据=tiktoken cl100k_base]

[文件职责] 实现 M-014 文本分块 Stage（≤2000tok + 200overlap，按段落边界切分）
[所属模块] M-014
[关联设计规范] MD-M014 / IC-004
[功能描述]
  功能1: 实现按段落优先的分块算法（避免句子被截断）
  功能2: 实现 max_tokens=2000 / overlap=200 默认配置（DD-001:MD-M014）
  功能3: 暴露分块元数据（位置、token 计数、页码）
  功能4: 暴露自定义 tokenizer 接口（可注入 tiktoken / 自研分词器）
[输入输出]
  输入: clean 阶段输出的清洗文本（str）
  输出: List[Chunk] 块列表
[依赖关系]
  依赖文件: aitutor/ingest/models.py（Chunk 模型）
  被依赖文件: aitutor/ingest/pipeline.py（DataPipeline.chunking() 调用）
[注意事项]
  注意1: max_tokens=2000 / overlap=200 不可硬编码（DD-001:MD-M014）
  注意2: chunk_size ∈ [500, 4000]（IC-004 入参校验）
  注意3: overlap ∈ [0, 500]（IC-004 入参校验）
  注意4: 分块必须按段落优先，避免句子被截断（DD-M推断:依据=PDF 段落是语义单元）
  注意5: overlap 不应超过 chunk_size 的 1/4（DD-M推断:依据=context overlap 经验值）
[代码风格] 遵循 CS-AITutor-V3.1（来自DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-014 - 初始版本
[作者] DD-M-014-20260602
[来源标注] [DD-001:MD-M014]
"""

# ================================
# 1. 标准库导入
# ================================
import uuid
from typing import Callable, List, Optional, Protocol

# ================================
# 2. 第三方库导入
# ================================
# DD-M推断:依据=tiktoken 是 OpenAI 推荐的 tokenizer，可选依赖
# import tiktoken

# ================================
# 3. 本地模块导入
# ================================
from aitutor.ingest.models import Chunk


# ============================================================
# Tokenizer 协议（依赖倒置）
# ============================================================


class TokenizerProtocol(Protocol):
    """Tokenizer 协议（依赖倒置）

    [DD-M推断:依据=Template 模式 + 依赖倒置，便于测试时注入 Mock tokenizer]
    """

    def encode(self, text: str) -> List[int]:
        """编码文本为 token 列表。"""
        ...

    def decode(self, tokens: List[int]) -> str:
        """解码 token 列表为文本。"""
        ...


# ============================================================
# 类定义（仅注释框架）
# ============================================================


class Chunker:
    """M-014 文本分块器

    [类] Chunker
    [职责] 将清洗后的文本按段落切分为 ≤max_tokens 的 Chunk 列表
    [关联设计规范] MD-M014 sm014-chunk

    属性:
        max_tokens: 每块最大 token 数（默认 2000）
        overlap: 相邻块 overlap token 数（默认 200）
        tokenizer: tokenizer 实例（可注入，默认 None 使用按字符估算）
    方法列表:
        方法1: chunk(text: str, doc_id: str) → List[Chunk] - 执行分块
        方法2: _count_tokens(text: str) → int - 计算 token 数
        方法3: _split_by_paragraphs(text: str) → List[str] - 段落切分
    异常处理:
        异常1: ValueError - max_tokens < 500 或 > 4000
        异常2: ValueError - overlap < 0 或 > 500
    [来源标注] [DD-001:MD-M014]
    """

    DEFAULT_MAX_TOKENS = 2000
    DEFAULT_OVERLAP = 200
    MIN_CHUNK_SIZE = 500
    MAX_CHUNK_SIZE = 4000
    MIN_OVERLAP = 0
    MAX_OVERLAP = 500

    def __init__(
        self,
        *,
        max_tokens: int = 2000,
        overlap: int = 200,
        tokenizer: Optional[TokenizerProtocol] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """初始化 Chunker。

        Args:
            max_tokens: 每块最大 token 数（默认 2000，[500, 4000]）
            overlap: overlap token 数（默认 200，[0, 500]）
            tokenizer: 可选 tokenizer 实例（默认 None 使用按字符估算）
            trace_id: 追踪 ID（32hex，可选）

        Raises:
            ValueError: 参数超出合法范围
        """
        ...

    def chunk(self, text: str, *, doc_id: str) -> List[Chunk]:
        """执行文本分块

        [函数名] chunk
        [职责] 将清洗后文本分块为 List[Chunk]
        [关联接口契约] IC-004
        [参数说明]
            text: 清洗后文本
            doc_id: 所属文档 ID（UUIDv4）
        [返回值]
            类型: List[Chunk]
            描述: 分块结果
        [错误码] 无（纯计算，不抛业务异常）
        [前置条件] text 非空，doc_id 合法 UUIDv4
        [后置条件] 每块 token_count ≤ max_tokens
        [并发安全] 线程安全（无共享可变状态）
        [幂等性] 是（相同输入必产生相同 Chunk 列表）
        [性能约束] 10MB 文本 ≤10s
        [来源标注] [DD-001:MD-M014]

        Args:
            text: 清洗后文本
            doc_id: 所属文档 ID（UUIDv4）

        Returns:
            分块结果
        """
        ...

    def _count_tokens(self, text: str) -> int:
        """计算文本 token 数（私有）

        Args:
            text: 文本

        Returns:
            token 数
        """
        ...

    def _split_by_paragraphs(self, text: str) -> List[str]:
        """按段落切分（私有）

        保留段落边界，作为分块的优先切分单位。

        Args:
            text: 文本

        Returns:
            段落列表
        """
        ...

    def _build_chunk(
        self,
        text: str,
        *,
        doc_id: str,
        position: int,
        page_number: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> Chunk:
        """构造 Chunk 实例（私有）

        Args:
            text: 块文本
            doc_id: 所属文档 ID
            position: 块在文档中的位置序号
            page_number: 所在 PDF 页码（可空）
            metadata: 附加元数据（可空）

        Returns:
            Chunk 实例
        """
        ...
