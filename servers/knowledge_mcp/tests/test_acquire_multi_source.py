"""acquire 多源签名契约测试。

新签名:
  acquire(*, subject, version, sources: list[AcquireSource], ...)

AcquireSource = {type: "file"|"web"|"video", uri: str}

  - 单源 file: 继续工作（兼容 spine v1）
  - 多源 file: 全部合并到一个 CorpusManifest
  - web: 接 research-tool（采集被 mock，不触网）
  - video: 仍为 stub，raise DEPENDENCY_MISSING
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


def test_acquire_web_source_via_research(
    db: RelationalStore, tmp_filestore: FileStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """web 源现接 research-tool（mock 掉采集，不触网）：acquire 应产出一个 web CorpusSource。"""
    from servers.knowledge_mcp import research_adapter
    from shared.schemas import CorpusSource

    def _fake(src, corpus_dir):  # noqa: ANN001
        md = corpus_dir / "web.md"
        md.write_text("# 主题\n## 片段\n正文内容\n", encoding="utf-8")
        return (
            CorpusSource(type="web", format="md", original_file=src.uri,
                         converted_file=str(md), language="zh", parser="research-tool"),
            md,
        )

    monkeypatch.setattr(research_adapter, "acquire_web", _fake)
    manifest, _corpus_id = acquire(
        subject="x", version=None,
        sources=[AcquireSource(type="web", uri="向量空间")],
        user_id="yhn", file_store=tmp_filestore, db=db,
    )
    assert len(manifest.sources) == 1
    assert manifest.sources[0].type == "web"
    assert manifest.sources[0].parser == "research-tool"


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


def test_acquire_pdf_translate_flag_threads_to_parse_pdf(
    db: RelationalStore, tmp_filestore: FileStore, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AcquireSource.translate=True 应一路串到 pdf_parser.parse_pdf（mock，不调 mineru）。"""
    from servers.knowledge_mcp import pdf_parser

    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    captured: dict = {}

    def _fake_parse(p, out_dir, *, translate=False, **kw):  # noqa: ANN001
        captured["translate"] = translate
        md = out_dir / "paper.md"
        md.write_text("# 标题\n## 节\n正文", encoding="utf-8")
        return md

    monkeypatch.setattr(pdf_parser, "parse_pdf", _fake_parse)

    manifest, _cid = acquire(
        subject="外文教材", version=None,
        sources=[AcquireSource(type="file", uri=str(pdf), translate=True)],
        user_id="yhn", file_store=tmp_filestore, db=db,
    )
    assert captured["translate"] is True
    assert manifest.sources[0].type == "textbook"


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
