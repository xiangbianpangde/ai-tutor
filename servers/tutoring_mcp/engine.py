"""L6 教学决策引擎 — Slice T1 升级版。

新增能力（相对 spine v2）:
- 注入 LLMProvider → LLMScorer 替代 2-gram 启发式判分
- ErrorDiagnoser 在 partial/incorrect 时填 ResponseResult.error_analysis
- 用 ReductionStrategy 完整状态机；next_action 内容随 state 变化
- transition_event(): 显式把外部事件（intro_done/explain_done/practice_done）推进状态机
- strategy 到达 NEXT 状态时自动切到下一个 concept（按拓扑序）
- 全部 concept 走完 → session.status='completed'

后续切片:
- StrategySelector 集成（按 mastery / cognitive_load 动态选 strategy）
- L3 复习节点插入
- 心流追踪 / 认知负荷在线估计
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.errors import TutorError
from shared.llm_client import LLMProvider, StubLLMProvider
from shared.logging_config import get_logger
from shared.models import (
    BKTParamRow,
    ConceptRow as ConceptRowORM,
    KnowledgeGraphRow,
    LearnerProfileRow,
    RelationRow as RelationRowORM,
)
from shared.schemas import (
    Concept,
    ErrorAnalysis,
    FlowLevel,
    FocusState,
    InterruptCheckpoint,
    InterruptResult,
    LearnerProfile,
    MasteryUpdate,
    ResponseResult,
    TeachingAction,
)
from shared.storage import RelationalStore

from .bkt_store import BKTStore
from .error_diagnoser import ErrorDiagnoser
from .flow_regulator import get_regulator
from .flow_signals import compute_flow_signals
from .flow_tracker import next_flow_level
from .gain_loop_monitor import detect_break, repair
from .intent_classifier import IntentClassifier
from .llm_scorer import LLMScorer
from .memory_store import MemoryStore
from .non_judgment_firewall import NonJudgmentFirewall
from .session import SessionStore
from .strategies import Strategy, get_strategy
from .strategies.reduction import ReductionStrategy
from .strategy_selector import select_strategy

_MAX_HISTORY = 20

logger = get_logger("tutoring_mcp.engine")


class TeachingEngine:
    # 掌握度 ≥ 此阈值视为"已掌握"，next_action 跳过教学（与 cold_start 一致）
    MASTERY_SKIP_THRESHOLD = 0.8

    def __init__(
        self,
        *,
        db: RelationalStore,
        sessions: SessionStore,
        llm: LLMProvider | None = None,
    ) -> None:
        self.db = db
        self.sessions = sessions
        self.llm = llm or StubLLMProvider()
        self.bkt = BKTStore(db)
        self.memory = MemoryStore(db)
        self.firewall = NonJudgmentFirewall()
        self.scorer = LLMScorer(llm=self.llm)
        self.diagnoser = ErrorDiagnoser(llm=self.llm)
        self.intent = IntentClassifier(llm=self.llm)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _load_concept(self, concept_id: str) -> Concept:
        with self.db.session() as s:
            row = s.get(ConceptRowORM, concept_id)
            if row is None:
                raise TutorError("KG_NOT_FOUND", hint=f"concept 不存在: {concept_id}")
            return Concept.model_validate(row.full_json)

    # ------------------------------------------------------------------ #
    # 策略装配（P1 #4：动态选策略 + 心流调参 + 无损重建）
    # ------------------------------------------------------------------ #
    def _mastery_for(self, user_id: str, concept_id: str) -> float:
        return self.bkt.load(user_id, concept_id).p_mastery

    def _load_profile(self, user_id: str) -> LearnerProfile:
        with self.db.session() as s:
            row = s.get(LearnerProfileRow, user_id)
            if row is not None and row.profile_json:
                try:
                    return LearnerProfile.model_validate(row.profile_json)
                except Exception:  # noqa: BLE001 — 画像损坏不应阻断教学
                    pass
        return LearnerProfile(user_id=user_id)

    def _mastered_ratio(self, ctx) -> float:
        if not ctx.teaching_plan_id:
            return 0.0
        order = self._topo_order(ctx.teaching_plan_id)
        if not order:
            return 0.0
        mastered = sum(1 for cid in order if self._is_mastered(ctx.user_id, cid))
        return mastered / len(order)

    def _current_flow_level(self, ctx) -> FlowLevel | None:
        """从历史取当前心流级别；历史太短时返回 None（避免会话初始的
        默认 SILENT 误触发降阶法——见 strategy_selector 规则 8）。"""
        if len(ctx.recent_history) < 2:
            return None
        last = ctx.recent_history[-1].get("flow_level")
        if last is None:
            return None
        try:
            return FlowLevel(int(last))
        except (ValueError, TypeError):
            return None

    def _recent_accuracy(self, ctx, window: int = 3) -> float | None:
        turns = [h for h in ctx.recent_history if "correctness" in h][-window:]
        if not turns:
            return None
        score = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}
        return sum(score.get(t["correctness"], 0.0) for t in turns) / len(turns)

    def _select_strategy_name(self, ctx, concept: Concept) -> str:
        try:
            return select_strategy(
                concept=concept,
                mastery=self._mastery_for(ctx.user_id, concept.id),
                cognitive_load=ctx.meta.current_cognitive_load,
                profile=self._load_profile(ctx.user_id),
                mastered_ratio=self._mastered_ratio(ctx),
                flow_level=self._current_flow_level(ctx),
            )
        except Exception as exc:  # noqa: BLE001 — 选择失败兜底 reduction
            logger.warning("strategy_select_failed", error=str(exc))
            return "reduction"

    def _compute_pace(self, ctx) -> dict[str, Any]:
        # 注意：FlowLevel.SILENT == 0 是 falsy，不能用 `or` 兜底，否则 SILENT 会被吞掉
        flow = self._current_flow_level(ctx)
        if flow is None:
            flow = FlowLevel.FLUENT
        pace = get_regulator().recommend_pace(
            flow_level=flow,
            cognitive_load=ctx.meta.current_cognitive_load,
            recent_accuracy=self._recent_accuracy(ctx),
        )
        return pace.to_dict()

    def _persist_strategy(self, ctx, strat: Strategy) -> None:
        ctx.current_strategy = strat.name
        ctx.current_strategy_state = strat.state
        ctx.strategy_internal = strat.export_state()

    def _strategy_terminal(self, ctx) -> bool:
        """当前持久化的策略状态是否为"本概念教学完成"。"""
        name = ctx.current_strategy
        if not name or not ctx.current_strategy_state:
            return False
        try:
            terms = get_strategy(name).TERMINAL_STATES
        except TutorError:
            terms = frozenset({"NEXT"})
        return ctx.current_strategy_state in terms

    def _make_strategy(self, ctx, concept: Concept) -> Strategy:
        """重建或新建当前概念的策略实例。

        - 已在教（current_strategy + 非 IDLE 状态）→ 按 name 重建并 restore_state；
          无快照的老 session：reduction 从 history 复原 attempt_count（CR1 兼容）。
        - 全新进入概念 → strategy_selector 选策略 + flow_regulator 给 pace 参数 + start。
        """
        mastery_map = {concept.id: self._mastery_for(ctx.user_id, concept.id)}
        name = ctx.current_strategy
        state = ctx.current_strategy_state

        if name and state and state != "IDLE":
            try:
                strat = get_strategy(name)
            except TutorError:
                strat, name = ReductionStrategy(), "reduction"
            strat.start(target=concept, mastery_map=mastery_map, params=ctx.strategy_internal or {})
            if ctx.strategy_internal:
                strat.restore_state(ctx.strategy_internal)
            else:
                strat.state = state
                if name == "reduction":
                    count = 0
                    for h in reversed(ctx.recent_history):
                        if h.get("concept_id") != concept.id:
                            break
                        if h.get("correctness") == "correct":
                            break
                        count += 1
                    strat.attempt_count = count
            return strat

        # 全新进入概念
        name = self._select_strategy_name(ctx, concept)
        strat = get_strategy(name)
        strat.start(target=concept, mastery_map=mastery_map, params=self._compute_pace(ctx))
        logger.info("strategy_selected", concept=concept.id, strategy=name)
        return strat

    def _topo_order(self, kg_id: str) -> list[str]:
        """拓扑序复制自 server.py _topological_order（避免 server↔engine 循环依赖）。"""
        with self.db.session() as s:
            nodes = s.query(ConceptRowORM).filter_by(kg_id=kg_id).all()
            if not nodes:
                return []
            edges = (
                s.query(RelationRowORM)
                .filter_by(kg_id=kg_id, type="prerequisite_strong", deprecated=False)
                .all()
            )

        def _key(cid: str) -> tuple[int, ...]:
            try:
                return tuple(int(x) for x in cid.split(":")[1].split("."))
            except (IndexError, ValueError):
                return (10**9,)

        indeg = {n.id: 0 for n in nodes}
        outgoing: dict[str, list[str]] = {n.id: [] for n in nodes}
        for e in edges:
            if e.from_id in indeg and e.to_id in indeg:
                indeg[e.to_id] += 1
                outgoing[e.from_id].append(e.to_id)
        ready = sorted([nid for nid, d in indeg.items() if d == 0], key=_key)
        out: list[str] = []
        while ready:
            cur = ready.pop(0)
            out.append(cur)
            for nxt in outgoing[cur]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)
            ready.sort(key=_key)
        for n in nodes:
            if n.id not in out:
                out.append(n.id)
        return out

    # ------------------------------------------------------------------ #
    # next_action
    # ------------------------------------------------------------------ #
    def _is_mastered(self, user_id: str, concept_id: str) -> bool:
        """冷启动种的先验或学习中达到阈值 → 视为已掌握，可跳过。"""
        try:
            return self.bkt.load(user_id, concept_id).p_mastery >= self.MASTERY_SKIP_THRESHOLD
        except Exception:  # noqa: BLE001 — DB 异常不应阻断教学
            return False

    def _skip_mastered(self, ctx, order: list[str], start: int) -> int:
        """从 start 起向前找第一个未掌握概念的下标（可能 == len(order)）。"""
        pos = start
        while pos < len(order) and self._is_mastered(ctx.user_id, order[pos]):
            pos += 1
        return pos

    @staticmethod
    def _plan_complete_action() -> TeachingAction:
        return TeachingAction(
            type="reflection",
            content="本次学习计划已全部完成。回顾一下你最有收获的点是什么？",
            estimated_duration_min=3,
        )

    def next_action(self, session_id: str) -> TeachingAction:
        ctx = self.sessions.load(session_id)
        order = self._topo_order(ctx.teaching_plan_id) if ctx.teaching_plan_id else []

        # 1) 上一次策略已完成本概念（达到该策略的终止态）→ 前进一格 + 跳过已掌握
        if order and self._strategy_terminal(ctx):
            target = self._skip_mastered(ctx, order, ctx.position_in_plan + 1)
            if target >= len(order):
                ctx.position_in_plan = target
                ctx.status = "completed"
                self.sessions.save(ctx)
                return self._plan_complete_action()
            ctx.current_concept_id = order[target]
            ctx.position_in_plan = target
            ctx.current_strategy = None
            ctx.current_strategy_state = None
            ctx.strategy_internal = {}
            self.sessions.save(ctx)

        # 2) 初次进入某概念（策略尚未起）：若当前概念已掌握，跳到第一个未掌握。
        #    仅当 position_in_plan 与 current_concept_id 一致时才动，避免误伤
        #    "current_concept_id 有效但 position 失同步" 的场景（见 _t1 完成测试）。
        elif (
            order
            and not ctx.current_strategy_state
            and 0 <= ctx.position_in_plan < len(order)
            and order[ctx.position_in_plan] == ctx.current_concept_id
        ):
            target = self._skip_mastered(ctx, order, ctx.position_in_plan)
            if target >= len(order):
                ctx.position_in_plan = target
                ctx.status = "completed"
                self.sessions.save(ctx)
                return self._plan_complete_action()
            if target != ctx.position_in_plan:
                ctx.current_concept_id = order[target]
                ctx.position_in_plan = target
                self.sessions.save(ctx)

        if not ctx.current_concept_id:
            raise TutorError(
                "DEPENDENCY_MISSING",
                hint="current_concept_id 未设置；start_learning_session 应先排好教学路径",
            )
        concept = self._load_concept(ctx.current_concept_id)
        strat = self._make_strategy(ctx, concept)
        action = strat.get_action()

        self._persist_strategy(ctx, strat)
        ctx.focus.primary_concept = concept.id
        ctx.focus.last_action_type = action.type
        self.sessions.save(ctx)
        return action

    # ------------------------------------------------------------------ #
    # transition_event：让 host 推进 intro_done / explain_done / practice_done
    # ------------------------------------------------------------------ #
    def transition_event(
        self, session_id: str, *, event: str, payload: dict[str, Any] | None = None
    ) -> None:
        ctx = self.sessions.load(session_id)
        if not ctx.current_concept_id:
            return
        concept = self._load_concept(ctx.current_concept_id)
        strat = self._make_strategy(ctx, concept)
        strat.transition(event=event, payload=payload or {})
        self._persist_strategy(ctx, strat)
        self.sessions.save(ctx)

    # ------------------------------------------------------------------ #
    # respond
    # ------------------------------------------------------------------ #
    def _build_raw_feedback(
        self, *, correctness: str, concept: Concept, score_evidence: str,
        remediation: str,
    ) -> str:
        if correctness == "correct":
            return f"你抓住了 {concept.names[0]} 的关键。{score_evidence} 继续？"
        if correctness == "partial":
            return f"你关于 {concept.names[0]} 的思考有对的地方。{remediation or '我们再看一个细节。'}"
        return f"我看到你在认真想这个问题。{remediation or '我们换个角度看 ' + concept.names[0] + '。'}"

    def _safe_feedback(self, raw: str, concept: Concept) -> str:
        if self.firewall.scan(raw) is None:
            return raw
        return f"我看到你在认真思考。我们一起再梳理一下 {concept.names[0]}。"

    def respond(self, session_id: str, answer: str) -> ResponseResult:
        ctx = self.sessions.load(session_id)
        if not ctx.current_concept_id:
            raise TutorError("DEPENDENCY_MISSING", hint="current_concept_id 未设置")
        concept = self._load_concept(ctx.current_concept_id)

        # 1) 判分（LLM 优先，启发式 fallback）
        score = self.scorer.score(concept=concept, student_answer=answer)
        correctness = score.correctness

        # 2) BKT 更新
        before = self.bkt.load(ctx.user_id, concept.id).p_mastery
        updated = self.bkt.record_observation(
            user_id=ctx.user_id,
            concept_id=concept.id,
            correct=(correctness == "correct"),
        )
        mastery_update = MasteryUpdate(
            concept_id=concept.id,
            new_mastery=updated.p_mastery,
            change=updated.p_mastery - before,
        )

        # 3) 错误诊断（仅 partial/incorrect）
        diagnosis = self.diagnoser.diagnose(
            concept=concept,
            student_answer=answer,
            correctness=correctness,
            score_evidence=score.evidence,
        )
        error_analysis = None
        if diagnosis is not None:
            error_analysis = ErrorAnalysis(
                type=diagnosis.error_type,
                root_concept=diagnosis.root_concept_id,
                surface_concept=diagnosis.surface_concept_id,
                explanation="; ".join(diagnosis.evidence),
                remediation=diagnosis.remediation_suggestion,
            )

        # 4) 反馈 + 防火墙
        raw = self._build_raw_feedback(
            correctness=correctness,
            concept=concept,
            score_evidence=score.evidence,
            remediation=(diagnosis.remediation_suggestion if diagnosis else ""),
        )
        feedback = self._safe_feedback(raw, concept)

        # 5) 推进 strategy（CHECK→PRACTICE/EXPLAIN/FLAG_DIFFICULT）
        strat = self._make_strategy(ctx, concept)
        strat.transition(event="answered", payload={"correctness": correctness})

        # 6) 更新统计
        ctx.session_stats.total_questions_asked += 1
        n = ctx.session_stats.total_questions_asked
        prev_rate = ctx.session_stats.correct_rate
        hit = 1.0 if correctness == "correct" else 0.0
        ctx.session_stats.correct_rate = (prev_rate * (n - 1) + hit) / n
        if diagnosis is not None:
            key = diagnosis.error_type
            ctx.session_stats.errors_by_type[key] = (
                ctx.session_stats.errors_by_type.get(key, 0) + 1
            )
        self._persist_strategy(ctx, strat)

        # T2: 记录到长期记忆（L3）— 跨会话能拟合遗忘曲线
        try:
            accuracy = 1.0 if correctness == "correct" else (0.5 if correctness == "partial" else 0.0)
            mode = "quick_quiz" if correctness == "correct" else "teach_back"
            err_types = [diagnosis.error_type] if diagnosis is not None else None
            self.memory.record_review(
                user_id=ctx.user_id,
                concept_id=concept.id,
                subject_id=ctx.subject_id,
                accuracy=accuracy,
                review_mode=mode,
                error_types=err_types,
                session_id=session_id,
            )
        except Exception as exc:  # noqa: BLE001 — 记忆失败不影响主教学流程
            logger.warning("respond.memory_record_failed", error=str(exc))

        # T3: 心流追踪 + 增益回路
        new_turn = {
            "answer": answer,
            "correctness": correctness,
            "timestamp": datetime.utcnow().isoformat(),
            "was_self_corrected": False,
            "has_initiative_marker": False,
            "concept_id": concept.id,
        }
        ctx.recent_history = (ctx.recent_history + [new_turn])[-_MAX_HISTORY:]

        # 把 ISO 时间戳还原成 datetime 给信号计算用
        from datetime import datetime as _dt

        sig_history: list[dict] = []
        for h in ctx.recent_history:
            ts = h.get("timestamp")
            if isinstance(ts, str):
                try:
                    ts = _dt.fromisoformat(ts)
                except ValueError:
                    ts = _dt.utcnow()
            sig_history.append({**h, "timestamp": ts})
        signals = compute_flow_signals(history=sig_history)

        # 从 session.current_strategy_state 是否包含 "flow_level" 元信息推 prev_level
        prev_level = FlowLevel.SILENT
        if len(ctx.recent_history) >= 2:
            last_prev = ctx.recent_history[-2].get("flow_level")
            if last_prev is not None:
                prev_level = FlowLevel(int(last_prev))
        new_level = next_flow_level(current_level=prev_level, signals=signals)
        ctx.recent_history[-1]["flow_level"] = int(new_level)

        # 增益回路检测：先看是否有断裂
        # skipped_count 在 handle_interrupt 的 pace_complaint→change_topic 分支累加
        skipped = ctx.session_stats.skipped_count
        brk = detect_break(signals=signals, recent_skipped_count=skipped)
        next_action: TeachingAction | None = None
        if brk is not None:
            next_action = repair(break_type=brk.type)
            logger.info(
                "gain_loop.break_detected",
                break_type=brk.type, session_id=session_id,
            )

        self.sessions.save(ctx)

        logger.info(
            "respond.done",
            session_id=session_id,
            concept=concept.id,
            correctness=correctness,
            mastery=round(updated.p_mastery, 3),
            strategy_state=strat.state,
            flow_level=int(new_level),
            gain_break=(brk.type if brk else None),
        )
        return ResponseResult(
            correctness=correctness,  # type: ignore[arg-type]
            feedback=feedback,
            error_analysis=error_analysis,
            mastery_update=mastery_update,
            next_action=next_action,
        )

    # ------------------------------------------------------------------ #
    # handle_interrupt — T1+
    # ------------------------------------------------------------------ #
    def _save_checkpoint(self, ctx) -> InterruptCheckpoint:
        """保存当前 strategy + concept + focus 到 ctx.interrupt_checkpoint。"""
        cp = InterruptCheckpoint(
            saved_at=datetime.utcnow(),
            current_concept_id=ctx.current_concept_id or "",
            position_in_plan=ctx.position_in_plan,
            strategy=ctx.current_strategy or "reduction",
            strategy_state=ctx.current_strategy_state or "IDLE",
            focus=ctx.focus,
            cognitive_load_at_save=ctx.meta.current_cognitive_load,
        )
        ctx.interrupt_checkpoint = cp
        ctx.meta.interrupt_count += 1
        ctx.status = "interrupted"
        return cp

    def _interrupt_branch_concept_question(
        self, *, concept: Concept | None, question: str,
    ) -> InterruptResult:
        if concept is None:
            return InterruptResult(
                type="context_aware_answer",
                content="我们一起看看你提的这个概念。",
                checkpoint_saved=True,
                resume_prompt="想好后告诉我，我们继续学",
                suggested_action="resume",
            )
        # 用 KG 中已有的定义作答（简化版；下切片可接 LLM 二次润色）
        content = (
            f"关于 {concept.names[0]}：{concept.definition}\n\n"
            f"通俗说：{concept.informal_description or '（可让 LLM 现场补）'}"
        )
        return InterruptResult(
            type="context_aware_answer",
            content=content,
            checkpoint_saved=True,
            resume_prompt=f"看明白后我们继续 {concept.names[0]}",
            suggested_action="resume",
        )

    def _interrupt_branch_prereq_gap(
        self, *, concept: Concept | None, question: str,
    ) -> InterruptResult:
        name = concept.names[0] if concept else "当前概念"
        return InterruptResult(
            type="prereq_tutorial",
            content=(
                f"你提到的好像是 {name} 的前置概念。我们花两三分钟先把它过一下，"
                f"然后再回来。"
            ),
            checkpoint_saved=True,
            resume_prompt=f"补完前置后我们回到 {name}",
            suggested_action="explore_further",
        )

    def _interrupt_branch_pace_complaint(
        self, *, concept: Concept | None, question: str,
    ) -> InterruptResult:
        return InterruptResult(
            type="pace_adjustment",
            content=(
                "好——我们可以快进/跳过这个，"
                "或者换一种讲法。你想走哪种？"
            ),
            checkpoint_saved=True,
            resume_prompt="决定好节奏后告诉我",
            suggested_action="change_topic",
        )

    def _interrupt_branch_cognitive_overload(
        self, *, concept: Concept | None, question: str,
    ) -> InterruptResult:
        return InterruptResult(
            type="pace_adjustment",
            content=(
                "我看到信息量有点大。建议休息 5–10 分钟，"
                "回来时我们用更轻一点的方式继续。"
            ),
            checkpoint_saved=True,
            resume_prompt="休息好了告诉我，我们换更轻的方式重新开始",
            suggested_action="resume",
        )

    def _interrupt_branch_distraction(
        self, *, concept: Concept | None, question: str,
    ) -> InterruptResult:
        name = concept.names[0] if concept else "当前主题"
        return InterruptResult(
            type="redirect",
            content=(
                "这是个有意思的话题。等学完 "
                f"{name} 我们可以再聊。"
            ),
            checkpoint_saved=True,
            resume_prompt=f"我们继续 {name}",
            suggested_action="resume",
        )

    _BRANCHES = {
        "concept_question": "_interrupt_branch_concept_question",
        "prereq_gap": "_interrupt_branch_prereq_gap",
        "pace_complaint": "_interrupt_branch_pace_complaint",
        "cognitive_overload": "_interrupt_branch_cognitive_overload",
        "distraction": "_interrupt_branch_distraction",
    }

    def handle_interrupt(self, session_id: str, question: str) -> InterruptResult:
        """处理学生打断：保存 checkpoint → 意图分类 → 分支响应。"""
        ctx = self.sessions.load(session_id)
        # 取当前 concept 供 LLM 参考
        concept: Concept | None = None
        if ctx.current_concept_id:
            try:
                concept = self._load_concept(ctx.current_concept_id)
            except TutorError:
                concept = None

        # 1) 保存 checkpoint
        self._save_checkpoint(ctx)

        # 2) 分类意图
        intent_result = self.intent.classify(
            question=question,
            current_concept_name=concept.names[0] if concept else None,
        )

        # 3) 走分支
        handler_name = self._BRANCHES[intent_result.intent]
        result: InterruptResult = getattr(self, handler_name)(
            concept=concept, question=question,
        )

        # 4) 反馈过防火墙
        if self.firewall.scan(result.content) is not None:
            result = InterruptResult(
                type=result.type,
                content=f"我看到你的想法。我们一起再梳理一下。",
                checkpoint_saved=True,
                resume_prompt=result.resume_prompt,
                suggested_action=result.suggested_action,
            )

        # 4.5) 累加 avoidance 计数器（用于 detect_break 的 avoidance_pattern）
        if result.suggested_action == "change_topic":
            ctx.session_stats.skipped_count += 1

        # 5) 保存
        self.sessions.save(ctx)

        logger.info(
            "interrupt.done",
            session_id=session_id,
            intent=intent_result.intent,
            confidence=round(intent_result.confidence, 2),
            type=result.type,
        )
        return result

    # ------------------------------------------------------------------ #
    # handle_checkpoint — T1+
    # ------------------------------------------------------------------ #
    def _llm_self_score(self, content: str) -> tuple[float, float]:
        """让 LLM 把学生自评文本映射到 0-1。失败 → 启发式。"""
        import json as _json

        prompt = f"""学生在阶段检查点说了一段自评：

"{content}"

把它映射到 0-1 的"我觉得自己学得多好"分数。
0 = 完全不懂；1 = 完全掌握。

只输出 JSON：{{"self_score": 0.0~1.0, "confidence": 0.0~1.0}}
"""
        try:
            resp = self.llm.chat(
                messages=[
                    {"role": "system", "content": "你是元认知评估器，把学生自评文字映射到 0-1。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1, max_tokens=128,
            )
            text = resp.content.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            data = _json.loads(text)
            if isinstance(data, dict):
                s = float(data.get("self_score", 0.5))
                c = float(data.get("confidence", 0.5))
                return max(0.0, min(1.0, s)), max(0.0, min(1.0, c))
        except (TutorError, ValueError, _json.JSONDecodeError):
            pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("checkpoint.llm_exception", error=str(exc))
        return self._heuristic_self_score(content)

    @staticmethod
    def _heuristic_self_score(content: str) -> tuple[float, float]:
        text = (content or "").lower()
        if not text.strip():
            return 0.5, 0.2
        # 注意：先匹"全都懂/都会了"这种极正面，再匹一般"会了"避免冲突
        for k in ("全都懂", "都会了", "全会了", "全掌握", "都掌握", "百分百"):
            if k in text:
                return 0.9, 0.5
        for k in ("差不多", "基本", "大部分", "应该可以"):
            if k in text:
                return 0.7, 0.5
        for k in ("还行", "一般", "马马虎虎", "勉强"):
            if k in text:
                return 0.5, 0.5
        for k in ("不太懂", "有点懵", "不熟"):
            if k in text:
                return 0.35, 0.5
        for k in ("不会", "完全不懂", "没听懂", "不知道"):
            if k in text:
                return 0.15, 0.5
        return 0.5, 0.3

    def handle_checkpoint(
        self,
        session_id: str,
        *,
        kind: str = "self_summary",
        content: str | None = None,
    ) -> dict[str, Any]:
        """阶段检查点：学生自评 vs BKT 实际 → 更新元认知。"""
        ctx = self.sessions.load(session_id)

        # 1) 收集涉及的 concepts
        covered_ids = list(ctx.session_stats.concepts_covered or [])
        with self.db.session() as s:
            if covered_ids:
                bkt_rows = (
                    s.query(BKTParamRow)
                    .filter(
                        BKTParamRow.user_id == ctx.user_id,
                        BKTParamRow.concept_id.in_(covered_ids),
                    )
                    .all()
                )
            else:
                bkt_rows = (
                    s.query(BKTParamRow)
                    .filter_by(user_id=ctx.user_id)
                    .all()
                )

        mastery_map = {r.concept_id: round(r.p_mastery, 3) for r in bkt_rows}
        actual_mastery = (
            sum(mastery_map.values()) / len(mastery_map) if mastery_map else 0.5
        )

        # 2) 解析自评
        self_score, _conf = self._llm_self_score(content or "")
        accuracy = max(0.0, min(1.0, 1.0 - abs(self_score - actual_mastery)))

        # 3) 更新 LearnerProfile.metacognitive
        with self.db.session() as s:
            row = s.get(LearnerProfileRow, ctx.user_id)
            if row is None:
                profile = LearnerProfile(user_id=ctx.user_id)
                row = LearnerProfileRow(
                    user_id=ctx.user_id,
                    profile_json=profile.model_dump(mode="json"),
                )
                s.add(row)
            profile_data = dict(row.profile_json or {})
            meta = dict(profile_data.get("metacognitive") or {})
            prev = float(meta.get("self_assessment_accuracy", 0.6))
            new_val = 0.7 * prev + 0.3 * accuracy
            meta["self_assessment_accuracy"] = round(new_val, 3)
            profile_data["metacognitive"] = meta
            row.profile_json = profile_data
            row.last_updated = datetime.utcnow()
            s.commit()

        # 4) 建议
        suggestions: list[str] = []
        gap = self_score - actual_mastery
        if gap > 0.15:
            suggestions.append(
                f"你的自评（{self_score:.0%}）高于实际（{actual_mastery:.0%}）；"
                f"建议挑一个最弱概念再讲一遍。"
            )
        elif gap < -0.15:
            suggestions.append(
                f"实际掌握（{actual_mastery:.0%}）比你想的（{self_score:.0%}）好。"
                f"信心可以更足。"
            )
        else:
            suggestions.append(
                f"自评与实际接近（差 {abs(gap):.0%}），元认知校准良好。"
            )

        ctx.meta.checkpoint_count += 1
        self.sessions.save(ctx)

        logger.info(
            "checkpoint.done",
            session_id=session_id, kind=kind,
            self_score=round(self_score, 2),
            actual=round(actual_mastery, 2),
            accuracy=round(accuracy, 2),
        )
        return {
            "self_assessment_accuracy": round(accuracy, 3),
            "self_score": round(self_score, 3),
            "actual_mastery_avg": round(actual_mastery, 3),
            "current_mastery_map": mastery_map,
            "cognitive_load": round(ctx.meta.current_cognitive_load, 3),
            "suggestions": suggestions,
        }
