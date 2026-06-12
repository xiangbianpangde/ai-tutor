"""study_pack generator 契约测试（#2：告别一次读 5 万行）。

输入: kg_id（manifest.source 指向语料 markdown）+ 输出目录
输出: 00_索引.md + NN_<标题>.md 分片，每份控制在 ~25 分钟阅读量内。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.errors import TutorError
from shared.storage import RelationalStore


@pytest.fixture
def kg_from_corpus(tmp_db: RelationalStore, tmp_path: Path):
    """直接用 toc builder 建 KG（无 LLM），manifest.source 指向语料文件。"""
    from servers.knowledge_mcp.kg_enrich_adapter import build_kg_toc

    big_section = "\n".join(
        "这是用于撑大章节体积的正文内容，模拟真实采集语料的篇幅密度与段落形态。" * 8
        for _ in range(20)
    )
    md = tmp_path / "corpus.md"
    md.write_text(
        "# 第一章 概念基础\n\n"
        + "\n".join(f"## 小节 {j}\n\n{big_section}\n" for j in range(4))
        + "\n# 第二章 小章\n\n短内容，一份之内读完。\n",
        encoding="utf-8",
    )
    kg_id, *_ = build_kg_toc(
        corpus_id="c1", subject_slug="t", markdown_path=md, db=tmp_db
    )
    return tmp_db, kg_id


def test_study_pack_splits_and_indexes(kg_from_corpus, tmp_path: Path) -> None:
    from servers.digest_mcp.study_pack import (
        CHARS_PER_MIN,
        MAX_MIN_PER_PART,
        generate_study_pack,
    )

    db, kg_id = kg_from_corpus
    arts = generate_study_pack(db=db, kg_id=kg_id, out_dir=tmp_path / "out")

    pack_dir = tmp_path / "out" / f"study_pack-{kg_id}"
    index = pack_dir / "00_索引.md"
    assert index.exists()

    parts = sorted(p for p in pack_dir.glob("*.md") if p.name != "00_索引.md")
    assert len(parts) >= 3  # 第一章超长被拆 + 第二章独立一份

    max_chars = MAX_MIN_PER_PART * CHARS_PER_MIN
    for p in parts:
        assert len(p.read_text(encoding="utf-8")) <= max_chars * 1.5

    text = index.read_text(encoding="utf-8")
    assert "预计" in text and "第二章 小章" in text
    assert len(arts) == len(parts) + 1  # 索引 + 各分片


def test_study_pack_missing_source_raises(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from shared.models import KnowledgeGraphRow

    from servers.digest_mcp.study_pack import generate_study_pack

    with tmp_db.session() as s:
        s.add(
            KnowledgeGraphRow(
                kg_id="kg-no-source", subject_id="s", corpus_id="c", version="v1",
                node_count=0, edge_count=0, quality_json={}, manifest_json={},
            )
        )
        s.commit()

    with pytest.raises(TutorError) as exc:
        generate_study_pack(db=tmp_db, kg_id="kg-no-source", out_dir=tmp_path)
    assert exc.value.code == "CORPUS_NOT_FOUND"


def test_study_pack_via_orchestrator(kg_from_corpus, tmp_path: Path) -> None:
    from servers.digest_mcp.orchestrator import digest

    db, kg_id = kg_from_corpus
    run = digest(db=db, kg_id=kg_id, out_dir=tmp_path / "o2", formats=["study_pack"])

    assert not run.warnings
    assert len(run.artifacts) >= 4
    assert any("00_" in a.uri for a in run.artifacts)
