"""mindmap generator 契约测试。

输入: kg_id + db + 输出目录
输出: 写一份 .mmd（Mermaid 文本）+ 返回 ArtifactURI

设计:
- 默认渲染 root + 二级节点（避免长尾节点炸图）
- max_depth 参数控制层级
- 支持 only_low_confidence 过滤（聚焦待复习概念）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import User
from shared.storage import RelationalStore


FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich(c: float) -> str:
    return json.dumps({"definition": "x", "confidence": c}, ensure_ascii=False)


@pytest.fixture
def kg_ready(tmp_db: RelationalStore, tmp_filestore):
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
    # 前 3 个低置信，其余高
    canned = [_enrich(0.3)] * 3 + [_enrich(0.85)] * 30
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]),
        db=tmp_db,
    )
    return tmp_db, r.kg_id


def test_mindmap_writes_mermaid_file(kg_ready, tmp_path: Path) -> None:
    from servers.digest_mcp.mindmap import generate_mindmap

    db, kg_id = kg_ready
    artifact = generate_mindmap(db=db, kg_id=kg_id, out_dir=tmp_path)

    assert artifact.mime_type == "text/vnd.mermaid"
    assert artifact.size_bytes > 0
    file_path = Path(artifact.uri.replace("file:///", ""))
    assert file_path.exists()
    text = file_path.read_text(encoding="utf-8")
    assert text.startswith("graph TD") or text.startswith("mindmap")


def test_mindmap_respects_max_depth(kg_ready, tmp_path: Path) -> None:
    """max_depth=1 时只包含一级标题（章节根节点）+ 子节，不到三级。"""
    from servers.digest_mcp.mindmap import generate_mindmap

    db, kg_id = kg_ready
    artifact = generate_mindmap(db=db, kg_id=kg_id, out_dir=tmp_path, max_depth=1)
    text = Path(artifact.uri.replace("file:///", "")).read_text(encoding="utf-8")

    # 三级（含三段冒号分隔的 chapter）的 concept 不应出现
    # mini_subject 里只有 2 章 + 5 节 + 10 小节，max_depth=1 应该只有 2 节点（章根）
    node_lines = [l for l in text.splitlines() if "[" in l and "]" in l]
    assert 1 <= len(node_lines) <= 3  # 顶层 2 章 + 容差


def test_mindmap_only_low_confidence(kg_ready, tmp_path: Path) -> None:
    """only_low_confidence=True → 只画 confidence<0.5 的节点。"""
    from servers.digest_mcp.mindmap import generate_mindmap

    db, kg_id = kg_ready
    artifact = generate_mindmap(
        db=db, kg_id=kg_id, out_dir=tmp_path,
        only_low_confidence=True, confidence_threshold=0.5,
    )
    text = Path(artifact.uri.replace("file:///", "")).read_text(encoding="utf-8")
    node_lines = [l for l in text.splitlines() if "[" in l and "]" in l]
    # 我们 fixture 中前 3 个 enrich 用了 0.3，所以应该 3 个低置信节点
    assert len(node_lines) <= 5


def test_mindmap_unknown_kg_raises(tmp_db, tmp_path: Path) -> None:
    from shared.errors import TutorError
    from servers.digest_mcp.mindmap import generate_mindmap

    with pytest.raises(TutorError) as exc:
        generate_mindmap(db=tmp_db, kg_id="no-such", out_dir=tmp_path)
    assert exc.value.code == "KG_NOT_FOUND"


def test_mindmap_filename_contains_kg_id(kg_ready, tmp_path: Path) -> None:
    from servers.digest_mcp.mindmap import generate_mindmap

    db, kg_id = kg_ready
    artifact = generate_mindmap(db=db, kg_id=kg_id, out_dir=tmp_path)
    assert kg_id in artifact.uri or kg_id.split("-")[0] in artifact.uri
