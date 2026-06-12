"""knowledge-mcp 端到端：acquire + build_kg(depth=toc) 在 fixture markdown 上跑通。"""
from __future__ import annotations

from pathlib import Path

import pytest

from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
from servers.knowledge_mcp.kg_enrich_adapter import build_kg_toc
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow, User
from shared.storage import FileStore, RelationalStore


FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


@pytest.fixture
def setup_user(tmp_db: RelationalStore) -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="yhn", display_name="Test"))
        s.commit()
    return tmp_db


def test_acquire_md_file(setup_user: RelationalStore, tmp_filestore: FileStore) -> None:
    assert FIXTURE.exists(), f"fixture missing: {FIXTURE}"
    manifest, corpus_id = acquire(
        subject="高等数学测试",
        version="v8",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=setup_user,
    )
    # corpus_id 由 subject 转拼音 + sha1 前 10 位组成
    assert manifest.total_chapters == 2  # "# 极限与连续" / "# 导数与微分"
    assert manifest.total_sections == 5  # 5 个 "## "


def test_build_kg_toc_full_flow(setup_user: RelationalStore, tmp_filestore: FileStore) -> None:
    manifest, corpus_id = acquire(
        subject="高等数学测试",
        version="v8",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=setup_user,
    )

    md_path = Path(manifest.file_paths["markdown"])
    kg_id, concepts, edges, quality, mermaid = build_kg_toc(
        corpus_id=corpus_id,
        subject_slug="gaoshu-test",
        markdown_path=md_path,
        db=setup_user,
    )

    # 节点数 = 2 章 + 5 节 + 10 小节 = 17
    assert len(concepts) == 17
    # 父子边 part_of: 17 - 2 个顶层 = 15
    part_of = [e for e in edges if e.type == "part_of"]
    assert len(part_of) == 15
    # 兄弟边 prerequisite_strong: 同级中除每组第一个之外都有；具体数与结构相关，>0 即可
    prereq = [e for e in edges if e.type == "prerequisite_strong"]
    assert len(prereq) > 0

    assert quality.overall in ("pass", "pass_with_warnings")
    assert "graph TD" in mermaid

    # 持久化校验
    with setup_user.session() as s:
        row = s.get(KnowledgeGraphRow, kg_id)
        assert row is not None
        assert row.node_count == len(concepts)
        assert row.edge_count == len(edges)

        concept_count = s.query(ConceptRow).filter_by(kg_id=kg_id).count()
        assert concept_count == len(concepts)

        relation_count = s.query(RelationRow).filter_by(kg_id=kg_id).count()
        assert relation_count == len(edges)


def test_kg_concept_ids_match_regex(setup_user: RelationalStore, tmp_filestore: FileStore) -> None:
    """生成的所有 Concept.id 必须符合 spec 的 regex。"""
    from shared.schemas import CONCEPT_ID_PATTERN
    import re

    manifest, corpus_id = acquire(
        subject="高数",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=setup_user,
    )
    md_path = Path(manifest.file_paths["markdown"])
    _, concepts, _, _, _ = build_kg_toc(
        corpus_id=corpus_id,
        subject_slug="gaoshu",
        markdown_path=md_path,
        db=setup_user,
    )
    pattern = re.compile(CONCEPT_ID_PATTERN)
    bad = [c.id for c in concepts if not pattern.match(c.id)]
    assert not bad, f"non-conformant ids: {bad}"


# ----------------------------- FIX-A：标题治理（#22 回归） ----------------------------- #


def test_build_toc_skips_code_fences_and_noise_titles(tmp_path: Path) -> None:
    """代码块注释 / 来源文件名 / 分隔线 / URL / 整句 不再成为概念；问句式标题保留。"""
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc

    md = tmp_path / "noisy.md"
    md.write_text(
        "# 真实章节\n"
        "## 真实小节\n"
        "```python\n"
        "# ============================================================\n"
        "# 代码注释不是标题\n"
        "print('x')\n"
        "```\n"
        "## 01-edu.aliyun.com-087e03\n"
        "## ============\n"
        "## https://example.com/page\n"
        "## 新加坡和北京地域的API Key不同，要分开获取再分别配置环境变量；\n"
        "## 什么是大模型？\n"
        "## 另一个真实小节\n",
        encoding="utf-8",
    )
    concepts, _edges = _build_toc(subject_slug="t", markdown_path=md)
    names = [c.names[0] for c in concepts]
    assert names == ["真实章节", "真实小节", "什么是大模型？", "另一个真实小节"]


def test_quality_warns_on_duplicate_names(tmp_path: Path) -> None:
    """重复概念名只告警不静默去重（跨章同名小节合法，归并交给 merge_concepts）。"""
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc, _compute_quality

    md = tmp_path / "dup.md"
    md.write_text(
        "# 第一章\n## QwenTTS 服务配置\n# 第二章\n## QwenTTS 服务配置\n",
        encoding="utf-8",
    )
    concepts, edges = _build_toc(subject_slug="t", markdown_path=md)
    assert len(concepts) == 4  # 不去重
    q = _compute_quality(concepts, edges)
    assert any("重复概念名" in w for w in q.warnings)


def test_demote_headings_fence_aware() -> None:
    from servers.knowledge_mcp.kg_enrich_adapter import demote_headings

    text = "# 标题\n```\n# 代码注释\n```\n## 子标题"
    out = demote_headings(text, min_level=2)
    lines = out.splitlines()
    assert lines[0] == "## 标题"
    assert lines[2] == "# 代码注释"  # 代码块内不动
    assert lines[4] == "### 子标题"
