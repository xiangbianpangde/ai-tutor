"""L2 会话上下文管理 — SessionContext CRUD。

合同来源:
  shared/schemas.py 的 SessionContext / SessionMeta / SessionStats
  specs/tutoring-state-machine.md (顶级状态机)

设计:
- create(): 实例化 SessionContext + 落 SessionRow（context_json 列）
- load(): 反序列化 context_json → SessionContext
- save(): 全量写回 context_json + ended_at（仅 status=completed/expired）

注意 SessionContext.status 的状态机由调用方维护，store 只做持久化。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from shared.errors import TutorError
from shared.models import SessionRow
from shared.schemas import SessionContext, SessionMeta
from shared.storage import RelationalStore

_TERMINAL_STATUSES = {"completed", "expired"}


def _new_session_id() -> str:
    return f"sess-{uuid.uuid4().hex[:12]}"


class SessionStore:
    def __init__(self, db: RelationalStore) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # create
    # ------------------------------------------------------------------ #
    def create(self, *, user_id: str, subject_id: str) -> SessionContext:
        now = datetime.utcnow()
        ctx = SessionContext(
            session_id=_new_session_id(),
            user_id=user_id,
            subject_id=subject_id,
            status="idle",
            meta=SessionMeta(started_at=now),
        )
        with self.db.session() as s:
            s.add(
                SessionRow(
                    id=ctx.session_id,
                    user_id=user_id,
                    subject_id=subject_id,
                    status=ctx.status,
                    context_json=ctx.model_dump(mode="json"),
                    started_at=now,
                )
            )
            s.commit()
        return ctx

    # ------------------------------------------------------------------ #
    # load
    # ------------------------------------------------------------------ #
    def load(self, session_id: str) -> SessionContext:
        with self.db.session() as s:
            row = s.get(SessionRow, session_id)
            if row is None:
                raise TutorError("SESSION_NOT_FOUND", hint=session_id)
            return SessionContext.model_validate(row.context_json)

    # ------------------------------------------------------------------ #
    # save
    # ------------------------------------------------------------------ #
    def save(self, ctx: SessionContext) -> None:
        with self.db.session() as s:
            row = s.get(SessionRow, ctx.session_id)
            if row is None:
                raise TutorError(
                    "SESSION_NOT_FOUND",
                    hint=f"save 前必须 create: {ctx.session_id}",
                )
            row.status = ctx.status
            row.context_json = ctx.model_dump(mode="json")
            if ctx.status in _TERMINAL_STATUSES and row.ended_at is None:
                row.ended_at = datetime.utcnow()
            s.commit()
