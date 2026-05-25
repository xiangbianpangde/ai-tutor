"""Quality Gate 结构化检查测试（_compute_quality 的三项门）。

1. 章节覆盖率 ≥ 85%（真实定义占比）
2. 每概念 ≥ 1 示例
3. 类别分布合理性（避免单一类别压倒性占比）

门均为「告警」语义：不把骨架图误判为 fail，只产出供 review_kg 的提示。
"""
from __future__ import annotations

from servers.knowledge_mcp.kg_enrich_adapter import _chapter_coverage, _compute_quality
from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    Example,
    Relation,
)


def _c(cid: str, name: str, *, definition: str, category: str = "definition",
       with_example: bool = True) -> Concept:
    return Concept(
        id=cid,
        names=[name],
        category=category,  # type: ignore[arg-type]
        definition=definition,
        informal_description="",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=0.4, domain="t"
        ),
        difficulty=ConceptDifficulty(
            prereq_count=0, prereq_max_depth=0, formula_density=0.2,
            coupling=0.2, cognitive_load_estimate=0.3, typical_learning_time_min=15,
        ),
        examples=[Example(text="例", type="computation")] if with_example else [],
        confidence=0.8,
    )


def _edge(a: str, b: str) -> Relation:
    return Relation(from_id=a, to_id=b, type="part_of", weight=0.8,
                    explanation="x", confidence=0.7)


def _well_formed(n: int = 6) -> list[Concept]:
    """高覆盖 + 有示例 + 类别均衡的概念集。"""
    cats = ["definition", "method", "theorem"]
    return [
        _c(f"t:{i}:c", f"概念{i}", definition=f"概念{i}的真实定义阐述",
           category=cats[i % len(cats)], with_example=True)
        for i in range(n)
    ]


def test_chapter_coverage_placeholder_vs_real() -> None:
    # 占位定义（definition == 标题）不算覆盖
    placeholder = [_c("t:1:a", "向量", definition="向量", with_example=True)]
    assert _chapter_coverage(placeholder) == 0.0
    real = [_c("t:1:a", "向量", definition="有方向和大小的量", with_example=True)]
    assert _chapter_coverage(real) == 1.0


def test_well_formed_kg_passes_without_gate_warnings() -> None:
    concepts = _well_formed()
    edges = [_edge(f"t:{i}:c", f"t:{i-1}:c") for i in range(1, len(concepts))]
    q = _compute_quality(concepts, edges)
    assert q.chapter_coverage == 1.0
    text = " ".join(q.warnings)
    assert "覆盖率" not in text
    assert "缺少示例" not in text
    assert "分布失衡" not in text


def test_low_coverage_warns() -> None:
    # 6 个里 5 个是占位定义 → 覆盖率 ~17% < 85%
    concepts = [_c("t:0:c", "A", definition="A 的真实定义")]
    concepts += [_c(f"t:{i}:c", f"N{i}", definition=f"N{i}") for i in range(1, 6)]
    q = _compute_quality(concepts, [])
    assert q.chapter_coverage < 0.85
    assert any("覆盖率" in w for w in q.warnings)


def test_missing_examples_warns() -> None:
    concepts = [
        _c("t:0:c", "A", definition="A 的定义", with_example=True),
        _c("t:1:c", "B", definition="B 的定义", with_example=False),
        _c("t:2:c", "C", definition="C 的定义", with_example=False),
    ]
    q = _compute_quality(concepts, [])
    assert any("缺少示例" in w for w in q.warnings)
    assert any("2/3" in w for w in q.warnings)


def test_category_skew_warns() -> None:
    # 6 个概念全是 definition → 失衡（100% > 90%）
    concepts = [
        _c(f"t:{i}:c", f"概念{i}", definition=f"概念{i}的定义", category="definition")
        for i in range(6)
    ]
    q = _compute_quality(concepts, [])
    assert any("分布失衡" in w for w in q.warnings)


def test_category_skew_skipped_for_small_n() -> None:
    # 概念数 < 5 时不做分布检查
    concepts = [
        _c(f"t:{i}:c", f"概念{i}", definition=f"概念{i}的定义", category="definition")
        for i in range(3)
    ]
    q = _compute_quality(concepts, [])
    assert not any("分布失衡" in w for w in q.warnings)


def test_gate_warnings_do_not_force_fail() -> None:
    """低覆盖/缺示例只产出告警，overall 仍是 pass_with_warnings，不是 fail。"""
    concepts = [_c(f"t:{i}:c", f"N{i}", definition=f"N{i}", with_example=False) for i in range(6)]
    q = _compute_quality(concepts, [])
    assert q.overall == "pass_with_warnings"
