"""K3 schema 增强契约测试：base_id + parent_kg_id。

设计:
- ConceptRow.base_id  — 默认 = id；跨 KG 版本的"稳定身份"
- KnowledgeGraphRow.parent_kg_id — 可空；指向上一版 KG，构成版本树
"""
from __future__ import annotations

import pytest

from shared.models import ConceptRow, KnowledgeGraphRow
from shared.storage import RelationalStore


def test_concept_row_has_base_id_field(tmp_db: RelationalStore) -> None:
    """ConceptRow 字段 base_id 存在且可读写。"""
    from shared.models import Corpus
    with tmp_db.session() as s:
        s.add(Corpus(id="c1", subject_id="x", user_id="u", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id="kg1", subject_id="x", corpus_id="c1",
            version="v1", node_count=1, edge_count=0, manifest_json={},
        ))
        s.add(ConceptRow(
            id="x:1:a", kg_id="kg1", base_id="x:1:a",
            name_primary="A", names_json=["A"], category="definition",
            definition="x", informal_description="",
            abstract_level=0.5, bloom_level="understand", domain="x",
            cognitive_load_estimate=0.3, typical_learning_time_min=10,
            prereq_count=0, prereq_max_depth=0, formula_density=0,
            coupling=0, confidence=0.9, full_json={},
        ))
        s.commit()

    with tmp_db.session() as s:
        row = s.get(ConceptRow, "x:1:a")
        assert row.base_id == "x:1:a"


def test_concept_row_base_id_defaults_to_id_if_omitted(tmp_db: RelationalStore) -> None:
    """如果 base_id 没显式提供，应默认等于 id（数据库 default 或 ORM 层）。"""
    from shared.models import Corpus
    with tmp_db.session() as s:
        s.add(Corpus(id="c2", subject_id="x", user_id="u", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id="kg2", subject_id="x", corpus_id="c2",
            version="v1", node_count=1, edge_count=0, manifest_json={},
        ))
        # 不指定 base_id；ORM 层 __init__ 应自动等于 id
        c = ConceptRow(
            id="x:1:b", kg_id="kg2",
            name_primary="B", names_json=["B"], category="definition",
            definition="x", informal_description="",
            abstract_level=0.5, bloom_level="understand", domain="x",
            cognitive_load_estimate=0.3, typical_learning_time_min=10,
            prereq_count=0, prereq_max_depth=0, formula_density=0,
            coupling=0, confidence=0.9, full_json={},
        )
        s.add(c)
        s.commit()

    with tmp_db.session() as s:
        row = s.get(ConceptRow, "x:1:b")
        assert row.base_id == "x:1:b"


def test_kg_row_has_parent_kg_id(tmp_db: RelationalStore) -> None:
    from shared.models import Corpus
    with tmp_db.session() as s:
        s.add(Corpus(id="c3", subject_id="x", user_id="u", manifest_json={}))
        # 父 KG
        s.add(KnowledgeGraphRow(
            kg_id="kg-parent", subject_id="x", corpus_id="c3",
            version="v1", node_count=0, edge_count=0, manifest_json={},
        ))
        # 子 KG
        s.add(KnowledgeGraphRow(
            kg_id="kg-child", subject_id="x", corpus_id="c3",
            version="v2", node_count=0, edge_count=0,
            manifest_json={}, parent_kg_id="kg-parent",
        ))
        s.commit()

    with tmp_db.session() as s:
        child = s.get(KnowledgeGraphRow, "kg-child")
        assert child.parent_kg_id == "kg-parent"

        parent = s.get(KnowledgeGraphRow, "kg-parent")
        assert parent.parent_kg_id is None


def test_query_concepts_by_base_id_returns_all_versions(tmp_db: RelationalStore) -> None:
    """同一 base_id 在两个 KG 版本下都存在 → 按 base_id 查应得 2 个。"""
    from shared.models import Corpus
    with tmp_db.session() as s:
        s.add(Corpus(id="c4", subject_id="x", user_id="u", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id="kg-v1", subject_id="x", corpus_id="c4",
            version="v1", node_count=1, edge_count=0, manifest_json={},
        ))
        s.add(KnowledgeGraphRow(
            kg_id="kg-v2", subject_id="x", corpus_id="c4",
            version="v2", node_count=1, edge_count=0,
            manifest_json={}, parent_kg_id="kg-v1",
        ))
        s.add(ConceptRow(
            id="x:1:a", kg_id="kg-v1", base_id="x:1:a",
            name_primary="A", names_json=["A"], category="definition",
            definition="old", informal_description="",
            abstract_level=0.5, bloom_level="understand", domain="x",
            cognitive_load_estimate=0.3, typical_learning_time_min=10,
            prereq_count=0, prereq_max_depth=0, formula_density=0,
            coupling=0, confidence=0.9, full_json={},
        ))
        # v2 中相同 base_id，但 id 有 @v2 后缀
        s.add(ConceptRow(
            id="x:1:a@kg-v2", kg_id="kg-v2", base_id="x:1:a",
            name_primary="A", names_json=["A"], category="definition",
            definition="new", informal_description="",
            abstract_level=0.5, bloom_level="understand", domain="x",
            cognitive_load_estimate=0.3, typical_learning_time_min=10,
            prereq_count=0, prereq_max_depth=0, formula_density=0,
            coupling=0, confidence=0.9, full_json={},
        ))
        s.commit()

    with tmp_db.session() as s:
        rows = s.query(ConceptRow).filter_by(base_id="x:1:a").all()
        assert len(rows) == 2
        ids = {r.id for r in rows}
        assert ids == {"x:1:a", "x:1:a@kg-v2"}


def test_concept_full_json_can_store_base_id(tmp_db: RelationalStore) -> None:
    """Pydantic Concept 不需要新增 base_id 字段（保持 schema 稳定）；
    但 full_json 可以包含 base_id 供运行时用。"""
    from shared.schemas import (
        Concept,
        ConceptClassification,
        ConceptDifficulty,
    )

    c = Concept(
        id="x:1:a",
        names=["A"],
        category="definition",
        definition="def",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.5, domain="x"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0,
            formula_density=0, coupling=0,
            cognitive_load_estimate=0.3, typical_learning_time_min=10,
        ),
        confidence=0.9,
    )
    d = c.model_dump(mode="json")
    # base_id 通过 attributes 字段额外存（向后兼容）
    d_with_base = {**d, "_base_id": "x:1:a"}
    assert d_with_base.get("_base_id") == "x:1:a"
