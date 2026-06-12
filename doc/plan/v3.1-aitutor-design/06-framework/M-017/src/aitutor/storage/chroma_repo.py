"""storage.chroma_repo - M-017 ChromaDB 向量库

> 对应模块: M-017 存储
> 关联接口: IC-003（RAG 检索）/ IC-004（数据入库）
> 关联选型: TS-004 ChromaDB
> 关联设计: MD-AITutor-V3.1#m-017 类设计 ChromaRepository
> 来源标注: [DD-001:MD-017] + [DD-M推断:依据=Adapter 模式]
"""

# [文件职责] ChromaDB 向量库仓储（query / add / delete）
# [所属模块] M-017
# [关联设计规范] MD-AITutor-V3.1#m-017 ChromaRepository
# [功能描述]
#   功能1: 向量相似度查询（cosine 距离）
#   功能2: 文档分块嵌入后入库
#   功能3: 文档 ID 删除（与 SQLite documents 表保持一致）
#   功能4: 损坏时自动重建 + 备份恢复（E01702）
# [输入输出]
#   输入: 嵌入向量 / 文档 ID / 文本块
#   输出: 检索结果列表（含 score/source）
# [依赖关系]
#   依赖文件: chromadb 第三方 / shared/exceptions.py
#   被依赖文件: rag/indexing/chroma.py（M-008）/ ingest/ingester.py（M-014）
# [注意事项]
#   注意1: ChromaDB 无传统事务，"事务一致性"由 UoW 显式补偿（delete 补偿）
#   注意2: collection 必须预创建；collection 名称遵循 ^[a-z0-9_]{1,63}$
#   注意3: 大批量 add 必须分批（每批 ≤500）防止 OOM
#   注意4: 嵌入模型由调用方提供 embedding_fn（不在此模块耦合）
# [代码风格] 遵循 CS-AITutor-V3.1
# [创建日期] 2026-06-02
# [作者] DD-M-017-20260602
# [来源标注] [DD-001:MD-017]

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, List, Optional

import chromadb
from chromadb.api.models.Collection import Collection

from aitutor.shared.exceptions import StorageError


# ============================================================
# 类：ChromaRepository
# ============================================================


class ChromaRepository:
    """ChromaDB 向量库仓储。

    [类名] ChromaRepository
    [职责] 封装 ChromaDB 客户端；提供 add/query/delete 高级 API
    [关联设计规范] MD-AITutor-V3.1#m-017 ChromaRepository
    [属性]
      属性1: client chromadb.PersistentClient 必填 ChromaDB 持久化客户端
      属性2: collection Collection 可选 当前活跃集合
      属性3: path Path 必填 持久化目录
      属性4: _collection_name str 内部 默认 "default"
      属性5: _batch_size int 内部 默认 500
      属性6: _lock asyncio.Lock 内部 串行化写入
    [方法列表]
      方法1: query - 相似度检索
      方法2: add - 批量入库
      方法3: delete - 按 ID 删除
      方法4: get_collection - 切换/创建集合
      方法5: rebuild - 损坏时重建 + 备份恢复
    [异常处理]
      异常1: StorageError - ChromaDB 损坏（E01702）
      异常2: StorageError - 磁盘满（E01701）
    [并发安全] 是（写入串行化，读取并行）
    [幂等性] add 非幂等（重复 add 触发去重警告，不影响结果）；delete 幂等
    [性能约束] 单查 ≤100ms（P95，10k 集合）
    [来源标注] [DD-001:MD-017]
    """

    def __init__(
        self,
        path: Path,
        collection_name: str = "default",
        batch_size: int = 500,
    ) -> None:
        """初始化 ChromaRepository。

        [函数名] __init__
        [职责] 创建 PersistentClient + 默认集合
        [参数说明]
          参数1: path Path 必填 ChromaDB 持久化目录
          参数2: collection_name str 可选 默认 "default" 集合名
          参数3: batch_size int 可选 默认 500 批量 add 上限
        [返回值]
          类型: None
        [错误码]
          错误码1: E01702 含义: ChromaDB 损坏 触发: 启动连接失败（已自动重建）
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def query(
        self,
        embedding: List[float],
        top_k: int = 5,
        where: Optional[dict[str, Any]] = None,
    ) -> List[dict[str, Any]]:
        """向量相似度检索。

        [函数名] query
        [职责] 用 embedding 检索 top_k 相似块
        [关联接口契约] IC-003（RAG 检索）
        [参数说明]
          参数1: embedding List[float] 必填 查询向量
          参数2: top_k int 可选 默认 5 规则 [1, 20]
          参数3: where Optional[dict] 可选 元数据过滤
        [返回值]
          类型: List[Dict]
          描述: 每项含 {id, score, text, metadata, source}
        [错误码]
          错误码1: E01702 含义: ChromaDB 损坏 触发: query 期间异常
        [并发安全] 是
        [幂等性] 是
        [性能约束] 单查 ≤100ms（P95）
        [来源标注] [DD-001:MD-017] + [IC-003]
        """
        ...

    async def add(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: Optional[List[dict[str, Any]]] = None,
    ) -> int:
        """批量入库。

        [函数名] add
        [职责] 批量插入（自动分批）
        [关联接口契约] IC-004（数据入库）
        [参数说明]
          参数1: ids List[str] 必填 文档 ID 列表（UUIDv4）
          参数2: embeddings List[List[float]] 必填 向量列表
          参数3: documents List[str] 必填 文本列表
          参数4: metadatas Optional[List[dict]] 可选 元数据列表
        [返回值]
          类型: int
          描述: 实际入库条数
        [错误码]
          错误码1: E01701 含义: 磁盘满 触发: 写入失败
          错误码2: E01702 含义: ChromaDB 损坏 触发: 写入异常
        [并发安全] 是（_lock 串行化）
        [幂等性] 否（重复 ID 会覆盖；上游负责去重）
        [性能约束] 1000 条/批 ≤2s（P95）
        [来源标注] [DD-001:MD-017] + [IC-004]
        """
        ...

    async def delete(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[dict[str, Any]] = None,
    ) -> int:
        """按 ID 或元数据删除。

        [函数名] delete
        [职责] 删除指定向量记录
        [参数说明]
          参数1: ids Optional[List[str]] 可选 要删除的 ID
          参数2: where Optional[dict] 可选 元数据过滤
        [返回值]
          类型: int
          描述: 实际删除条数
        [并发安全] 是
        [幂等性] 是
        [性能约束] ≤500ms（P95）
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def get_collection(self, name: str) -> Collection:
        """获取/创建指定集合。

        [函数名] get_collection
        [职责] 切换活跃集合；不存在则创建
        [参数说明]
          参数1: name str 必填 集合名（^[a-z0-9_]{1,63}$）
        [返回值]
          类型: Collection
        [错误码]
          错误码1: ValueError 含义: 集合名非法 触发: 命名空间规则违反
        [来源标注] [DD-001:MD-017]
        """
        ...

    async def rebuild(self, backup_path: Optional[Path] = None) -> None:
        """损坏时重建 + 备份恢复。

        [函数名] rebuild
        [职责] 删除损坏集合 → 从 backup_path 恢复（若有）
        [参数说明]
          参数1: backup_path Optional[Path] 可选 备份目录
        [返回值]
          类型: None
        [错误码]
          错误码1: E01702 含义: 重建失败 触发: 备份不存在或读取失败
        [注意事项] 注意1: 此方法会清空当前集合；调用方需先停止写入
        [来源标注] [DD-001:MD-017]
        """
        ...
