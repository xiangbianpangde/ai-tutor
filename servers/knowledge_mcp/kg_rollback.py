"""rollback_kg — 把 subject.kg_id 回退到 parent 链上的某一版本。

设计:
- target 必须是当前 kg 的祖先（沿 parent_kg_id 向上追溯能找到 target）
- 不删除任何 KG 行（保留审计）
- 仅修改 Subject.kg_id
- BKT 因 base_id 设计自动跟随：concept 在不同 KG 版本下 base_id 一致
  → mem record 用 base_id 已经能跨版本继承
"""
from __future__ import annotations

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import KnowledgeGraphRow, Subject
from shared.storage import RelationalStore

logger = get_logger("knowledge_mcp.kg_rollback")


def _walk_parents(db: RelationalStore, kg_id: str, max_depth: int = 50) -> list[str]:
    """向上追溯 parent_kg_id 链；返回 [kg_id, parent, grandparent, ...]。"""
    chain: list[str] = []
    seen: set[str] = set()
    cur = kg_id
    while cur and cur not in seen and len(chain) < max_depth:
        chain.append(cur)
        seen.add(cur)
        with db.session() as s:
            row = s.get(KnowledgeGraphRow, cur)
            if row is None or row.parent_kg_id is None:
                break
            cur = row.parent_kg_id
    return chain


def rollback_kg(
    *,
    db: RelationalStore,
    subject_id: str,
    target_kg_id: str,
) -> dict:
    """把 subject 的当前 kg_id 改回 target_kg_id（必须是祖先）。"""
    with db.session() as s:
        subj = s.get(Subject, subject_id)
        if subj is None:
            raise TutorError("SUBJECT_NOT_FOUND", hint=subject_id)
        cur_kg = subj.kg_id
        target = s.get(KnowledgeGraphRow, target_kg_id)
        if target is None:
            raise TutorError("KG_NOT_FOUND", hint=target_kg_id)
        if cur_kg is None:
            # subject 还没绑过 kg
            raise TutorError(
                "INVALID_KG_EDIT_ACTION",
                hint=f"subject={subject_id} 当前没有 kg_id，无法回退",
            )

    if cur_kg == target_kg_id:
        logger.info("rollback.noop", subject_id=subject_id, kg_id=cur_kg)
        return {"subject_id": subject_id, "from_kg_id": cur_kg, "to_kg_id": cur_kg, "changed": False}

    ancestors = _walk_parents(db, cur_kg)
    if target_kg_id not in ancestors:
        raise TutorError(
            "INVALID_KG_EDIT_ACTION",
            hint=(
                f"target_kg_id={target_kg_id} 不是 {cur_kg} 的祖先；"
                f"沿 parent 链可达: {ancestors}"
            ),
        )

    with db.session() as s:
        subj = s.get(Subject, subject_id)
        subj.kg_id = target_kg_id
        s.commit()

    logger.info(
        "rollback.done",
        subject_id=subject_id, from_kg_id=cur_kg, to_kg_id=target_kg_id,
    )
    return {
        "subject_id": subject_id,
        "from_kg_id": cur_kg,
        "to_kg_id": target_kg_id,
        "changed": True,
    }
