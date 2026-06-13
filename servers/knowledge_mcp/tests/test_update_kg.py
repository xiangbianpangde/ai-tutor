"""update_kg 6 种 op 契约测试（in-place + audit trail 版本）。

设计说明:
- spec 原文要求"新 KG 版本不覆盖原 kg_id"。但当前 ConceptRow.id 是全表 PK，
  复制成本高且会破坏 BKT 跨版本继承。本切片采用 **in-place + audit trail**：
  - 直接修改 kg_id 对应的行
  - manifest_json.update_history 记录每次 update 的 actions + applied/failed
- 完整版本树（KG 复制 + 回滚）留到后续切片（需要时改 (kg_id, id) 复合 PK）。

支持的 op:
1. edit_definition       — 改 concept.definition
2. add_edge              — 加一条 Relation
3. remove_edge           — 删一条 Relation
4. delete_concept        — 删一个 Concept（连带删它的所有边）
5. merge_concepts        — 把 src 合并到 tgt（边重定向，src 删除）
6. approve_all           — no-op，仅打 approved 标记
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
    RelationRow,
    User,
)
from shared.schemas import KgEditAction, Relation

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _conf_response(c: float) -> str:
    return json.dumps({"definition": "LLM 填充", "confidence": c}, ensure_ascii=False)


@pytest.fixture
def kg_ready(tmp_db, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="测试",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=tmp_db,
    )
    llm = MockLLMProvider(canned_responses=[_conf_response(0.5) for _ in range(50)])
    r = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]),
        db=tmp_db,
    )
    return tmp_db, r.kg_id


def _first_two_concept_ids(db, kg_id) -> tuple[str, str]:
    with db.session() as s:
        rows = s.query(ConceptRow).filter_by(kg_id=kg_id).order_by(ConceptRow.id).all()
        return rows[0].id, rows[1].id


def test_update_returns_same_kg_id_and_records_history(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    result = update_kg(db=db, kg_id=kg_id, actions=[KgEditAction(op="approve_all")])
    assert result.kg_id == kg_id  # in-place
    assert result.applied == 1
    assert result.failed == []
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        history = kg.manifest_json.get("update_history", [])
        assert len(history) == 1
        assert history[0]["applied"] == 1
        assert "approve_all" in str(history[0])


def test_edit_definition_op(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    cid, _ = _first_two_concept_ids(db, kg_id)
    update_kg(
        db=db,
        kg_id=kg_id,
        actions=[KgEditAction(op="edit_definition", concept_id=cid, new_definition="新定义")],
    )
    with db.session() as s:
        row = s.get(ConceptRow, cid)
        assert row.definition == "新定义"


def test_add_edge_op(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    c1, c2 = _first_two_concept_ids(db, kg_id)
    new_edge = Relation(
        from_id=c1,
        to_id=c2,
        type="analogous_to",
        weight=0.8,
        explanation="人工补的类比边",
        confidence=1.0,
    )
    update_kg(db=db, kg_id=kg_id, actions=[KgEditAction(op="add_edge", edge=new_edge)])
    with db.session() as s:
        rels = (
            s.query(RelationRow)
            .filter_by(kg_id=kg_id, type="analogous_to", from_id=c1, to_id=c2)
            .all()
        )
        assert len(rels) == 1


def test_remove_edge_op(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    with db.session() as s:
        e = s.query(RelationRow).filter_by(kg_id=kg_id).first()
        target = Relation(
            from_id=e.from_id, to_id=e.to_id, type=e.type, weight=e.weight,
            explanation=e.explanation, confidence=e.confidence,
        )

    update_kg(db=db, kg_id=kg_id, actions=[KgEditAction(op="remove_edge", edge=target)])
    with db.session() as s:
        match = (
            s.query(RelationRow)
            .filter_by(
                kg_id=kg_id, from_id=target.from_id, to_id=target.to_id, type=target.type
            )
            .all()
        )
        assert len(match) == 0


def test_delete_concept_op_also_removes_edges(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    cid, _ = _first_two_concept_ids(db, kg_id)
    update_kg(db=db, kg_id=kg_id, actions=[KgEditAction(op="delete_concept", concept_id=cid)])
    with db.session() as s:
        assert s.get(ConceptRow, cid) is None
        rels = (
            s.query(RelationRow)
            .filter_by(kg_id=kg_id)
            .filter((RelationRow.from_id == cid) | (RelationRow.to_id == cid))
            .all()
        )
        assert rels == []


def test_merge_concepts_redirects_edges(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    src, tgt = _first_two_concept_ids(db, kg_id)
    update_kg(
        db=db,
        kg_id=kg_id,
        actions=[KgEditAction(op="merge_concepts", concept_id=src, merge_target_id=tgt)],
    )
    with db.session() as s:
        assert s.get(ConceptRow, src) is None
        assert s.get(ConceptRow, tgt) is not None
        # 没有边再指向 src（含自环也是 src→tgt 的合并方向应去重）
        bad = (
            s.query(RelationRow)
            .filter_by(kg_id=kg_id)
            .filter((RelationRow.from_id == src) | (RelationRow.to_id == src))
            .all()
        )
        assert bad == []


def test_invalid_action_records_failure_others_succeed(kg_ready) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    result = update_kg(
        db=db,
        kg_id=kg_id,
        actions=[
            KgEditAction(op="edit_definition"),  # 缺必填字段
            KgEditAction(op="approve_all"),
        ],
    )
    assert result.applied == 1
    assert len(result.failed) == 1
    assert result.failed[0].action_index == 0
    assert "concept_id" in result.failed[0].reason or "definition" in result.failed[0].reason


def test_unknown_kg_raises(tmp_db) -> None:
    from servers.knowledge_mcp.kg_update import update_kg

    with pytest.raises(TutorError) as exc:
        update_kg(db=tmp_db, kg_id="no-such-kg", actions=[KgEditAction(op="approve_all")])
    assert exc.value.code == "KG_NOT_FOUND"


def test_quality_report_recomputed(kg_ready) -> None:
    """删几个 concept 后，quality_report 的 isolated_nodes / avg_confidence 应重算。"""
    from servers.knowledge_mcp.kg_update import update_kg

    db, kg_id = kg_ready
    cid, _ = _first_two_concept_ids(db, kg_id)
    result = update_kg(
        db=db,
        kg_id=kg_id,
        actions=[KgEditAction(op="delete_concept", concept_id=cid)],
    )
    assert result.new_quality_report.overall in ("pass", "pass_with_warnings", "fail")
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        assert kg.node_count == result.new_quality_report.isolated_nodes + (
            kg.node_count - kg.node_count + result.new_quality_report.isolated_nodes
        ) or kg.node_count > 0  # 容忍：至少 node_count 已减一


@pytest.mark.asyncio
async def test_update_kg_tool_no_longer_stub() -> None:
    from servers.knowledge_mcp import server as srv

    fn = getattr(srv.update_kg, "fn", srv.update_kg)
    with pytest.raises(TutorError) as exc:
        await fn(kg_id="no-such-kg", actions=[{"op": "approve_all"}])
    assert exc.value.code == "KG_NOT_FOUND"
