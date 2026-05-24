"""存储抽象（L1）。

Spine 切片只实现两类：
- FileStore: 本地文件系统读写（artifacts、corpora/、knowledge_graphs/）
- RelationalStore: SQLAlchemy session 工厂 + create_all

Redis / VectorStore 后续切片补。
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base


# --------------------------------------------------------------------------- #
# FileStore
# --------------------------------------------------------------------------- #


class FileStore:
    """本地文件系统抽象，root 下分目录组织：
        corpora/<corpus_id>/...
        knowledge_graphs/<kg_id>/...
        output/<session_id>/...
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        p = self.root.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def write_text(self, *parts: str, content: str, encoding: str = "utf-8") -> Path:
        p = self.path(*parts)
        p.write_text(content, encoding=encoding)
        return p

    def read_text(self, *parts: str, encoding: str = "utf-8") -> str:
        return self.path(*parts).read_text(encoding=encoding)

    def exists(self, *parts: str) -> bool:
        return self.root.joinpath(*parts).exists()


# --------------------------------------------------------------------------- #
# RelationalStore
# --------------------------------------------------------------------------- #


class RelationalStore:
    """SQLAlchemy session 工厂。

    用法:
        store = RelationalStore.from_env()
        store.init_schema()   # 仅开发期；生产用 alembic
        with store.session() as s:
            s.add(User(id="yhn"))
            s.commit()
    """

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.url = url
        # SQLite 多线程开发场景需 check_same_thread=False
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(url, echo=echo, future=True, connect_args=connect_args)
        self._session_maker = sessionmaker(self.engine, expire_on_commit=False)

    @classmethod
    def from_env(cls, *, default: str = "sqlite:///data/tutor.db") -> "RelationalStore":
        url = os.environ.get("DATABASE_URL", default)
        return cls(url)

    def init_schema(self) -> None:
        """开发期一键建表；生产请走 alembic upgrade head。"""
        # 确保 SQLite 文件目录存在
        if self.url.startswith("sqlite:///"):
            db_path = Path(self.url.removeprefix("sqlite:///"))
            db_path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._session_maker()
        try:
            yield s
        finally:
            s.close()
