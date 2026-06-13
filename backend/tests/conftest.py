"""backend 测试夹具：隔离临时库 + TestClient（进入即触发 lifespan 建库）。"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    # 每个测试独立临时库；_env_file=None 隔离仓库 .env，保证默认值可预期
    return AppConfig(_env_file=None, db_path=tmp_path / "tutor.db")


@pytest.fixture
def client(config: AppConfig) -> Iterator[TestClient]:
    app = create_app(config)
    with TestClient(app) as c:  # __enter__ 触发 lifespan → 建 14 表
        yield c
