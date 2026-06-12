"""test_indexing - 索引子能力测试

> 对应模块: M-008 子模块 sm008-indexing
> 来源标注: [DD-001:FS-M-008] + [DD-001:MD-M-008]
"""
from __future__ import annotations

import pytest

# 本地模块
from aitutor.rag.indexing.chroma import ChromaCollection
from aitutor.rag.indexing.adapter import ChromaIndexAdapter, IndexAdapter


# ========== 测试场景注释 ==========

# [测试场景1: ChromaCollection.query 返回 top-k chunks]
# 断言: len(results) <= n_results
# Mock: chromadb.Client + Collection（内存模式）

# [测试场景2: ChromaIndexAdapter.query 委派给 ChromaCollection]
# 断言: 返回 List[Chunk] 类型
# Mock: ChromaCollection.query 返回固定 dict

# [测试场景3: add chunks 幂等性]
# 断言: 重复 add 相同 chunk_id 不重复插入
# Mock: ChromaCollection mock

# [测试场景4: delete 幂等性]
# 断言: 重复 delete 相同 chunk_id 不抛异常
# Mock: ChromaCollection mock

# [测试场景5: 集合不存在抛 CollectionNotFoundError]
# 断言: 抛 CollectionNotFoundError
# Mock: chromadb mock

# [测试场景6: 并发查询线程安全（ChromaDB 单写者多读者）]
# 断言: 100 个并发 query() 无 race condition
# Mock: 内存 ChromaDB

# [测试场景7: 新增 QdrantIndexAdapter 不影响调用方（OCP 验证）]
# 断言: QdrantIndexAdapter 继承 IndexAdapter 后被 engine.py 接受
# Mock: MockQdrantIndexAdapter
