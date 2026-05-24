"""kg_full 纯函数测试：难度校准 + embedding。"""
from __future__ import annotations

import pytest

from servers.knowledge_mcp.kg_full import (
    _EMBED_DIM,
    build_embeddings,
    compute_calibrated_difficulty,
    cosine,
    embed_text,
)
from shared.schemas import Concept, ConceptClassification, ConceptDifficulty


def _concept(cid="x:1:a", *, load=0.3, formula=0.2, abstract=0.3,
             depth=1, time=10, names=None, definition="定义", keywords=None) -> Concept:
    return Concept(
        id=cid,
        names=names or ["概念A"],
        category="definition",
        definition=definition,
        informal_description="",
        classification=ConceptClassification(
            bloom_level="understand", abstract_level=abstract, domain="math",
        ),
        difficulty=ConceptDifficulty(
            prereq_count=depth, prereq_max_depth=depth, formula_density=formula,
            coupling=0.3, cognitive_load_estimate=load, typical_learning_time_min=time,
        ),
        keywords=keywords or [],
        confidence=0.9,
    )


# ---------------- 难度校准 ---------------- #


def test_difficulty_in_range():
    assert 0.0 <= compute_calibrated_difficulty(_concept()) <= 1.0


def test_difficulty_monotonic_in_cognitive_load():
    low = compute_calibrated_difficulty(_concept(load=0.1))
    high = compute_calibrated_difficulty(_concept(load=0.9))
    assert high > low


def test_difficulty_monotonic_in_formula_and_depth():
    # time 最小 1（schema ge=1），故 easy 不会是纯 0，但应非常接近
    easy = compute_calibrated_difficulty(_concept(formula=0.0, depth=0, abstract=0.0, time=1, load=0.0))
    hard = compute_calibrated_difficulty(_concept(formula=1.0, depth=8, abstract=1.0, time=120, load=1.0))
    assert easy < hard
    assert hard == pytest.approx(1.0, abs=1e-6)
    assert easy < 0.05  # 全特征最低 → 接近 0


def test_difficulty_depth_capped():
    """prereq_max_depth 超过归一上限不应让总分越界。"""
    d = compute_calibrated_difficulty(_concept(depth=100))
    assert 0.0 <= d <= 1.0


# ---------------- embedding ---------------- #


def test_embedding_fixed_dim_and_normalized():
    v = embed_text("机器学习 是 一种 方法 method")
    assert len(v) == _EMBED_DIM
    import math
    norm = math.sqrt(sum(x * x for x in v))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_embedding_empty_text_zero_vector():
    v = embed_text("")
    assert len(v) == _EMBED_DIM
    assert all(x == 0.0 for x in v)


def test_build_embeddings_keyed_by_id():
    cs = [_concept("x:1:a"), _concept("x:1:b")]
    emb = build_embeddings(cs)
    assert set(emb.keys()) == {"x:1:a", "x:1:b"}
    assert all(len(v) == _EMBED_DIM for v in emb.values())


def test_cosine_similar_concepts_higher():
    """文本相近的概念余弦更高。"""
    a = _concept("x:1:a", names=["梯度下降"], definition="一种优化算法 通过梯度迭代", keywords=["优化", "梯度"])
    b = _concept("x:1:b", names=["梯度下降法"], definition="优化算法 沿梯度方向迭代", keywords=["优化", "梯度"])
    c = _concept("x:1:c", names=["贝叶斯定理"], definition="条件概率公式 先验后验", keywords=["概率"])
    emb = build_embeddings([a, b, c])
    sim_ab = cosine(emb["x:1:a"], emb["x:1:b"])
    sim_ac = cosine(emb["x:1:a"], emb["x:1:c"])
    assert sim_ab > sim_ac


def test_cosine_zero_vector_safe():
    assert cosine([0.0] * _EMBED_DIM, [0.0] * _EMBED_DIM) == 0.0
