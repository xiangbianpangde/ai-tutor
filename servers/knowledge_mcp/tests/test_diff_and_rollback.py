"""diff_kg + rollback_kg 契约测试。

diff_kg(kg_a, kg_b) → DiffResult:
- added:        b 有 a 没有的 concept（按 base_id 对齐）
- removed:      a 有 b 没有
- definition_changed: 同 base_id 但 definition 不同
- confidence_changed: 同 base_id 但 confidence 差 > 0.1
- edges_added/edges_removed

rollback_kg(subject_id, target_kg_id):
- 把 subject.kg_id 改回 target_kg_id（必须是当前 kg 的祖先）
- 不删除 child KG（审计保留）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.errors import TutorError
from shared.llm_client import MockLLMProvider
from shared.models import (
    ConceptRow,
    KnowledgeGraphRow,
    Subject,
    User,
)
from shared.schemas import KgEditAction
from shared.storage import RelationalStore


FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enrich() -> str:
    return json.dumps({"definition": "x", "confidence": 0.85}, ensure_ascii=False)


@pytest.fixture
def parent_and_child_kg(tmp_db: RelationalStore, tmp_filestore):
    """跑一个 KG → versioned update 出子 KG。"""
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_update import update_kg

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ml", user_id="yhn", display_name="ML"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ml", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    llm = MockLLMProvider(canned_responses=[_enrich() for _ in range(50)])
    r = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="ml",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    parent_kg = r.kg_id

    # 关联到 subject
    with tmp_db.session() as s:
        s.get(Subject, "ml").kg_id = parent_kg
        # 取第一个 concept 做修改 / 删除
        first = (
            s.query(ConceptRow).filter_by(kg_id=parent_kg).order_by(ConceptRow.id).first()
        )
        first_id = first.id
        s.commit()

    # 创建子 KG（编辑一个 + 删除一个）
    with tmp_db.session() as s:
        second = (
            s.query(ConceptRow)
            .filter_by(kg_id=parent_kg)
            .order_by(ConceptRow.id)
            .offset(1)
            .first()
        )
        second_id = second.id

    upd = update_kg(
        db=tmp_db, kg_id=parent_kg,
        actions=[
            KgEditAction(op="edit_definition", concept_id=first_id, new_definition="K3 改的定义"),
            KgEditAction(op="delete_concept", concept_id=second_id),
        ],
        mode="versioned",
    )
    child_kg = upd.kg_id
    return tmp_db, parent_kg, child_kg, first_id, second_id


def test_diff_detects_definition_changed(parent_and_child_kg) -> None:
    from servers.knowledge_mcp.kg_diff import diff_kg

    db, parent, child, first_id, _ = parent_and_child_kg
    d = diff_kg(db=db, kg_id_a=parent, kg_id_b=child)
    changed_base_ids = {c["base_id"] for c in d.definition_changed}
    assert first_id in changed_base_ids


def test_diff_detects_removed_concept(parent_and_child_kg) -> None:
    from servers.knowledge_mcp.kg_diff import diff_kg

    db, parent, child, _, second_id = parent_and_child_kg
    d = diff_kg(db=db, kg_id_a=parent, kg_id_b=child)
    removed_base_ids = {c["base_id"] for c in d.removed}
    assert second_id in removed_base_ids


def test_diff_added_when_b_has_extra(parent_and_child_kg) -> None:
    """在 child 加一个新 concept（通过 versioned update 加边方式 — 简化版直接 SQL 加）。"""
    from servers.knowledge_mcp.kg_diff import diff_kg

    db, parent, child, _, _ = parent_and_child_kg
    # 手动在 child 加一个新 concept
    with db.session() as s:
        s.add(ConceptRow(
            id=f"ml:99:new_concept@{child.split('-')[-1]}",
            kg_id=child,
            base_id="ml:99:new_concept",
            name_primary="新概念",
            names_json=["新概念"],
            category="definition",
            definition="新加的",
            informal_description="",
            abstract_level=0.5, bloom_level="understand", domain="ml",
            cognitive_load_estimate=0.3, typical_learning_time_min=10,
            prereq_count=0, prereq_max_depth=0, formula_density=0,
            coupling=0, confidence=0.9, full_json={},
        ))
        s.commit()

    d = diff_kg(db=db, kg_id_a=parent, kg_id_b=child)
    added_base_ids = {c["base_id"] for c in d.added}
    assert "ml:99:new_concept" in added_base_ids


def test_diff_unknown_kg_raises(tmp_db: RelationalStore) -> None:
    from servers.knowledge_mcp.kg_diff import diff_kg

    with pytest.raises(TutorError) as exc:
        diff_kg(db=tmp_db, kg_id_a="no-such-a", kg_id_b="no-such-b")
    assert exc.value.code == "KG_NOT_FOUND"


def test_diff_includes_summary_counts(parent_and_child_kg) -> None:
    from servers.knowledge_mcp.kg_diff import diff_kg

    db, parent, child, _, _ = parent_and_child_kg
    d = diff_kg(db=db, kg_id_a=parent, kg_id_b=child)
    # summary 应反映 1 removed + 1 def-changed
    assert d.summary["definition_changed_count"] >= 1
    assert d.summary["removed_count"] >= 1


# --------------------------------------------------------------------------- #
# rollback_kg
# --------------------------------------------------------------------------- #


def test_rollback_changes_subject_kg_id(parent_and_child_kg) -> None:
    """rollback subject 当前 kg_id 从 child 改回 parent。"""
    from servers.knowledge_mcp.kg_rollback import rollback_kg

    db, parent, child, _, _ = parent_and_child_kg
    # 先把 subject.kg_id 指向 child
    with db.session() as s:
        s.get(Subject, "ml").kg_id = child
        s.commit()

    rollback_kg(db=db, subject_id="ml", target_kg_id=parent)

    with db.session() as s:
        assert s.get(Subject, "ml").kg_id == parent


def test_rollback_does_not_delete_child(parent_and_child_kg) -> None:
    """child KG 应保留（审计），仅 subject.kg_id 改变。"""
    from servers.knowledge_mcp.kg_rollback import rollback_kg

    db, parent, child, _, _ = parent_and_child_kg
    rollback_kg(db=db, subject_id="ml", target_kg_id=parent)
    with db.session() as s:
        assert s.get(KnowledgeGraphRow, child) is not None


def test_rollback_requires_ancestor(parent_and_child_kg) -> None:
    """target_kg_id 必须是当前 subject.kg_id 的祖先；否则抛错。"""
    from servers.knowledge_mcp.kg_rollback import rollback_kg

    db, parent, child, _, _ = parent_and_child_kg
    # 当前 subject.kg_id 是 parent；试图 rollback 到 child（非祖先）
    with db.session() as s:
        assert s.get(Subject, "ml").kg_id == parent
    with pytest.raises(TutorError) as exc:
        rollback_kg(db=db, subject_id="ml", target_kg_id=child)
    assert exc.value.code in ("INVALID_KG_EDIT_ACTION", "KG_NOT_FOUND")


def test_rollback_unknown_subject(tmp_db: RelationalStore) -> None:
    from servers.knowledge_mcp.kg_rollback import rollback_kg

    with pytest.raises(TutorError) as exc:
        rollback_kg(db=tmp_db, subject_id="no-such", target_kg_id="kg-x")
    assert exc.value.code == "SUBJECT_NOT_FOUND"


def test_rollback_unknown_target(parent_and_child_kg) -> None:
    from servers.knowledge_mcp.kg_rollback import rollback_kg

    db, _, _, _, _ = parent_and_child_kg
    with pytest.raises(TutorError) as exc:
        rollback_kg(db=db, subject_id="ml", target_kg_id="no-such-kg")
    assert exc.value.code == "KG_NOT_FOUND"
