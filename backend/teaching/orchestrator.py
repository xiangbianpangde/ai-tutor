"""backend.teaching.orchestrator —— 教学编排（M-009，对应 v2 #10 部分）。

把 v1 `TeachingEngine`（L6 教学决策：策略状态机 / BKT / 心流 / 判分 / 错误诊断）包成
REST 可驱动的编排服务：start / next_action / respond / advance / transition。

务实接线（对齐 C2/C3 哲学）：
- **engine 工厂可注入**——测试传 stub，免建真 KG / 真 LLM / 碰演示资产。
- 经 **M-004 SessionManager** 共享会话存储（新建会话自动进 list_sessions）+ 摘要刷新。
- 经 **M-006 EventBus** 发教学事件（session_started / responded / action）——#7 实时推送、
  #11 监控各自 subscribe，互不耦合。

只编排不重写决策：拓扑序选概念 / 判分 / 策略推进全在 v1 engine 内，本层只搬运 + 接线。
"""
from __future__ import annotations

from typing import Any

from shared.errors import TutorError
from shared.logging_config import get_logger

logger = get_logger("backend.teaching.orchestrator")


class TeachingOrchestrator:
    """教学会话编排：驱动 v1 TeachingEngine 跑 start→action→respond 循环。"""

    def __init__(
        self,
        store: Any,
        *,
        llm: Any = None,
        sessions: Any = None,  # M-004 SessionManager（可选）
        events: Any = None,  # M-006 EventBus（可选）
        engine_factory: Any = None,
    ) -> None:
        self._store = store
        self._llm = llm
        self._sessions = sessions
        self._events = events
        self._engine_factory = engine_factory
        self._engine: Any = None

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    def _engine_(self) -> Any:
        """构建并缓存 TeachingEngine（持 db/sessions/llm，跨请求可复用）。"""
        if self._engine is None:
            if self._engine_factory is not None:
                self._engine = self._engine_factory()
            else:
                from servers.tutoring_mcp.engine import TeachingEngine
                from servers.tutoring_mcp.session import SessionStore

                # LLM 选择：注入的 > MiniMax（配了 key 的真 LLM）> 本地判分器（基础模式）。
                # 无真 LLM 时若仍用 FIX-L 回退启发式（永不授 correct）→ CHECK 死循环、科目学不完。
                llm = self._llm
                if llm is None:
                    from .minimax_provider import MiniMaxProvider

                    if MiniMaxProvider.available():
                        try:
                            llm = MiniMaxProvider()
                        except Exception:
                            llm = None
                    if llm is None:
                        from .local_judge import LocalJudgeProvider

                        llm = LocalJudgeProvider()
                self._engine = TeachingEngine(
                    db=self._store, sessions=SessionStore(self._store), llm=llm
                )
        return self._engine

    def _session_store(self) -> Any:
        """共享 M-004 的 SessionStore（让新建会话进 list_sessions）；无 M-004 则自建。"""
        if self._sessions is not None:
            return self._sessions.store
        from servers.tutoring_mcp.session import SessionStore

        return SessionStore(self._store)

    def _resolve_kg_id(self, subject_id: str, kg_id: str | None) -> str:
        if kg_id:
            return kg_id
        from shared.models import Subject

        with self._store.session() as s:
            subj = s.get(Subject, subject_id)
            if subj is None:
                raise TutorError("SUBJECT_NOT_FOUND", hint=subject_id)
            if not subj.kg_id:
                raise TutorError("KG_NOT_BUILT", hint=f"subject={subject_id} 未关联 KG")
            return subj.kg_id

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._events is None:
            return
        try:
            from ..middleware.event_bus import Event

            await self._events.publish(Event(type=event_type, payload=payload))
        except Exception:
            pass

    def _refresh_summary(self, session_id: str) -> None:
        if self._sessions is None:
            return
        try:
            self._sessions.touch(session_id)
            self._sessions.summarize(session_id)
        except Exception:
            pass

    @staticmethod
    def _dump(model: Any) -> Any:
        """Pydantic → JSON 安全 dict；非 Pydantic 原样返回。"""
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")
        return model

    # 问答态：这些 action.type 需要学生作答（respond）；其余是展示态（advance 继续）。
    _QUESTION_ACTIONS = frozenset({"ask_question", "give_exercise"})

    def _session_meta(self, session_id: str) -> dict[str, Any]:
        """会话进度元信息：是否学完 + 当前位置，供 UI 决定"继续/作答/已学完"。"""
        try:
            ctx = self._session_store().load(session_id)
            return {
                "completed": ctx.status == "completed",
                "status": ctx.status,
                "position": ctx.position_in_plan,
            }
        except Exception:
            return {"completed": False, "status": "active", "position": 0}

    def _annotate(self, session_id: str, action: Any) -> dict[str, Any]:
        """把动作 + 是否需作答 + 会话进度打包给 UI。"""
        a = self._dump(action)
        atype = a.get("type") if isinstance(a, dict) else getattr(action, "type", None)
        return {
            "action": a,
            "interactive": atype in self._QUESTION_ACTIONS,
            **self._session_meta(session_id),
        }

    # ------------------------------------------------------------------ #
    # 编排动作
    # ------------------------------------------------------------------ #
    async def start(self, *, user_id: str, subject_id: str, kg_id: str | None = None) -> dict[str, Any]:
        """开启新学习会话：定位首个概念 → 建会话 → 给首个教学动作。"""
        kg_id = self._resolve_kg_id(subject_id, kg_id)
        engine = self._engine_()
        order = engine._topo_order(kg_id)
        if not order:
            raise TutorError("KG_NOT_BUILT", hint=f"KG {kg_id} 无概念")

        store = self._session_store()
        ctx = store.create(user_id=user_id, subject_id=subject_id)
        ctx.current_concept_id = order[0]
        ctx.position_in_plan = 0
        ctx.status = "active"
        ctx.teaching_plan_id = kg_id
        store.save(ctx)

        first_action = engine.next_action(ctx.session_id)
        logger.info("teaching.session_started", session_id=ctx.session_id,
                    subject_id=subject_id, total_concepts=len(order))
        await self._emit("teaching.session_started", {
            "session_id": ctx.session_id, "subject_id": subject_id,
            "total_concepts": len(order),
        })
        self._refresh_summary(ctx.session_id)
        return {
            "session_id": ctx.session_id,
            "kg_id": kg_id,
            "total_concepts": len(order),
            "current_action": self._dump(first_action),
            **self._annotate(ctx.session_id, first_action),
        }

    async def next_action(self, session_id: str) -> dict[str, Any]:
        """要下一个教学动作（拓扑序推进 + 跳过已掌握，全在 engine 内）。"""
        action = self._engine_().next_action(session_id)
        await self._emit("teaching.action", {
            "session_id": session_id, "type": getattr(action, "type", None),
        })
        return {"session_id": session_id, **self._annotate(session_id, action)}

    async def respond(self, session_id: str, answer: str) -> dict[str, Any]:
        """学生作答 → 判分/诊断/反馈/策略推进 → 取下一个动作（含是否学完）。"""
        result = self._engine_().respond(session_id, answer)
        await self._emit("teaching.responded", {
            "session_id": session_id,
            "correctness": getattr(result, "correctness", None),
        })
        self._refresh_summary(session_id)
        nxt = self._engine_().next_action(session_id)  # 作答后推进到下一个教学动作
        return {
            "session_id": session_id,
            "result": self._dump(result),
            "next": self._annotate(session_id, nxt),
        }

    async def advance(self, session_id: str) -> dict[str, Any]:
        """讲解/展示步骤后"继续"：推进纯展示态到下一步（问答步骤应改用 respond）。"""
        action = self._engine_().advance(session_id)
        return {"session_id": session_id, **self._annotate(session_id, action)}

    async def transition(
        self, session_id: str, *, event: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """显式把外部事件（intro_done/explain_done/practice_done）推进策略状态机。"""
        self._engine_().transition_event(session_id, event=event, payload=payload or {})
        return {"session_id": session_id, "event": event, "ok": True}
