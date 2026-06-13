"""update_kg(mode="versioned") 契约测试。

K3 新行为：
- mode="versioned" → 复制 KG 到新 kg_id（带 parent_kg_id），应用 actions，原 KG 不变
- mode="in_place"  → 旧 K2 行为
- 默认 mode 留作 backward-compat："in_place"（避免破坏 K2 用户）

新 kg_id 规则：`{parent_kg_id}-v{n}` (n = 2, 3, ...)
concept.id 后缀：`{base_id}@{new_kg_id}` 避免 PK 冲突；base_id 保留
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.errors import TutorError
from shared.llm_client import MockLLMProvider
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow, User
from shared.schemas import KgEditAction
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich() -> str:
    return json.dumps({"definition": "x", "confidence": 0.85}, ensure_ascii=False)


@pytest.fixture
def kg_ready(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ce-shi", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    llm = MockLLMProvider(canned_responses=[_enrich() for _ in range(50)])
    r = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    return tmp_db, r.kg_id


def _first_concept_id(db, kg_id) -> str:
    with db.session() as s:
        return s.query(ConceptRow).filter_by(kg_id=kg_id).order_by(ConceptRow.id).first().id


def test_versioned_mode_creates_new_kg(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, parent_kg = kg_ready
    result = update_kg(
        db=db, kg_id=parent_kg,
        actions=[KgEditAction(op="approve_all")],
        mode="versioned",
    )
    assert result.kg_id != parent_kg  # 新 kg_id
    assert result.applied == 1
    with db.session() as s:
        # 父 KG 还在
        parent = s.get(KnowledgeGraphRow, parent_kg)
        assert parent is not None
        # 新 KG 创建了，且 parent_kg_id 指向父
        child = s.get(KnowledgeGraphRow, result.kg_id)
        assert child is not None
        assert child.parent_kg_id == parent_kg


def test_versioned_mode_copies_concepts(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, parent_kg = kg_ready
    with db.session() as s:
        original_count = s.query(ConceptRow).filter_by(kg_id=parent_kg).count()

    result = update_kg(
        db=db, kg_id=parent_kg,
        actions=[KgEditAction(op="approve_all")],
        mode="versioned",
    )
    with db.session() as s:
        new_count = s.query(ConceptRow).filter_by(kg_id=result.kg_id).count()
        assert new_count == original_count


def test_versioned_concept_ids_preserve_base_id(kg_ready) -> None:
    """新 KG 的 concept.id 加版本后缀；base_id 保留原 id。"""
    from servers.knowledge_mcp.kg_update import update_kg

    db, parent_kg = kg_ready
    cid = _first_concept_id(db, parent_kg)

    result = update_kg(
        db=db, kg_id=parent_kg,
        actions=[KgEditAction(op="approve_all")],
        mode="versioned",
    )
    with db.session() as s:
        new_rows = s.query(ConceptRow).filter_by(kg_id=result.kg_id).all()
        # 每个 new concept 的 base_id 应在 parent KG 中存在
        parent_base_ids = {
            r.id for r in s.query(ConceptRow).filter_by(kg_id=parent_kg).all()
        }
        for r in new_rows:
            assert r.base_id in parent_base_ids, f"{r.id} 的 base_id={r.base_id} 不在父集合"
            # id 应不同（带 @ 后缀）
            if r.id != r.base_id:
                assert "@" in r.id


def test_versioned_edit_definition_doesnt_change_parent(kg_ready) -> None:
    """在子版本 edit_definition → 父版本不变。"""
    from servers.knowledge_mcp.kg_update import update_kg

    db, parent_kg = kg_ready
    cid = _first_concept_id(db, parent_kg)
    with db.session() as s:
        original_def = s.get(ConceptRow, cid).definition

    update_kg(
        db=db, kg_id=parent_kg,
        actions=[
            KgEditAction(op="edit_definition", concept_id=cid, new_definition="新定义 K3"),
        ],
        mode="versioned",
    )
    with db.session() as s:
        # 父 KG 中 concept 不变
        parent_concept = s.get(ConceptRow, cid)
        assert parent_concept.definition == original_def


def test_versioned_in_place_mode_unchanged(kg_ready) -> None:
    """mode="in_place" 应保留 K2 行为：原 kg_id 不变 + audit trail。"""
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    result = update_kg(
        db=db, kg_id=kg_id,
        actions=[KgEditAction(op="approve_all")],
        mode="in_place",
    )
    assert result.kg_id == kg_id


def test_versioned_unknown_mode_raises(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    with pytest.raises(TutorError) as exc:
        update_kg(
            db=db, kg_id=kg_id, actions=[KgEditAction(op="approve_all")],
            mode="alien",  # type: ignore[arg-type]
        )
    assert exc.value.code == "DEPENDENCY_MISSING"


def test_versioned_delete_concept_only_in_child(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, parent_kg = kg_ready
    cid = _first_concept_id(db, parent_kg)

    result = update_kg(
        db=db, kg_id=parent_kg,
        actions=[KgEditAction(op="delete_concept", concept_id=cid)],
        mode="versioned",
    )
    with db.session() as s:
        # 父中还在
        assert s.get(ConceptRow, cid) is not None
        # 子中没有 base_id=cid 的
        survivors = s.query(ConceptRow).filter_by(kg_id=result.kg_id, base_id=cid).all()
        assert survivors == []


def test_versioned_edges_remapped_to_new_ids(kg_ready) -> None:
    """子版本中所有 edge 应指向 child 的 concept_id（带 @ 后缀的）。"""
    from servers.knowledge_mcp.kg_update import update_kg

    db, parent_kg = kg_ready
    result = update_kg(
        db=db, kg_id=parent_kg,
        actions=[KgEditAction(op="approve_all")],
        mode="versioned",
    )
    with db.session() as s:
        child_concept_ids = {
            r.id for r in s.query(ConceptRow).filter_by(kg_id=result.kg_id).all()
        }
        child_edges = s.query(RelationRow).filter_by(kg_id=result.kg_id).all()
        # 子 KG 的边端点应都在子 KG 内
        for e in child_edges:
            assert e.from_id in child_concept_ids, f"边 {e.from_id} 不在子 KG"
            assert e.to_id in child_concept_ids


def test_versioned_records_history(kg_ready) -> None:
    """子 KG 的 manifest_json 也应有 update_history 记录创建动作。"""
    from servers.knowledge_mcp.kg_update import update_kg

    db, parent_kg = kg_ready
    result = update_kg(
        db=db, kg_id=parent_kg,
        actions=[KgEditAction(op="approve_all")],
        mode="versioned",
    )
    with db.session() as s:
        child = s.get(KnowledgeGraphRow, result.kg_id)
        manifest = child.manifest_json or {}
        assert "update_history" in manifest
        assert manifest["update_history"]
        assert manifest.get("parent_kg_id") == parent_kg
