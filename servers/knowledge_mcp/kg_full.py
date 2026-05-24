"""kg_full — depth=full 的两个产物：确定性难度校准 + 本地 embedding。

难度校准（compute_calibrated_difficulty）:
  没有真实难度标注数据集，用可解释加权特征公式而非未训练的 XGBoost。
  特征已由 ConceptDifficulty / ConceptClassification 给出，全部归一到 [0,1]：
    cognitive_load(0.30) + formula_density(0.20) + abstract_level(0.20)
    + norm(prereq_max_depth)(0.15) + norm(learning_time)(0.15)
  权重和=1 → 结果天然 ∈[0,1]，单调（任一特征升高 → 难度升高）。
  将来有学习者答题正确率数据时，可用它做监督训练替换本公式。

embedding（build_embeddings）:
  numpy feature-hashing TF 向量（固定维度，L2 归一化），零额外依赖。
  中文按 2-gram、英文/数字按 token 切分，hash 到 dim 个桶累加词频，再 L2 归一。
  支持余弦近邻语义检索。装了 chromadb 时由 builder 另写专业向量库。
"""
from __future__ import annotations

import hashlib
import re

import numpy as np

from shared.schemas import Concept

_EMBED_DIM = 64
# 难度特征权重（和为 1.0）
_W_LOAD = 0.30
_W_FORMULA = 0.20
_W_ABSTRACT = 0.20
_W_DEPTH = 0.15
_W_TIME = 0.15

_DEPTH_NORM = 5.0   # prereq_max_depth ≥5 视为满难度
_TIME_NORM = 60.0   # learning_time ≥60min 视为满难度

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
_CJK_RE = re.compile(r"[一-鿿]")


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_calibrated_difficulty(concept: Concept) -> float:
    """确定性加权难度分 ∈[0,1]。"""
    d = concept.difficulty
    cls = concept.classification
    depth_norm = _clip01(d.prereq_max_depth / _DEPTH_NORM)
    time_norm = _clip01(d.typical_learning_time_min / _TIME_NORM)
    score = (
        _W_LOAD * d.cognitive_load_estimate
        + _W_FORMULA * d.formula_density
        + _W_ABSTRACT * cls.abstract_level
        + _W_DEPTH * depth_norm
        + _W_TIME * time_norm
    )
    return round(_clip01(score), 4)


def _tokenize(text: str) -> list[str]:
    """英文/数字 token + 中文 2-gram。"""
    text = (text or "").lower()
    tokens = _TOKEN_RE.findall(text)
    cjk = _CJK_RE.findall(text)
    # 中文相邻字组 bigram；单字也留作 unigram 兜底
    cjk_str = "".join(cjk)
    tokens.extend(cjk_str[i:i + 2] for i in range(len(cjk_str) - 1))
    tokens.extend(cjk)
    return tokens


def _hash_bucket(token: str, dim: int) -> int:
    h = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(h, 16) % dim


def _concept_text(c: Concept) -> str:
    parts = list(c.names) + [c.definition, c.informal_description]
    parts.extend(c.keywords or [])
    return " ".join(p for p in parts if p)


def embed_text(text: str, dim: int = _EMBED_DIM) -> list[float]:
    """单条文本 → L2 归一化的 feature-hashing 词频向量。"""
    vec = np.zeros(dim, dtype=np.float64)
    for tok in _tokenize(text):
        vec[_hash_bucket(tok, dim)] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return [round(float(x), 6) for x in vec]


def build_embeddings(concepts: list[Concept], dim: int = _EMBED_DIM) -> dict[str, list[float]]:
    """每个 concept → embedding 向量（id → vec）。"""
    return {c.id: embed_text(_concept_text(c), dim) for c in concepts}


def cosine(a: list[float], b: list[float]) -> float:
    """两个等长向量余弦相似度（向量已 L2 归一时即点积）。"""
    va, vb = np.asarray(a), np.asarray(b)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))
