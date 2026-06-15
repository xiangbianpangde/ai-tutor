"""backend.rag.engine —— RAG 引擎统一入口（M-008，对应 v2 #9 AgenticRAG）。

编排 routing → retrieval →（重检索循环 ≤3 轮）→ validation，落地设计文档 MD-M-008
状态机：IDLE→RETRIEVED→SCORED→VALIDATED / CANNOT_CONFIRM。

务实取舍（对齐 C2 全波次哲学）：
- 不引 ChromaDB / transformers；检索 = LexicalRetriever，验证 = AnswerValidator。
- 缓存（M-005）/ 事件（M-006）可注入；不注入则退化为纯检索，零外部依赖、可测。
- 方法 async（匹配设计 + 未来 LLM 调用），内部同步——测试用 asyncio.run。

Agentic 体现：单轮检索最高分 < 阈值时**自主重检索**——逐轮放宽 top_k 并把路由关键字
并入 query 重打分，最多 max_rounds 轮；仍不达标则 confirmed=False（透明披露，不假装确认）。
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from shared.logging_config import get_logger

from .retriever import LexicalRetriever
from .routing import KeywordRouter, Router
from .types import Chunk, RetrieveResult, ValidationResult
from .validator import AnswerValidator

logger = get_logger("backend.rag.engine")

# 状态机常量（MD-M-008）
STATE_IDLE = "IDLE"
STATE_RETRIEVED = "RETRIEVED"
STATE_SCORED = "SCORED"
STATE_VALIDATED = "VALIDATED"
STATE_CANNOT_CONFIRM = "CANNOT_CONFIRM"


class RAGEngine:
    """RAG 引擎——统一检索/验证入口，编排四子能力。"""

    def __init__(
        self,
        retriever: LexicalRetriever,
        validator: AnswerValidator,
        *,
        router: Router | None = None,
        cache: Any = None,
        events: Any = None,
        max_rounds: int = 3,
        nli_threshold: float = 0.7,
        top_k: int = 5,
    ) -> None:
        self.retriever = retriever
        self.validator = validator
        self.router = router or KeywordRouter()
        self.cache = cache
        self.events = events
        self.max_rounds = max(1, min(max_rounds, 5))
        self.nli_threshold = nli_threshold
        self.top_k = top_k

    async def retrieve(self, query: str, top_k: int | None = None) -> RetrieveResult:
        """检索 + 自主重检索循环。top_score 用相关分归一近似 NLI（无模型时的代理信号）。"""
        if not query or not query.strip():
            from shared.errors import TutorError

            raise TutorError("RAG_EMPTY_QUERY", hint="query 不能为空")
        k = top_k or self.top_k

        cached = self._cache_get("retrieve", query, k)
        if cached is not None:
            return cached

        decision = self.router.route(query)
        state = STATE_IDLE
        best: list[Chunk] = []
        top_score = 0.0
        rounds = 0
        for rounds in range(1, self.max_rounds + 1):
            widen = k * rounds  # 逐轮放宽召回
            extra = decision.keywords if rounds > 1 else None  # 重检索轮并入路由关键字
            chunks = self.retriever.retrieve(query, top_k=widen, extra_terms=extra)
            state = STATE_RETRIEVED
            if chunks:
                best = chunks[:k]
                top_score = self._normalize_score(chunks[0].score, chunks)
                state = STATE_SCORED
            else:
                best = []
                top_score = 0.0
            if top_score >= self.nli_threshold:
                state = STATE_VALIDATED
                break
        confirmed = top_score >= self.nli_threshold
        if not confirmed:
            state = STATE_CANNOT_CONFIRM
        result = RetrieveResult(
            chunks=best, confirmed=confirmed, rounds=rounds,
            top_score=round(top_score, 4), state=state,
        )
        logger.info("rag.retrieve", query_len=len(query), rounds=rounds,
                    confirmed=confirmed, top_score=result.top_score, n=len(best))
        await self._emit("rag.retrieve", {
            "rounds": rounds, "confirmed": confirmed, "n": len(best),
            "top_score": result.top_score,
        })
        self._cache_set("retrieve", query, k, result)
        return result

    async def validate_answer(self, answer: str, sources: Sequence[str]) -> ValidationResult:
        """验证答案被引用源支撑。NLI 法官优先，否则词法回退（永不过度授信）。"""
        result = self.validator.validate(answer, list(sources or []))
        await self._emit("rag.validate", {
            "is_supported": result.is_supported,
            "confidence": result.confidence,
            "method": result.method,
        })
        return result

    # ---------- 内部 ----------

    @staticmethod
    def _normalize_score(top_raw: float, chunks: list[Chunk]) -> float:
        """把 BM25-lite 绝对分归一到 [0,1] 作 NLI 代理信号。

        用 top 相对全体分布的领先度：top / (top + 次优)；只有 1 个命中时按饱和函数。
        命中越独占、分越高 → 越接近 1，近似"高置信检索到了对的东西"。
        """
        if not chunks or top_raw <= 0:
            return 0.0
        if len(chunks) == 1:
            return round(top_raw / (top_raw + 0.1), 4)  # 单命中饱和
        second = chunks[1].score
        lead = top_raw / (top_raw + second) if (top_raw + second) > 0 else 0.0
        # 领先度 × 绝对分饱和，兼顾"独占"与"够强"
        absolute = top_raw / (top_raw + 0.1)
        return round(0.5 * lead + 0.5 * absolute, 4)

    def _cache_get(self, op: str, query: str, k: int) -> RetrieveResult | None:
        if self.cache is None:
            return None
        try:
            raw = self.cache.get("rag", op, [{"role": "user", "content": f"{query}|{k}"}], 0.0)
            if raw is None:
                return None
            data = json.loads(raw)
            return RetrieveResult(
                chunks=[Chunk(**c) for c in data["chunks"]],
                confirmed=data["confirmed"], rounds=data["rounds"],
                top_score=data["top_score"], state=data["state"],
            )
        except Exception:
            return None

    def _cache_set(self, op: str, query: str, k: int, result: RetrieveResult) -> None:
        if self.cache is None:
            return
        try:
            self.cache.set(
                "rag", op, [{"role": "user", "content": f"{query}|{k}"}], 0.0,
                json.dumps(result.to_dict(), ensure_ascii=False), ttl_s=3600,
            )
        except Exception:
            pass

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self.events is None:
            return
        try:
            from ..middleware.event_bus import Event

            await self.events.publish(Event(type=event_type, payload=payload))
        except Exception:
            pass
