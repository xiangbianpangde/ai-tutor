"""backend.middleware.cache_layer —— SQLite L1 LLM 缓存（M-005 / spec 03 功能3）。

相同 (provider, model, messages, temperature) 命中直接返回，省 token。

与 v1 `shared.llm_cache.CachedLLMProvider`（进程内 LRU，重启即失）的区别：
**本层落 SQLite，跨进程/重启存活**——这是"v2 第一波过堂"挑战（重复问题命中 + 进程重启可续）的缓存侧基础。

缓存键 = sha256(provider + model + messages_json + temperature)；TTL 默认 24h，可按调用覆盖。
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from sqlalchemy import create_engine, text

DEFAULT_TTL_S = 24 * 3600  # 概念定义类默认 24h；判分/讲解类调用方传更短 ttl_s

_DDL = """
CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key  TEXT PRIMARY KEY,
    provider   TEXT NOT NULL,
    model      TEXT NOT NULL,
    response   TEXT NOT NULL,
    tokens     INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    expires_at REAL
)
"""


class CacheLayer:
    """SQLite 实现的 L1 LLM 缓存。命中率 / 节省 token 经 :meth:`stats` 暴露。"""

    def __init__(self, db_url: str, *, default_ttl_s: int | None = DEFAULT_TTL_S) -> None:
        connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
        self._engine = create_engine(db_url, future=True, connect_args=connect_args)
        self._default_ttl_s = default_ttl_s
        # 运行期计数（重启归零；缓存条目本身落库存活）
        self._hits = 0
        self._misses = 0
        self._saved_tokens = 0
        with self._engine.begin() as conn:
            conn.execute(text(_DDL))

    @staticmethod
    def make_key(
        provider: str, model: str, messages: list[dict[str, Any]], temperature: float
    ) -> str:
        payload = json.dumps(
            {"provider": provider, "model": model, "messages": messages, "temp": temperature},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        *,
        now: float | None = None,
    ) -> str | None:
        """命中返回缓存 response，未命中/已过期返回 None（过期项顺手删除）。"""
        now = time.time() if now is None else now
        key = self.make_key(provider, model, messages, temperature)
        with self._engine.begin() as conn:
            row = conn.execute(
                text("SELECT response, tokens, expires_at FROM cache_entries WHERE cache_key = :k"),
                {"k": key},
            ).first()
            if row is None:
                self._misses += 1
                return None
            response, tokens, expires_at = row
            if expires_at is not None and now > expires_at:
                conn.execute(text("DELETE FROM cache_entries WHERE cache_key = :k"), {"k": key})
                self._misses += 1
                return None
        self._hits += 1
        self._saved_tokens += tokens or 0
        return response

    def set(
        self,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        response: str,
        *,
        tokens: int = 0,
        ttl_s: int | None = None,
        now: float | None = None,
    ) -> None:
        """写入/更新缓存。``ttl_s`` 省略时用默认；``ttl_s=None`` 显式表示永不过期需传 0 之外的语义——见下。"""
        now = time.time() if now is None else now
        ttl = self._default_ttl_s if ttl_s is None else ttl_s
        expires_at = None if ttl is None else now + ttl
        key = self.make_key(provider, model, messages, temperature)
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO cache_entries
                        (cache_key, provider, model, response, tokens, created_at, expires_at)
                    VALUES (:k, :p, :m, :r, :tok, :c, :e)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        response = excluded.response,
                        tokens = excluded.tokens,
                        created_at = excluded.created_at,
                        expires_at = excluded.expires_at
                    """
                ),
                {"k": key, "p": provider, "m": model, "r": response, "tok": tokens, "c": now, "e": expires_at},
            )

    def stats(self) -> dict[str, Any]:
        """命中率 + 节省 token + 当前条目数。"""
        total = self._hits + self._misses
        with self._engine.begin() as conn:
            entries = conn.execute(text("SELECT COUNT(*) FROM cache_entries")).scalar() or 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
            "saved_tokens": self._saved_tokens,
            "entries": int(entries),
        }

    def clear(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("DELETE FROM cache_entries"))
        self._hits = self._misses = self._saved_tokens = 0
