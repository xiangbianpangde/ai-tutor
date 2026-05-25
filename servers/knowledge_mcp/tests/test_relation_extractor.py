"""RelationExtractor 契约测试。

输入: 已富化的 Concept 列表 + 已有结构边（part_of/prerequisite_strong）+ LLMProvider
输出: 其余 10 种语义关系的 Relation 列表（绝不抛错，失败即降级为空）。
"""
from __future__ import annotations

import json

from shared.llm_client import MockLLMProvider, StubLLMProvider
from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    Relation,
    SourceRef,
)


def _concept(cid: str, name: str, definition: str = "定义") -> Concept:
    return Concept(
        id=cid,
        names=[name],
        category="definition",
        definition=definition,
        informal_description="x",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.5, domain="test"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0, formula_density=0.1,
            coupling=0.1, cognitive_load_estimate=0.3, typical_learning_time_min=30,
        ),
        confidence=0.7,
        sources=[SourceRef(type="textbook", ref="x.md")],
    )


def _concepts() -> list[Concept]:
    return [
        _concept("t:1:vector", "向量", "有方向和大小的量"),
        _concept("t:2:matrix", "矩阵", "二维数表，向量的推广"),
        _concept("t:3:eigen", "特征值", "由矩阵计算得到的标量"),
    ]


def _relations_json(rels: list[dict]) -> str:
    return json.dumps({"relations": rels}, ensure_ascii=False)


def test_extracts_typed_relations_by_id() -> None:
    from servers.knowledge_mcp.relation_extractor import RelationExtractor

    resp = _relations_json([
        {"from": "t:2:matrix", "to": "t:1:vector", "type": "generalizes",
         "weight": 0.8, "explanation": "矩阵是向量的推广", "confidence": 0.9},
        {"from": "t:3:eigen", "to": "t:2:matrix", "type": "computed_from",
         "weight": 0.7, "explanation": "特征值由矩阵算出", "confidence": 0.85},
    ])
    edges, warns = RelationExtractor(llm=MockLLMProvider(canned_responses=[resp])).extract(
        concepts=_concepts(), existing_edges=[]
    )
    assert warns == []
    assert {(e.from_id, e.to_id, e.type) for e in edges} == {
        ("t:2:matrix", "t:1:vector", "generalizes"),
        ("t:3:eigen", "t:2:matrix", "computed_from"),
    }
    assert all(isinstance(e, Relation) for e in edges)


def test_resolves_endpoint_by_name_fallback() -> None:
    """LLM 偶尔返回概念名而非 id → 用 names 兜底解析。"""
    from servers.knowledge_mcp.relation_extractor import RelationExtractor

    resp = _relations_json([
        {"from": "矩阵", "to": "向量", "type": "generalizes",
         "explanation": "名称兜底", "confidence": 0.8},
    ])
    edges, _ = RelationExtractor(llm=MockLLMProvider(canned_responses=[resp])).extract(
        concepts=_concepts(), existing_edges=[]
    )
    assert len(edges) == 1
    assert (edges[0].from_id, edges[0].to_id) == ("t:2:matrix", "t:1:vector")


def test_drops_invalid_type_and_unresolvable_endpoints() -> None:
    from servers.knowledge_mcp.relation_extractor import RelationExtractor

    resp = _relations_json([
        {"from": "t:1:vector", "to": "t:2:matrix", "type": "is_friends_with"},  # 非法 type
        {"from": "t:1:vector", "to": "不存在的概念", "type": "is_a"},            # 端点解析失败
        {"from": "t:1:vector", "to": "t:1:vector", "type": "is_a"},             # 自环
        {"from": "t:1:vector", "to": "t:2:matrix", "type": "is_a",
         "explanation": "合法", "confidence": 0.7},                              # 唯一合法
    ])
    edges, warns = RelationExtractor(llm=MockLLMProvider(canned_responses=[resp])).extract(
        concepts=_concepts(), existing_edges=[]
    )
    assert len(edges) == 1
    assert edges[0].type == "is_a"
    assert len(warns) >= 2  # 非法 type + 无法解析端点都应记 warning


def test_dedups_against_structural_edges() -> None:
    """LLM 重复产出已有的 part_of/prerequisite_strong → 跳过。"""
    from servers.knowledge_mcp.relation_extractor import RelationExtractor

    structural = [
        Relation(from_id="t:2:matrix", to_id="t:1:vector", type="part_of",
                 weight=0.9, explanation="结构边", confidence=0.7),
    ]
    resp = _relations_json([
        {"from": "t:2:matrix", "to": "t:1:vector", "type": "part_of",
         "explanation": "重复", "confidence": 0.8},   # 与结构边重复 → 跳过
        {"from": "t:2:matrix", "to": "t:1:vector", "type": "analogous_to",
         "explanation": "不同类型可共存", "confidence": 0.8},  # 同端点不同类型 → 保留
    ])
    edges, _ = RelationExtractor(llm=MockLLMProvider(canned_responses=[resp])).extract(
        concepts=_concepts(), existing_edges=structural
    )
    assert len(edges) == 1
    assert edges[0].type == "analogous_to"


def test_degrades_gracefully_when_llm_unavailable() -> None:
    """LLM 抛 PLUGIN_NOT_AVAILABLE → 不抛错，返回空关系 + warning（结构边由调用方保留）。"""
    from servers.knowledge_mcp.relation_extractor import RelationExtractor

    edges, warns = RelationExtractor(llm=StubLLMProvider()).extract(
        concepts=_concepts(), existing_edges=[]
    )
    assert edges == []
    assert len(warns) == 1


def test_tolerates_non_json() -> None:
    from servers.knowledge_mcp.relation_extractor import RelationExtractor

    edges, warns = RelationExtractor(
        llm=MockLLMProvider(canned_responses=["这是一段散文，不是 JSON"])
    ).extract(concepts=_concepts(), existing_edges=[])
    assert edges == []
    assert len(warns) == 1


def test_skips_when_too_many_concepts() -> None:
    from servers.knowledge_mcp.relation_extractor import RelationExtractor

    many = [_concept(f"t:{i}:c", f"概念{i}") for i in range(100)]
    llm = MockLLMProvider(canned_responses=[_relations_json([])])
    edges, warns = RelationExtractor(llm=llm).extract(concepts=many, existing_edges=[])
    assert edges == []
    assert len(warns) == 1
    assert len(llm.calls) == 0  # 超规模直接跳过，不调 LLM


def test_no_call_for_fewer_than_two_concepts() -> None:
    from servers.knowledge_mcp.relation_extractor import RelationExtractor

    llm = MockLLMProvider(canned_responses=[_relations_json([])])
    edges, warns = RelationExtractor(llm=llm).extract(
        concepts=[_concept("t:1:x", "x")], existing_edges=[]
    )
    assert edges == [] and warns == []
    assert len(llm.calls) == 0
