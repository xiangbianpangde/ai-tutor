"""backend.memory.longterm —— 长期记忆（M-013，对应 v2 #18 长期幻觉）。

22 问题 #18「长期幻觉」：AI 跨会话记不住已确认的事实，越聊越编。本模块把**已确认的事实**
落库长存，供后续回答检索接地（grounding）。LRU 淘汰防无限膨胀。

按 FDR-013-001 引 service Façade（LongTermMemory）统一编排 save/query/evict/extract，上层
只依赖 Façade 不碰底层表（Repository 模式）。表 `long_term_facts` 自建自管（CREATE IF NOT
EXISTS，落同库），不改 shared ORM。
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from sqlalchemy import text

from ..rag.retriever import tokenize

_DDL = """
CREATE TABLE IF NOT EXISTS long_term_facts (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    subject_id       TEXT NOT NULL,
    content          TEXT NOT NULL,
    source           TEXT,
    created_at       REAL NOT NULL,
    last_accessed_at REAL NOT NULL,
    access_count     INTEGER NOT NULL DEFAULT 0
)
"""

_SENTENCE = re.compile(r"[^。！？.!?\n]+[。！？.!?]?")


def extract_facts(text_blob: str, *, min_len: int = 6, max_facts: int = 50) -> list[str]:
    """从文本切出候选事实句（按句末标点/换行；过滤过短/纯标点）。"""
    out: list[str] = []
    for m in _SENTENCE.findall(text_blob or ""):
        s = m.strip()
        if len(s) >= min_len and any(c.isalnum() for c in s):
            out.append(s)
        if len(out) >= max_facts:
            break
    return out


class LongTermMemory:
    """长期事实记忆 Façade：save / query / evict_lru / extract。"""

    def __init__(self, db: Any, *, max_facts_per_subject: int = 500) -> None:
        self.db = db
        self.max_facts = max_facts_per_subject
        with self.db.engine.begin() as conn:
            conn.execute(text(_DDL))

    @staticmethod
    def _fact_id(user_id: str, subject_id: str, content: str) -> str:
        payload = f"{user_id}|{subject_id}|{content.strip()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def save_fact(
        self, *, user_id: str, subject_id: str, content: str, source: str | None = None,
        now: float | None = None,
    ) -> str:
        """落一条事实（按 user+subject+content 去重幂等）；返回 fact_id。超额触发 LRU 淘汰。"""
        content = (content or "").strip()
        if not content:
            from shared.errors import TutorError

            raise TutorError("MEMORY_EMPTY_FACT", hint="content 不能为空")
        now = time.time() if now is None else now
        fid = self._fact_id(user_id, subject_id, content)
        with self.db.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO long_term_facts
                        (id, user_id, subject_id, content, source, created_at, last_accessed_at, access_count)
                    VALUES (:id, :u, :s, :c, :src, :now, :now, 0)
                    ON CONFLICT(id) DO UPDATE SET
                        last_accessed_at = :now,
                        source = COALESCE(excluded.source, long_term_facts.source)
                    """
                ),
                {"id": fid, "u": user_id, "s": subject_id, "c": content, "src": source, "now": now},
            )
        self.evict_lru(user_id=user_id, subject_id=subject_id, now=now)
        return fid

    def query_facts(
        self, *, user_id: str, subject_id: str, query: str | None = None, limit: int = 10,
        now: float | None = None,
    ) -> list[dict]:
        """检索事实。给 query 时按 token 重叠排序，否则按最近访问。命中项刷新 last_accessed。"""
        now = time.time() if now is None else now
        with self.db.engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, content, source, access_count, last_accessed_at "
                    "FROM long_term_facts WHERE user_id=:u AND subject_id=:s"
                ),
                {"u": user_id, "s": subject_id},
            ).all()
            facts = [
                {"id": r[0], "content": r[1], "source": r[2],
                 "access_count": r[3], "last_accessed_at": r[4]}
                for r in rows
            ]
            if query:
                q_terms = set(tokenize(query))
                scored = []
                for f in facts:
                    overlap = len(q_terms & set(tokenize(f["content"])))
                    if overlap > 0:
                        scored.append((overlap, f))
                scored.sort(key=lambda x: (x[0], x[1]["last_accessed_at"]), reverse=True)
                ranked = [f for _, f in scored][:limit]
            else:
                facts.sort(key=lambda f: f["last_accessed_at"], reverse=True)
                ranked = facts[:limit]
            # 刷新命中项访问元信息（LRU 行为）
            for f in ranked:
                conn.execute(
                    text(
                        "UPDATE long_term_facts SET last_accessed_at=:now, "
                        "access_count=access_count+1 WHERE id=:id"
                    ),
                    {"now": now, "id": f["id"]},
                )
        return ranked

    def evict_lru(
        self, *, user_id: str, subject_id: str, now: float | None = None
    ) -> int:
        """超出每科目上限时，淘汰最久未访问的事实；返回淘汰条数。"""
        with self.db.engine.begin() as conn:
            total = conn.execute(
                text("SELECT COUNT(*) FROM long_term_facts WHERE user_id=:u AND subject_id=:s"),
                {"u": user_id, "s": subject_id},
            ).scalar() or 0
            if total <= self.max_facts:
                return 0
            to_evict = total - self.max_facts
            victims = conn.execute(
                text(
                    "SELECT id FROM long_term_facts WHERE user_id=:u AND subject_id=:s "
                    "ORDER BY last_accessed_at ASC LIMIT :n"
                ),
                {"u": user_id, "s": subject_id, "n": to_evict},
            ).all()
            ids = [v[0] for v in victims]
            for vid in ids:
                conn.execute(text("DELETE FROM long_term_facts WHERE id=:id"), {"id": vid})
        return len(ids)

    def ingest_text(
        self, *, user_id: str, subject_id: str, text_blob: str, source: str | None = None
    ) -> list[str]:
        """从一段文本抽事实并批量落库（extract + save）；返回 fact_id 列表。"""
        ids = []
        for fact in extract_facts(text_blob):
            ids.append(self.save_fact(user_id=user_id, subject_id=subject_id,
                                      content=fact, source=source))
        return ids
