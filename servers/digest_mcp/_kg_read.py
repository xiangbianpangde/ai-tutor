"""digest generator 共享：读 KG 概念并按章节号自然排序。

D2 的 4 个新 generator（simulation/multi_agent/slides/audio）都用它，
统一 KG_NOT_FOUND 行为和章节排序。现有 3 个 generator 保持各自实现不动。
"""
from __future__ import annotations

from shared.errors import TutorError
from shared.models import ConceptRow, KnowledgeGraphRow
from shared.storage import RelationalStore


def chapter_key(concept_id: str) -> tuple[int, ...]:
    """从 concept_id 'subj:1.2.3:slug' 解析章节号做自然排序键。"""
    try:
        chapter = concept_id.split(":")[1]
        return tuple(int(x) for x in chapter.split("."))
    except (IndexError, ValueError):
        return (10**9,)


def chapter_depth(concept_id: str) -> int:
    try:
        return concept_id.split(":")[1].count(".") + 1
    except IndexError:
        return 1


def load_sorted_concepts(
    db: RelationalStore, kg_id: str,
) -> tuple[KnowledgeGraphRow, list[ConceptRow]]:
    """返回 (KG 行, 按章节排序的 concept 行列表)。KG 不存在 → KG_NOT_FOUND。"""
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)
        rows = s.query(ConceptRow).filter_by(kg_id=kg_id).all()
        # detach 前触发属性加载（避免 session 关闭后 DetachedInstanceError）
        for r in rows:
            _ = (r.id, r.name_primary, r.definition, r.informal_description,
                 r.confidence, r.full_json)
        s.expunge_all()
    rows.sort(key=lambda r: chapter_key(r.id))
    return kg, rows
