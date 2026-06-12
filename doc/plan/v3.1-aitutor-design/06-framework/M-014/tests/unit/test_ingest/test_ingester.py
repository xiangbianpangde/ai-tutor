"""test_ingester - M-014 Ingester 单元测试

> 对应模块: M-014
> 来源标注: [DD-001:MD-M014 sm014-ingest] + [DD-M推断:依据=UnitOfWork 模式]

[文件职责] Ingester.ingest() 单元测试
[所属模块] M-014
[测试策略] 单元测试 + 集成测试
[用例规划] 4 用例
[来源标注] [DD-001:MD-M014]
"""

# from aitutor.ingest.ingester import Ingester


def test_ingest_writes_to_chroma_and_sqlite_atomically() -> None:
    """场景 1: 原子写入 ChromaDB + SQLite

    断言: ChromaDB 和 SQLite 数据一致 / 任一失败则回滚
    """
    ...


def test_ingest_chroma_failure_rolls_back_sqlite() -> None:
    """场景 2: ChromaDB 失败时 SQLite 回滚

    Mock: _write_chroma 抛异常
    断言: _write_sqlite 写过的数据被回滚
    """
    ...


def test_ingest_batch_size_default_32() -> None:
    """场景 3: 默认 batch_size=32

    断言: 100 chunks 分 4 批写入
    """
    ...


def test_ingest_empty_chunks_returns_zero() -> None:
    """场景 4: 空 chunks 列表

    输入: chunks=[]
    断言: 返回 0
    """
    ...
