"""backend.rag.types —— RAG 引擎轻量数据类型（M-008）。

不用 ChromaDB / transformers 的重类型；纯 dataclass，可序列化为 REST 信封。
设计文档的 Chunk / ValidationResult / RouteDecision 在此务实落地。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Chunk:
    """一个检索单元（默认 = 一个 KG 概念：名+别名+定义）。"""

    id: str
    text: str
    source: str  # 来源标识（如 concept_id / 文件路径）
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RouteDecision:
    """关键字路由结果：检索范围 + 抽出的内容关键字。"""

    scope: str  # "concept"（默认，over KG 概念）/ 未来可扩 "corpus"
    keywords: list[str]
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    """答案-引用源一致性验证结果（NLI 风格）。

    method: "llm"（注入法官）或 "heuristic"（词法回退，永不过度授信）。
    """

    is_supported: bool
    confidence: float
    mismatched_claims: list[str] = field(default_factory=list)
    method: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetrieveResult:
    """retrieve() 的完整结果：含重检索轮次与是否达标，便于 API 透明披露。"""

    chunks: list[Chunk]
    confirmed: bool  # 最高分是否 >= nli_threshold
    rounds: int
    top_score: float
    state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunks": [c.to_dict() for c in self.chunks],
            "confirmed": self.confirmed,
            "rounds": self.rounds,
            "top_score": self.top_score,
            "state": self.state,
        }
