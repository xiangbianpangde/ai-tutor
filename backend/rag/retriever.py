"""backend.rag.retriever —— 词法检索器（M-008，BM25-lite，无外部向量库）。

设计文档定的 ChromaDB 是 100 用户后才需要的重后端；当前阶段务实用纯 Python
词法检索（idf 加权 token 重叠），确定性、零网络、可测，且把 chunk 来源抽成
Protocol——未来要换 Chroma/Qdrant 只换 ChunkSource，engine 不动（OCP）。

中文无空格：tokenize 同时产出 ascii 词 + CJK 单字 + CJK 双字 bigram，召回更稳。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from .types import Chunk

_ASCII_WORD = re.compile(r"[a-z0-9]+")
_CJK = re.compile(r"[一-鿿]")
# 极简停用词（中英），避免把"的/是/the/a"当检索信号
_STOP = {
    "the", "a", "an", "of", "to", "is", "are", "and", "or", "in", "on", "for",
    "what", "how", "why", "with", "as", "by", "at", "be", "this", "that",
    "的", "是", "了", "和", "与", "在", "有", "对", "我", "你", "他", "它",
    "什么", "怎么", "为什么", "如何", "吗", "呢", "吧",
}


def tokenize(text: str) -> list[str]:
    """ascii 词 + CJK 单字 + CJK 双字 bigram；过滤停用词。"""
    text = (text or "").lower()
    tokens: list[str] = [w for w in _ASCII_WORD.findall(text) if w not in _STOP]
    cjk = _CJK.findall(text)
    tokens.extend(c for c in cjk if c not in _STOP)
    # 连续 CJK 的 bigram（提升中文短语区分度）
    cjk_runs = re.findall(r"[一-鿿]{2,}", text)
    for run in cjk_runs:
        for i in range(len(run) - 1):
            bg = run[i : i + 2]
            if bg not in _STOP:
                tokens.append(bg)
    return tokens


class ChunkSource(Protocol):
    """检索语料来源抽象。换向量后端只换实现。"""

    def chunks(self) -> Iterable[Chunk]: ...


class StaticChunkSource:
    """内存固定 chunk 列表（测试/小语料用）。"""

    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self._chunks = list(chunks)

    def chunks(self) -> list[Chunk]:
        return list(self._chunks)


class KGChunkSource:
    """从 KG 概念表装载 chunk：每个概念 = 名 + 别名 + 定义 + 非形式描述。

    只读 store，不写。绑定单个 kg_id。
    """

    def __init__(self, store: Any, kg_id: str) -> None:
        self._store = store
        self._kg_id = kg_id

    def chunks(self) -> list[Chunk]:
        from shared.models import ConceptRow

        out: list[Chunk] = []
        with self._store.session() as s:
            rows = s.query(ConceptRow).filter_by(kg_id=self._kg_id).all()
            for c in rows:
                aliases = " ".join(c.names_json or [])
                parts = [c.name_primary, aliases, c.definition or "", c.informal_description or ""]
                text = "\n".join(p for p in parts if p)
                out.append(
                    Chunk(
                        id=c.id,
                        text=text,
                        source=c.id,
                        metadata={
                            "name": c.name_primary,
                            "category": c.category,
                            "kg_id": self._kg_id,
                        },
                    )
                )
        return out


class LexicalRetriever:
    """idf 加权 token 重叠检索（BM25-lite）。索引惰性构建并缓存。"""

    def __init__(self, source: ChunkSource) -> None:
        self._source = source
        self._chunks: list[Chunk] | None = None
        self._chunk_tokens: list[Counter[str]] | None = None
        self._idf: dict[str, float] | None = None

    def _ensure_index(self) -> None:
        if self._chunks is not None:
            return
        chunks = list(self._source.chunks())
        chunk_tokens = [Counter(tokenize(c.text)) for c in chunks]
        n = len(chunks)
        df: Counter[str] = Counter()
        for tok in chunk_tokens:
            for term in tok:
                df[term] += 1
        # 平滑 idf；n=0 时为空
        idf = {term: math.log(1 + n / (1 + d)) for term, d in df.items()} if n else {}
        self._chunks = chunks
        self._chunk_tokens = chunk_tokens
        self._idf = idf

    def invalidate(self) -> None:
        """语料变更后清索引（重建图后调用）。"""
        self._chunks = None
        self._chunk_tokens = None
        self._idf = None

    def retrieve(
        self, query: str, *, top_k: int = 5, extra_terms: Sequence[str] | None = None
    ) -> list[Chunk]:
        """返回按相关分降序的 top_k chunk（分写入 chunk.score）。"""
        self._ensure_index()
        assert self._chunks is not None and self._chunk_tokens is not None and self._idf is not None
        if not self._chunks:
            return []

        q_terms = Counter(tokenize(query))
        for t in extra_terms or ():
            q_terms[t] += 1
        if not q_terms:
            return []

        scored: list[Chunk] = []
        for chunk, ctoks in zip(self._chunks, self._chunk_tokens, strict=True):
            doc_len = sum(ctoks.values()) or 1
            s = 0.0
            for term, qf in q_terms.items():
                tf = ctoks.get(term, 0)
                if not tf:
                    continue
                idf = self._idf.get(term, 0.0)
                # tf 归一（抑制长文档膨胀）× idf × query 频次
                s += (tf / doc_len) * idf * qf
            if s > 0:
                scored.append(
                    Chunk(id=chunk.id, text=chunk.text, source=chunk.source, score=round(s, 6),
                          metadata=dict(chunk.metadata))
                )
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]
