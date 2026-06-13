"""多 Session 学习计划 (P0 #3：跨天调度) — 核心逻辑 + 持久化。

为什么需要：原来每次 start_learning_session 都新建会话从头排路径，Session 结束后
没有"下次从哪继续"的结构。BKT 掌握度虽跨会话持久化（已掌握的会被引擎跳过），但
缺少：(1) 显式的阶段化计划；(2)"我学到哪了 / 明天从哪继续"的进度查询。

做法：
- build_plan：把 KG 拓扑序按【顶层章节】切成若干 Phase（每章一个阶段，含时长估计）。
- compute_progress：结合 BKT 掌握度算每个 Phase 的完成度 + 当前 Phase + 下一个该学的概念。
- LearningPlanStore：把计划持久化到 learning_plans 表（按 user+subject 唯一）。

计划本身只存概念 id 的分组；掌握度永远实时从 BKT 读，所以计划不会"过期"。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from shared.models import LearningPlanRow
from shared.schemas import (
    Concept,
    LearningPlan,
    LearningProgress,
    PhasePlan,
    PhaseProgress,
)
from shared.storage import RelationalStore

from .cold_start import MASTERY_SKIP_THRESHOLD

# 掌握度 ≥ 此阈值视为"已掌握"（与 cold_start / engine 一致）
_MASTERED = MASTERY_SKIP_THRESHOLD


def _chapter_key(concept_id: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in concept_id.split(":")[1].split("."))
    except (IndexError, ValueError):
        return (10**9,)


def _top_chapter(concept_id: str) -> int:
    return _chapter_key(concept_id)[0]


# --------------------------------------------------------------------------- #
# build_plan
# --------------------------------------------------------------------------- #


def build_plan(
    *,
    user_id: str,
    subject_id: str,
    kg_id: str,
    ordered_concepts: list[Concept],
) -> LearningPlan:
    """把拓扑序概念按顶层章节切成 Phase。

    按顶层章节归组（每章一个 Phase），章节顺序按首次出现。拓扑序不保证同章概念相邻
    （跨章前置会让章节交错），所以用 dict 归组而非"连续段"，避免同一章被拆成多个 Phase。
    计划仅用于进度展示——真正的教学顺序由 engine 的拓扑序走，不受此分组影响。
    Phase 标题取该章的"章节根概念"（id 形如 `subject:N:slug`）名，否则用组内首概念名。
    """
    total_min = 0
    # 顶层章节号 → 该章概念（保持拓扑序内的相对顺序）；dict 保持首次出现顺序
    groups: dict[int, list[Concept]] = {}
    for c in ordered_concepts:
        total_min += c.difficulty.typical_learning_time_min
        groups.setdefault(_top_chapter(c.id), []).append(c)

    phases: list[PhasePlan] = []
    for phase_no, (_ch, group) in enumerate(groups.items(), start=1):
        root = next((c for c in group if len(_chapter_key(c.id)) == 1), None)
        head = root or group[0]
        title = head.names[0] if head.names else f"第 {phase_no} 阶段"
        minutes = sum(c.difficulty.typical_learning_time_min for c in group)
        phases.append(
            PhasePlan(
                phase=phase_no,
                title=title,
                concept_ids=[c.id for c in group],
                estimated_hours=round(minutes / 60.0, 2),
            )
        )

    return LearningPlan(
        user_id=user_id,
        subject_id=subject_id,
        kg_id=kg_id,
        phases=phases,
        total_concepts=len(ordered_concepts),
        estimated_hours=round(total_min / 60.0, 2),
        created_at=datetime.utcnow(),
    )


# --------------------------------------------------------------------------- #
# compute_progress
# --------------------------------------------------------------------------- #


def compute_progress(
    *,
    plan: LearningPlan,
    mastery_of: Callable[[str], float],
    name_of: dict[str, str] | Callable[[str], str],
) -> LearningProgress:
    """结合实时掌握度算跨 Session 进度。"""

    def _name(cid: str) -> str:
        if callable(name_of):
            return name_of(cid)
        return name_of.get(cid, cid)

    phase_reports: list[PhaseProgress] = []
    total = 0
    total_mastered = 0
    next_concept_id: str | None = None
    current_phase: int | None = None

    for ph in plan.phases:
        n = len(ph.concept_ids)
        m = sum(1 for cid in ph.concept_ids if mastery_of(cid) >= _MASTERED)
        total += n
        total_mastered += m
        done = n > 0 and m == n
        # 第一个未完成的 Phase 标 in_progress，其余未完成标 pending
        if done:
            status = "done"
        elif current_phase is None:
            status = "in_progress"
            current_phase = ph.phase
        else:
            status = "pending"
        phase_reports.append(
            PhaseProgress(
                phase=ph.phase,
                title=ph.title,
                concepts_total=n,
                concepts_mastered=m,
                mastered_ratio=round(m / n, 3) if n else 0.0,
                status=status,
            )
        )
        # 下一个该学的概念 = 全局第一个未掌握
        if next_concept_id is None:
            for cid in ph.concept_ids:
                if mastery_of(cid) < _MASTERED:
                    next_concept_id = cid
                    break

    completed = total > 0 and total_mastered == total
    current_title = None
    if current_phase is not None:
        current_title = next((p.title for p in plan.phases if p.phase == current_phase), None)

    return LearningProgress(
        user_id=plan.user_id,
        subject_id=plan.subject_id,
        overall_mastery_ratio=round(total_mastered / total, 3) if total else 0.0,
        concepts_total=total,
        concepts_mastered=total_mastered,
        current_phase=current_phase,
        current_phase_title=current_title,
        next_concept_id=next_concept_id,
        next_concept_name=_name(next_concept_id) if next_concept_id else None,
        phases=phase_reports,
        completed=completed,
    )


# --------------------------------------------------------------------------- #
# 持久化
# --------------------------------------------------------------------------- #


class LearningPlanStore:
    def __init__(self, db: RelationalStore) -> None:
        self.db = db

    def load(self, user_id: str, subject_id: str) -> LearningPlan | None:
        with self.db.session() as s:
            row = s.get(LearningPlanRow, (user_id, subject_id))
            if row is None:
                return None
            return LearningPlan.model_validate(row.plan_json)

    def save(self, plan: LearningPlan) -> None:
        with self.db.session() as s:
            row = s.get(LearningPlanRow, (plan.user_id, plan.subject_id))
            if row is None:
                row = LearningPlanRow(
                    user_id=plan.user_id,
                    subject_id=plan.subject_id,
                    kg_id=plan.kg_id,
                    plan_json=plan.model_dump(mode="json"),
                )
                s.add(row)
            else:
                row.kg_id = plan.kg_id
                row.plan_json = plan.model_dump(mode="json")
                row.last_updated = datetime.utcnow()
            s.commit()
