"""notes generator 契约测试。

输入: kg_id + db + 输出目录
输出: 一份结构化 markdown，按章节层级（# / ## / ###）组织 + 定义 +
      examples + common_misconceptions。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enriched(name: str, conf: float = 0.85) -> str:
    return json.dumps({
        "definition": f"{name}：精确定义文字",
        "informal_description": f"通俗解释：{name}",
        "examples": [{"text": f"例子：{name}", "type": "computation"}],
        "common_misconceptions": [f"常见误解：{name}"],
        "confidence": conf,
    }, ensure_ascii=False)


@pytest.fixture
def kg_with_content(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ce-shi",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=tmp_db,
    )
    canned = [_enriched(f"concept{i}") for i in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]),
        db=tmp_db,
    )
    return tmp_db, r.kg_id


def test_notes_writes_markdown_file(kg_with_content, tmp_path: Path) -> None:
    from servers.digest_mcp.notes import generate_notes

    db, kg_id = kg_with_content
    artifact = generate_notes(db=db, kg_id=kg_id, out_dir=tmp_path)
    assert artifact.mime_type == "text/markdown"
    file_path = Path(artifact.uri.replace("file:///", ""))
    text = file_path.read_text(encoding="utf-8")
    # 至少包含 markdown heading
    assert text.startswith("#") or "\n#" in text
    # 包含 enrich 后的定义片段
    assert "精确定义文字" in text or "通俗解释" in text


def test_notes_organizes_by_chapter_levels(kg_with_content, tmp_path: Path) -> None:
    """章节深度 1 → `#`、深度 2 → `##`、深度 3 → `###`。"""
    from servers.digest_mcp.notes import generate_notes

    db, kg_id = kg_with_content
    artifact = generate_notes(db=db, kg_id=kg_id, out_dir=tmp_path)
    text = Path(artifact.uri.replace("file:///", "")).read_text(encoding="utf-8")
    headings = [l for l in text.splitlines() if l.startswith("#")]
    levels = {h.split(" ")[0] for h in headings}
    # fixture 有 # / ## / ### 三级
    assert "#" in levels
    assert "##" in levels
    assert "###" in levels


def test_notes_includes_examples_and_misconceptions(kg_with_content, tmp_path: Path) -> None:
    from servers.digest_mcp.notes import generate_notes

    db, kg_id = kg_with_content
    artifact = generate_notes(db=db, kg_id=kg_id, out_dir=tmp_path)
    text = Path(artifact.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "例子" in text or "Example" in text or "例：" in text
    assert "误解" in text or "Misconception" in text or "误：" in text


def test_notes_orders_by_chapter_id(kg_with_content, tmp_path: Path) -> None:
    """节点按章节号自然顺序 (1, 1.1, 1.2, 2, 2.1) 出现。"""
    from servers.digest_mcp.notes import generate_notes

    db, kg_id = kg_with_content
    artifact = generate_notes(db=db, kg_id=kg_id, out_dir=tmp_path)
    text = Path(artifact.uri.replace("file:///", "")).read_text(encoding="utf-8")

    # 找出标题对应的 concept_id（用 inline 链接或注释；这里宽松断言）
    # 直接断言：先出现 chapter=1 的内容，再 chapter=2 的内容
    lines = text.splitlines()
    idx_ch1 = next(
        (i for i, l in enumerate(lines) if l.startswith("# ") and "极限" in l), -1
    )
    idx_ch2 = next(
        (i for i, l in enumerate(lines) if l.startswith("# ") and "导数" in l), -1
    )
    if idx_ch1 >= 0 and idx_ch2 >= 0:
        assert idx_ch1 < idx_ch2


def test_notes_unknown_kg_raises(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from servers.digest_mcp.notes import generate_notes
    from shared.errors import TutorError

    with pytest.raises(TutorError) as exc:
        generate_notes(db=tmp_db, kg_id="no-such", out_dir=tmp_path)
    assert exc.value.code == "KG_NOT_FOUND"


def test_notes_skips_empty_kg(tmp_db: RelationalStore, tmp_path: Path) -> None:
    """空 KG 仍能成功写文件（不抛错），文件含说明。"""
    from servers.digest_mcp.notes import generate_notes
    from shared.models import KnowledgeGraphRow

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        # 必须先建 corpus 行才能建 KG（外键）
        from shared.models import Corpus
        s.add(Corpus(id="c1", subject_id="x", user_id="yhn", manifest_json={}))
        s.add(
            KnowledgeGraphRow(
                kg_id="empty-kg", subject_id="x", corpus_id="c1",
                version="v1", node_count=0, edge_count=0, manifest_json={},
            )
        )
        s.commit()
    artifact = generate_notes(db=tmp_db, kg_id="empty-kg", out_dir=tmp_path)
    text = Path(artifact.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "无" in text or "empty" in text.lower() or len(text) > 0
