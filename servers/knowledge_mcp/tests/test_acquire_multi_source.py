"""acquire 多源签名契约测试。

新签名:
  acquire(*, subject, version, sources: list[AcquireSource], ...)

AcquireSource = {type: "file"|"web"|"video", uri: str}

  - 单源 file: 继续工作（兼容 spine v1）
  - 多源 file: 全部合并到一个 CorpusManifest
  - web/video: stub raise DEPENDENCY_MISSING + hint 指向后续切片
"""
from __future__ import annotations

from pathlib import Path

import pytest

from servers.knowledge_mcp.acquisition_adapter import (
    AcquireSource,
    acquire,
)
from shared.errors import TutorError
from shared.models import User
from shared.storage import FileStore, RelationalStore


FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


@pytest.fixture
def db(tmp_db: RelationalStore) -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    return tmp_db


def test_acquire_single_file_source(db: RelationalStore, tmp_filestore: FileStore) -> None:
    manifest, corpus_id = acquire(
        subject="高数",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=db,
    )
    assert manifest.total_chapters == 2
    assert len(manifest.sources) == 1
    assert manifest.sources[0].format == "md"


def test_acquire_multiple_file_sources_merges(
    db: RelationalStore, tmp_filestore: FileStore, tmp_path: Path
) -> None:
    """两个本地 md：每个产生一个 CorpusSource，合并到同一 manifest。"""
    second = tmp_path / "second.md"
    second.write_text("# 章节 A\n## 节 A.1\n", encoding="utf-8")

    manifest, corpus_id = acquire(
        subject="高数",
        version="v1",
        sources=[
            AcquireSource(type="file", uri=str(FIXTURE)),
            AcquireSource(type="file", uri=str(second)),
        ],
        user_id="yhn",
        file_store=tmp_filestore,
        db=db,
    )
    assert len(manifest.sources) == 2
    # 章节数 = 两个 md 的 # 总和 = 2 + 1
    assert manifest.total_chapters == 3


def test_acquire_web_source_stub(db: RelationalStore, tmp_filestore: FileStore) -> None:
    with pytest.raises(TutorError) as exc:
        acquire(
            subject="x",
            version=None,
            sources=[AcquireSource(type="web", uri="https://example.com")],
            user_id="yhn",
            file_store=tmp_filestore,
            db=db,
        )
    assert exc.value.code == "DEPENDENCY_MISSING"
    assert "research_tool" in (exc.value.hint or "") or "web" in (exc.value.hint or "")


def test_acquire_video_source_stub(db: RelationalStore, tmp_filestore: FileStore) -> None:
    with pytest.raises(TutorError) as exc:
        acquire(
            subject="x",
            version=None,
            sources=[AcquireSource(type="video", uri="https://www.bilibili.com/video/BV1xx")],
            user_id="yhn",
            file_store=tmp_filestore,
            db=db,
        )
    assert exc.value.code == "DEPENDENCY_MISSING"


def test_acquire_empty_sources_raises(db: RelationalStore, tmp_filestore: FileStore) -> None:
    with pytest.raises(TutorError) as exc:
        acquire(
            subject="x",
            version=None,
            sources=[],
            user_id="yhn",
            file_store=tmp_filestore,
            db=db,
        )
    assert exc.value.code in ("DEPENDENCY_MISSING", "CORPUS_NOT_FOUND")
