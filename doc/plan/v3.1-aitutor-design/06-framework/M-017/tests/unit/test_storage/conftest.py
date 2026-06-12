"""tests.unit.test_storage.conftest - M-017 存储模块测试 Fixture

> 对应模块: M-017 存储
> 创建日期: 2026-06-02
> 作者: DD-M-017-20260602
> 来源标注: [DD-M推断:依据=pytest conftest 标准]
"""

# [文件职责] 共享测试 Fixture：内存 SQLite / 临时 ChromaDB / 临时文件目录 / StorageConfig

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from aitutor.storage.unit_of_work import StorageConfig


@pytest_asyncio.fixture
async def temp_storage_dir(tmp_path: Path) -> Path:
    """临时存储根目录（每个测试隔离）。

    [Fixture] temp_storage_dir
    [职责] 提供 tmp_path 隔离的存储目录
    [来源标注] [DD-M推断:依据=pytest tmp_path 标准]
    """
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


@pytest_asyncio.fixture
async def storage_config(temp_storage_dir: Path) -> StorageConfig:
    """存储配置（默认参数）。

    [Fixture] storage_config
    [职责] 构造 StorageConfig 指向临时目录
    [来源标注] [DD-001:MD-017]
    """
    return StorageConfig(
        sqlite_path=temp_storage_dir / "test.db",
        chroma_path=temp_storage_dir / "chroma",
        file_base_path=temp_storage_dir / "files",
    )


@pytest_asyncio.fixture
async def async_session(temp_storage_dir: Path) -> AsyncIterator[AsyncSession]:
    """异步 SQLite Session（带 schema）。

    [Fixture] async_session
    [职责] 提供内存 SQLite session
    [来源标注] [DD-M推断:依据=SQLAlchemy 2.0 async 测试模式]
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        # 测试用最小 schema（实际表结构由 migrations/v1_initial 定义）
        from sqlalchemy import MetaData, Table, Column, Integer, String
        metadata = MetaData()
        Table(
            "test_items",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String(64)),
        )
        await conn.run_sync(metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()
