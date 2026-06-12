"""adapter - 索引策略适配器（M-008）

> 对应模块: M-008 子模块 sm008-indexing
> 关联接口: IC-003 top_k_chunks
> 设计模式: Adapter（封装 ChromaIndexAdapter）
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-001:IC-003]
"""
from __future__ import annotations

# 标准库
import abc
from typing import List, Optional

# 第三方库
import structlog

# 本地模块
from aitutor.rag.indexing.chroma import ChromaCollection
from aitutor.shared.types import Chunk, Embedding

logger = structlog.get_logger(__name__)


class IndexAdapter(abc.ABC):
    """索引策略适配器抽象基类。

    [职责] 定义索引后端的统一接口
    [关联设计规范] MD-M-008

    [属性]
        backend_name: str - 后端名

    [方法列表]
        query(query_embedding, top_k) -> List[Chunk]
        add(chunks) -> None
        delete(chunk_ids) -> None

    [来源标注] [DD-001:MD-M-008 ChromaIndexAdapter] + [DD推断:依据=Adapter 抽象]
    """

    def __init__(self, *, backend_name: str) -> None:
        """构造索引适配器。

        [函数名] __init__
        [职责] 初始化后端名

        [参数说明]
            参数1: backend_name str 必填 后端名（如 "chroma"）
        """
        self.backend_name = backend_name

    @abc.abstractmethod
    async def query(
        self, query_embedding: Embedding, top_k: int = 5
    ) -> List[Chunk]:
        """抽象查询方法。

        [函数名] query
        [职责] 由子类实现具体查询逻辑
        [关联接口契约] IC-003 top_k_chunks

        [参数说明]
            参数1: query_embedding Embedding 必填 查询向量
            参数2: top_k int 可选 默认 5 规则 [1, 20]

        [返回值]
            类型: List[Chunk]
            描述: 检索结果

        [来源标注] [DD-001:IC-003] + [DD-001:MD-M-008]
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def add(self, chunks: List[Chunk]) -> None:
        """抽象添加 chunks 方法。

        [函数名] add
        [职责] 由子类实现具体添加逻辑

        [参数说明]
            参数1: chunks List[Chunk] 必填 待添加 chunks
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def delete(self, chunk_ids: List[str]) -> None:
        """抽象删除 chunks 方法。

        [函数名] delete
        [职责] 由子类实现具体删除逻辑

        [参数说明]
            参数1: chunk_ids List[str] 必填 待删除 chunk_ids
        """
        raise NotImplementedError


class ChromaIndexAdapter(IndexAdapter):
    """ChromaDB 索引适配器（默认实现）。"""

    def __init__(self, collection: ChromaCollection) -> None:
        """构造 ChromaDB 索引适配器。

        [函数名] __init__
        [职责] 注入 ChromaCollection 包装

        [参数说明]
            参数1: collection ChromaCollection 必填 集合封装对象
        """
        # [DD-M推断:依据=MD-M-008 ChromaIndexAdapter 属性 collection]
        super().__init__(backend_name="chroma")
        self._collection = collection

    async def query(
        self, query_embedding: Embedding, top_k: int = 5
    ) -> List[Chunk]:
        """委托给 ChromaCollection.query 并转换为 Chunk。

        [函数名] query
        [职责] Adapter 委派 + 类型转换

        [参数说明]
            参数1: query_embedding Embedding 必填
            参数2: top_k int 可选 默认 5

        [返回值]
            类型: List[Chunk]
            描述: 检索结果

        [来源标注] [DD-001:MD-M-008] + [DD-001:IC-003]
        """
        # [DD-M推断:依据=MD-M-008 ChromaIndexAdapter.query()]
        pass

    async def add(self, chunks: List[Chunk]) -> None:
        """添加 chunks 到 ChromaDB 集合。

        [函数名] add
        [职责] 批量 upsert

        [参数说明]
            参数1: chunks List[Chunk] 必填 待添加 chunks

        [前置条件] 集合已创建
        [后置条件] chunks 已持久化
        [并发安全] 否（ChromaDB 单写者）
        [幂等性] 是 / 幂等键: chunk_id

        [来源标注] [DD-001:MD-M-008 ChromaIndexAdapter.add()]
        """
        # [DD-M推断:依据=MD-M-008 ChromaIndexAdapter.add()]
        pass

    async def delete(self, chunk_ids: List[str]) -> None:
        """从 ChromaDB 集合删除 chunks。

        [函数名] delete
        [职责] 批量删除

        [参数说明]
            参数1: chunk_ids List[str] 必填 待删除 chunk_ids

        [前置条件] 集合已创建
        [后置条件] chunks 已删除
        [并发安全] 否
        [幂等性] 是

        [来源标注] [DD-001:MD-M-008 ChromaIndexAdapter.delete()]
        """
        # [DD-M推断:依据=MD-M-008 ChromaIndexAdapter.delete()]
        pass


# 文件头注释覆盖
# [文件路径] src/aitutor/rag/indexing/adapter.py
# [文件职责] 索引策略适配器（Template + Adapter 组合）
# [所属模块] M-008 子模块 sm008-indexing
# [关联设计规范] FS-M-008 / MD-M-008 / IC-003
# [输入输出]
#   输入: query_embedding / chunks / chunk_ids
#   输出: List[Chunk] / None
# [依赖关系]
#   依赖文件: rag/indexing/chroma.py, shared/types.py
#   被依赖文件: rag/engine.py, ingest/ingester.py (M-014 跨模块调用)
# [注意事项]
#   注意1: 新增索引后端（如 Qdrant / Milvus）只需继承 IndexAdapter
#   注意2: 跨模块调用 M-014 入库时，必须经 IndexAdapter 接口
#   注意3: 集合名与 user_id 关联，敏感操作需鉴权
# [代码风格] 遵循 CS-NNN
# [创建日期] 2026-06-02
# [作者] DD-M-008-20260602
# [来源标注] [DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-001:IC-003]
