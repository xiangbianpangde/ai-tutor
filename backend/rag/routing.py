"""backend.rag.routing —— 关键字路由（M-008 默认策略）。

设计文档的 RoutingAdapter（Strategy 模式）务实落地为单个 KeywordRouter：从 query
抽内容关键字（去停用词），决定检索范围。当前只有 "concept" 一个范围；保留 Protocol
便于未来按 query 意图路由到不同语料（corpus / web / 公式库）。
"""
from __future__ import annotations

from typing import Protocol

from .retriever import tokenize
from .types import RouteDecision


class Router(Protocol):
    def route(self, query: str) -> RouteDecision: ...


class KeywordRouter:
    """默认路由：抽 query 关键字，范围恒定 concept（KG 概念检索）。"""

    def __init__(self, *, scope: str = "concept") -> None:
        self._scope = scope

    def route(self, query: str) -> RouteDecision:
        keywords = list(dict.fromkeys(tokenize(query)))  # 去重保序
        return RouteDecision(
            scope=self._scope,
            keywords=keywords,
            reason=f"{len(keywords)} 个内容关键字 → 范围 {self._scope}",
        )
