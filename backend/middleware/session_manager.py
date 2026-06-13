"""backend.middleware.session_manager —— 多会话管理（M-004 / spec 03 功能1）。

包 v1 `servers.tutoring_mcp.session.SessionStore`（SessionContext 的 create/load/save 不重写），
另建 `session_summaries` 表承载 v2 新增的会话元信息：摘要 / 已学概念 / token 计数 / 最后活跃 / 7 天 TTL。

`session_summaries` 由本层自建自管（CREATE IF NOT EXISTS，落同库），不改 shared ORM。
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, text

from servers.tutoring_mcp.session import SessionStore
from shared.errors import TutorError
from shared.models import SessionRow
from shared.schemas import SessionContext
from shared.storage import RelationalStore

DEFAULT_TTL_DAYS = 7
_TERMINAL = {"completed", "expired"}

_DDL = """
CREATE TABLE IF NOT EXISTS session_summaries (
    session_id       TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    subject_id       TEXT NOT NULL,
    summary          TEXT,
    concepts_covered TEXT,
    input_tokens     INTEGER NOT NULL DEFAULT 0,
    output_tokens    INTEGER NOT NULL DEFAULT 0,
    last_active_at   REAL,
    expires_at       REAL
)
"""


class SessionManager:
    """多会话并行：列表 / 切换 / 自动摘要 / token 计数 / 过期清理。"""

    def __init__(self, db: RelationalStore, *, ttl_days: int = DEFAULT_TTL_DAYS) -> None:
        self.db = db
        self.store = SessionStore(db)
        self._ttl_s = ttl_days * 24 * 3600
        with self.db.engine.begin() as conn:
            conn.execute(text(_DDL))

    # ----- 列表 / 切换 ------------------------------------------------- #
    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """用户全部会话（含摘要元信息）；已 expired 的不返回（spec 场景1/5）。"""
        with self.db.session() as s:
            rows = (
                s.query(SessionRow)
                .filter(SessionRow.user_id == user_id, SessionRow.status != "expired")
                .all()
            )
            base = [
                {"session_id": r.id, "subject_id": r.subject_id, "status": r.status,
                 "started_at": r.started_at}
                for r in rows
            ]
        meta = self._summaries({b["session_id"] for b in base})
        out = []
        for b in base:
            m = meta.get(b["session_id"], {})
            out.append({
                "session_id": b["session_id"],
                "subject_id": b["subject_id"],
                "status": b["status"],
                "summary": m.get("summary"),
                "concepts_covered": m.get("concepts_covered", []),
                "token_usage": m.get("input_tokens", 0) + m.get("output_tokens", 0),
                "last_active_at": m.get("last_active_at")
                or (b["started_at"].timestamp() if b["started_at"] else None),
            })
        return out

    def switch_session(self, user_id: str, session_id: str, *, now: float | None = None) -> SessionContext:
        """加载目标会话并校验归属（非本人 → SESSION_NOT_FOUND，不泄露存在性）。"""
        ctx = self.store.load(session_id)  # 不存在自然抛 SESSION_NOT_FOUND
        if ctx.user_id != user_id:
            raise TutorError("SESSION_NOT_FOUND", hint=session_id)
        self.touch(session_id, now=now)
        return ctx

    # ----- 摘要 / token / 活跃 ---------------------------------------- #
    def summarize(self, session_id: str, *, now: float | None = None) -> str:
        """从 session_stats 生成摘要（模板式，不依赖 LLM）并落 session_summaries（spec 场景3）。"""
        ctx = self.store.load(session_id)
        stats = ctx.session_stats
        covered, mastered = stats.concepts_covered, stats.concepts_mastered
        weak = [c for c in covered if c not in mastered]
        if weak:
            nxt = f"复习薄弱概念 {weak[0]}"
        elif ctx.current_concept_id:
            nxt = f"继续 {ctx.current_concept_id}"
        else:
            nxt = "进入下一概念"
        summary = f"学过 {len(covered)} 概念（掌握 {len(mastered)}）；薄弱 {len(weak)} 个；下一步：{nxt}"
        self._upsert(session_id, ctx.user_id, ctx.subject_id, now=now,
                     summary=summary, concepts_covered=covered)
        return summary

    def record_tokens(self, session_id: str, *, input_tokens: int = 0, output_tokens: int = 0,
                      now: float | None = None) -> None:
        """累加本会话 token 消耗（spec 场景4 的来源）。"""
        ctx = self.store.load(session_id)
        self._upsert(session_id, ctx.user_id, ctx.subject_id, now=now,
                     add_input=input_tokens, add_output=output_tokens)

    def token_usage(self, session_id: str) -> dict[str, int]:
        m = self._summaries({session_id}).get(session_id, {})
        i, o = m.get("input_tokens", 0), m.get("output_tokens", 0)
        return {"input_tokens": i, "output_tokens": o, "total_tokens": i + o}

    def touch(self, session_id: str, *, now: float | None = None) -> None:
        ctx = self.store.load(session_id)
        self._upsert(session_id, ctx.user_id, ctx.subject_id, now=now)

    # ----- 过期清理 --------------------------------------------------- #
    def cleanup_expired(self, *, now: float | None = None) -> int:
        """把 TTL 内无活跃的非终态会话标记 expired（spec 场景5）。返回清理数。"""
        now = time.time() if now is None else now
        cutoff = now - self._ttl_s
        meta = self._summaries(None)  # 全量
        expired_ids: list[str] = []
        with self.db.session() as s:
            rows = s.query(SessionRow).filter(SessionRow.status.notin_(list(_TERMINAL))).all()
            for r in rows:
                last = meta.get(r.id, {}).get("last_active_at")
                if last is None and r.started_at is not None:
                    last = r.started_at.timestamp()
                if last is not None and last < cutoff:
                    r.status = "expired"
                    if r.ended_at is None:
                        r.ended_at = datetime.utcnow()
                    expired_ids.append(r.id)
            s.commit()
        if expired_ids:
            stmt = text(
                "UPDATE session_summaries SET expires_at = :n WHERE session_id IN :ids"
            ).bindparams(bindparam("ids", expanding=True))
            with self.db.engine.begin() as conn:
                conn.execute(stmt, {"n": now, "ids": expired_ids})
        return len(expired_ids)

    # ----- 内部 ------------------------------------------------------- #
    def _summaries(self, ids: set[str] | None) -> dict[str, dict[str, Any]]:
        with self.db.engine.begin() as conn:
            rows = conn.execute(text(
                "SELECT session_id, summary, concepts_covered, input_tokens, output_tokens,"
                " last_active_at, expires_at FROM session_summaries"
            )).all()
        out: dict[str, dict[str, Any]] = {}
        for r in rows:
            if ids is not None and r[0] not in ids:
                continue
            out[r[0]] = {
                "summary": r[1],
                "concepts_covered": json.loads(r[2]) if r[2] else [],
                "input_tokens": r[3], "output_tokens": r[4],
                "last_active_at": r[5], "expires_at": r[6],
            }
        return out

    def _upsert(self, session_id: str, user_id: str, subject_id: str, *,
                now: float | None = None, summary: str | None = None,
                concepts_covered: list[str] | None = None,
                add_input: int = 0, add_output: int = 0) -> None:
        now = time.time() if now is None else now
        cc = json.dumps(concepts_covered, ensure_ascii=False) if concepts_covered is not None else None
        with self.db.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO session_summaries
                    (session_id, user_id, subject_id, summary, concepts_covered,
                     input_tokens, output_tokens, last_active_at)
                VALUES (:sid, :uid, :sub, :sum, :cc, :ai, :ao, :now)
                ON CONFLICT(session_id) DO UPDATE SET
                    summary = COALESCE(:sum, session_summaries.summary),
                    concepts_covered = COALESCE(:cc, session_summaries.concepts_covered),
                    input_tokens = session_summaries.input_tokens + :ai,
                    output_tokens = session_summaries.output_tokens + :ao,
                    last_active_at = :now
            """), {"sid": session_id, "uid": user_id, "sub": subject_id, "sum": summary,
                   "cc": cc, "ai": add_input, "ao": add_output, "now": now})
