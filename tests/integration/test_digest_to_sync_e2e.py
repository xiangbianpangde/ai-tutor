"""digest → sync 端到端：generator 产物的 ArtifactURI 必须能被 sync 直接消费。

回归测试 — 2026-05-22 真实 demo 中发现 generator 用相对 out_dir 时
生成的 file:// URI 无法被 sync-mcp 解析（前导 / + Windows 相对路径）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import User


@pytest.fixture
def kg_id_and_db(tmp_db, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "mini_subject.md"
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="e2e", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    llm = MockLLMProvider(canned_responses=[
        json.dumps({"definition": "x", "confidence": 0.8}, ensure_ascii=False)
        for _ in range(50)
    ])
    r = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="e2e",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    return tmp_db, r.kg_id


def test_digest_artifacts_uri_is_absolute(kg_id_and_db, tmp_path: Path) -> None:
    """所有 generator 必须产出绝对路径 URI（防 sync 解析失败的回归）。"""
    from servers.digest_mcp.orchestrator import digest

    db, kg_id = kg_id_and_db
    # 故意传相对路径
    run = digest(
        db=db, kg_id=kg_id,
        out_dir=Path("data/output/digest") / kg_id,  # 相对
        formats=["mindmap", "notes", "quiz"],
    )
    for art in run.artifacts:
        # file:///C:/... 或 file:///abs/path/...
        # 关键：剥 file:/// 后是绝对路径，不是 "data/..."
        path_str = art.uri.replace("file:///", "")
        p = Path(path_str)
        assert p.is_absolute() or path_str.startswith(("C:", "D:", "/", "c:", "d:")), \
            f"URI 应是绝对路径，得到 {art.uri!r}"


def test_digest_to_sync_round_trip(kg_id_and_db, tmp_path: Path) -> None:
    """digest 产物列表直接喂给 sync.push_to_obsidian 应该 100% 成功。"""
    from servers.digest_mcp.orchestrator import digest
    from servers.sync_mcp.obsidian import push_to_obsidian

    db, kg_id = kg_id_and_db
    out_dir = tmp_path / "out"
    run = digest(db=db, kg_id=kg_id, out_dir=out_dir, formats=["mindmap", "notes", "quiz"])
    assert len(run.artifacts) >= 3

    vault = tmp_path / "vault"
    vault.mkdir()
    push = push_to_obsidian(
        vault_path=vault, subject_id="e2e", artifacts=run.artifacts,
    )
    assert push.failed == [], f"push 出现失败: {push.failed}"
    assert push.pushed_count == len(run.artifacts)
