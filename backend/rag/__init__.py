"""backend.rag —— RAG 引擎（M-008，对应 v2 #9 AgenticRAG）。

务实落地：词法检索 + NLI 风格验证 + 自主重检索循环，无 ChromaDB/transformers 重依赖。
向量后端经 ChunkSource Protocol 注入即可平滑替换。
"""
from __future__ import annotations

from .engine import (
    STATE_CANNOT_CONFIRM,
    STATE_VALIDATED,
    RAGEngine,
)
from .retriever import KGChunkSource, LexicalRetriever, StaticChunkSource, tokenize
from .routing import KeywordRouter
from .types import Chunk, RetrieveResult, RouteDecision, ValidationResult
from .validator import AnswerValidator

__all__ = [
    "RAGEngine",
    "LexicalRetriever",
    "KGChunkSource",
    "StaticChunkSource",
    "KeywordRouter",
    "AnswerValidator",
    "Chunk",
    "RouteDecision",
    "ValidationResult",
    "RetrieveResult",
    "tokenize",
    "STATE_VALIDATED",
    "STATE_CANNOT_CONFIRM",
]
