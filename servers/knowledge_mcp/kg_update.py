"""update_kg — 应用 KgEditAction 列表到 KG（in-place + audit trail）。

设计说明:
- spec 原文要求"新 KG 版本"，本切片简化为 in-place（避免 ConceptRow PK 重构）。
  审计信息追加到 KnowledgeGraphRow.manifest_json['update_history']。
- 完整版本树（KG 复制 + 回滚）留到后续切片。

6 种 op:
- edit_definition / add_edge / remove_edge / delete_concept / merge_concepts / approve_all
"""
from __future__ import annotations

import copy
from datetime import datetime

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import (
    ConceptRow,
    KnowledgeGraphRow,
    RelationRow,
)
from shared.schemas import (
    Concept,
    KgEditAction,
    KgUpdateFailure,
    KgUpdateResult,
    QualityReport,
)
from shared.schemas import (
    Relation as RelationSchema,
)
from shared.storage import RelationalStore

from .kg_enrich_adapter import _compute_quality

logger = get_logger("knowledge_mcp.kg_update")


def _apply_one(session, kg_id: str, action: KgEditAction) -> None:
    """成功 → 静默返回；失败 → raise ValueError(reason)。事务由外层管理。"""
    op = action.op

    if op == "approve_all":
        return  # no-op，仅记审计

    if op == "edit_definition":
        if not action.concept_id or not action.new_definition:
            raise ValueError("edit_definition 需要 concept_id 和 new_definition")
        row = session.get(ConceptRow, action.concept_id)
        if row is None or row.kg_id != kg_id:
            raise ValueError(f"concept_id {action.concept_id} 不在 kg {kg_id} 中")
        row.definition = action.new_definition
        # 同步进 full_json
        full = dict(row.full_json or {})
        full["definition"] = action.new_definition
        row.full_json = full
        return

    if op == "add_edge":
        if not action.edge:
            raise ValueError("add_edge 需要 edge 字段")
        e = action.edge
        # 防自环（Relation 模型已做，但额外校验避免数据不一致）
        if e.from_id == e.to_id:
            raise ValueError("不允许自环边")
        # 检查两端 concept 存在
        for cid in (e.from_id, e.to_id):
            cr = session.get(ConceptRow, cid)
            if cr is None or cr.kg_id != kg_id:
                raise ValueError(f"concept {cid} 不在 kg {kg_id}")
        session.add(
            RelationRow(
                kg_id=kg_id,
                from_id=e.from_id,
                to_id=e.to_id,
                type=e.type,
                weight=e.weight,
                explanation=e.explanation,
                confidence=e.confidence,
                deprecated=False,
            )
        )
        return

    if op == "remove_edge":
        if not action.edge:
            raise ValueError("remove_edge 需要 edge 字段")
        e = action.edge
        targets = (
            session.query(RelationRow)
            .filter_by(kg_id=kg_id, from_id=e.from_id, to_id=e.to_id, type=e.type)
            .all()
        )
        if not targets:
            raise ValueError("未找到匹配的边")
        for t in targets:
            session.delete(t)
        return

    if op == "delete_concept":
        if not action.concept_id:
            raise ValueError("delete_concept 需要 concept_id")
        row = session.get(ConceptRow, action.concept_id)
        if row is None or row.kg_id != kg_id:
            raise ValueError(f"concept_id {action.concept_id} 不在 kg {kg_id}")
        # 删它的所有边
        edges = (
            session.query(RelationRow)
            .filter_by(kg_id=kg_id)
            .filter(
                (RelationRow.from_id == action.concept_id)
                | (RelationRow.to_id == action.concept_id)
            )
            .all()
        )
        for e in edges:
            session.delete(e)
        session.delete(row)
        return

    if op == "merge_concepts":
        src = action.concept_id
        tgt = action.merge_target_id
        if not src or not tgt:
            raise ValueError("merge_concepts 需要 concept_id 和 merge_target_id")
        if src == tgt:
            raise ValueError("不能合并到自身")
        src_row = session.get(ConceptRow, src)
        tgt_row = session.get(ConceptRow, tgt)
        if src_row is None or src_row.kg_id != kg_id:
            raise ValueError(f"src {src} 不在 kg {kg_id}")
        if tgt_row is None or tgt_row.kg_id != kg_id:
            raise ValueError(f"target {tgt} 不在 kg {kg_id}")
        # 重定向 src 的所有边到 tgt（同时去除会变成自环的边）
        edges = (
            session.query(RelationRow)
            .filter_by(kg_id=kg_id)
            .filter(
                (RelationRow.from_id == src) | (RelationRow.to_id == src)
            )
            .all()
        )
        for e in edges:
            new_from = tgt if e.from_id == src else e.from_id
            new_to = tgt if e.to_id == src else e.to_id
            if new_from == new_to:
                session.delete(e)  # 重定向后自环 → 删
            else:
                e.from_id = new_from
                e.to_id = new_to
        # 合并 names（保持 tgt 在前 + 去重，保序）
        # BUG.6 fix: 同时同步 full_json["names"] 和 name_primary 保持一致；
        # 否则下游 Concept.model_validate(full_json) 看不到 src 的别名。
        tgt_names = list(tgt_row.names_json or [])
        src_names = list(src_row.names_json or [])
        merged: list[str] = []
        for n in tgt_names + src_names:
            if n and n not in merged:
                merged.append(n)
        tgt_row.names_json = merged
        # name_primary：若原本是 src 的 primary 才换；否则保留 tgt 的
        if merged and not tgt_row.name_primary:
            tgt_row.name_primary = merged[0]
        # 同步 full_json
        full = dict(tgt_row.full_json or {})
        full["names"] = merged
        if tgt_row.name_primary:
            full["names"] = [tgt_row.name_primary] + [n for n in merged if n != tgt_row.name_primary]
        tgt_row.full_json = full
        session.delete(src_row)
        return

    raise ValueError(f"未知 op: {op}")


_VALID_MODES = ("in_place", "versioned")


def _next_version_kg_id(db, parent_kg_id: str) -> str:
    """生成新 KG 版本 id：`{parent_kg_id}-v{N}`，N 取已有子版本数 + 2。"""
    with db.session() as s:
        existing = (
            s.query(KnowledgeGraphRow)
            .filter_by(parent_kg_id=parent_kg_id)
            .count()
        )
    return f"{parent_kg_id}-v{existing + 2}"


def _versioned_concept_id(base_id: str, new_kg_id: str) -> str:
    """给 concept.id 加版本后缀避免全表 PK 冲突。"""
    # 用 kg_id 末段作短后缀（防超长）
    short = new_kg_id.split("-")[-1]
    return f"{base_id}@{short}"


def _clone_kg(
    db,
    parent_kg_id: str,
    new_kg_id: str,
) -> dict[str, str]:
    """把父 KG 完整复制到 new_kg_id；返回 {old_concept_id: new_concept_id} 映射。"""
    with db.session() as s:
        parent = s.get(KnowledgeGraphRow, parent_kg_id)
        if parent is None:
            raise TutorError("KG_NOT_FOUND", hint=parent_kg_id)

        # 复制 KG 行
        s.add(
            KnowledgeGraphRow(
                kg_id=new_kg_id,
                subject_id=parent.subject_id,
                corpus_id=parent.corpus_id,
                version=f"{parent.version}-edit",
                node_count=0,  # 后面更新
                edge_count=0,
                quality_json=parent.quality_json,
                manifest_json={
                    **(parent.manifest_json or {}),
                    "parent_kg_id": parent_kg_id,
                    "cloned_at": datetime.utcnow().isoformat() + "Z",
                },
                parent_kg_id=parent_kg_id,
            )
        )

        # 复制 ConceptRow（id 加后缀，base_id 保留）
        old_rows = s.query(ConceptRow).filter_by(kg_id=parent_kg_id).all()
        id_map: dict[str, str] = {}
        for old in old_rows:
            new_id = _versioned_concept_id(old.base_id, new_kg_id)
            id_map[old.id] = new_id
            # full_json 保留 base id（Concept schema pattern 不允许 @）；
            # versioned KG 的 isolated 检测在 update_kg 末尾基于 ORM id 重算覆盖。
            new_full = dict(old.full_json or {})
            s.add(
                ConceptRow(
                    id=new_id,
                    kg_id=new_kg_id,
                    base_id=old.base_id,
                    name_primary=old.name_primary,
                    names_json=list(old.names_json),
                    category=old.category,
                    definition=old.definition,
                    informal_description=old.informal_description,
                    abstract_level=old.abstract_level,
                    bloom_level=old.bloom_level,
                    domain=old.domain,
                    cognitive_load_estimate=old.cognitive_load_estimate,
                    typical_learning_time_min=old.typical_learning_time_min,
                    prereq_count=old.prereq_count,
                    prereq_max_depth=old.prereq_max_depth,
                    formula_density=old.formula_density,
                    coupling=old.coupling,
                    confidence=old.confidence,
                    full_json=new_full,
                )
            )

        # 复制 RelationRow（端点用 id_map 重映射）
        old_edges = s.query(RelationRow).filter_by(kg_id=parent_kg_id).all()
        for e in old_edges:
            from_new = id_map.get(e.from_id)
            to_new = id_map.get(e.to_id)
            if from_new is None or to_new is None:
                continue
            s.add(
                RelationRow(
                    kg_id=new_kg_id,
                    from_id=from_new,
                    to_id=to_new,
                    type=e.type,
                    weight=e.weight,
                    explanation=e.explanation,
                    confidence=e.confidence,
                    deprecated=bool(e.deprecated),
                )
            )
        s.commit()
    return id_map


def _remap_action_to_child_kg(
    action: KgEditAction, id_map: dict[str, str]
) -> KgEditAction:
    """把 action 里引用的 parent KG concept_id 转成 child KG 的（带 @ 后缀）。"""
    updates: dict = {}
    if action.concept_id and action.concept_id in id_map:
        updates["concept_id"] = id_map[action.concept_id]
    if action.merge_target_id and action.merge_target_id in id_map:
        updates["merge_target_id"] = id_map[action.merge_target_id]
    if action.edge is not None:
        e = action.edge
        new_from = id_map.get(e.from_id, e.from_id)
        new_to = id_map.get(e.to_id, e.to_id)
        if new_from != e.from_id or new_to != e.to_id:
            updates["edge"] = e.model_copy(update={"from_id": new_from, "to_id": new_to})
    return action.model_copy(update=updates) if updates else action


def update_kg(
    *,
    db: RelationalStore,
    kg_id: str,
    actions: list[KgEditAction],
    mode: str = "in_place",
) -> KgUpdateResult:
    """对 KG 应用 actions 列表，返回 KgUpdateResult。

    mode:
    - "in_place"  (K2 行为，默认)  在 kg_id 上直接修改 + audit trail
    - "versioned" (K3 行为)          复制 KG 到新 kg_id 后再改；原 KG 不变
    """
    if mode not in _VALID_MODES:
        raise TutorError(
            "DEPENDENCY_MISSING",
            hint=f"mode 必须是 {_VALID_MODES}，收到 {mode!r}",
        )

    # 预检父 KG 存在
    with db.session() as s:
        if s.get(KnowledgeGraphRow, kg_id) is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)

    # versioned：先复制
    target_kg = kg_id
    id_map: dict[str, str] = {}
    if mode == "versioned":
        target_kg = _next_version_kg_id(db, kg_id)
        id_map = _clone_kg(db, kg_id, target_kg)
        # actions 中引用 parent kg 的 id 需要重映射
        actions = [_remap_action_to_child_kg(a, id_map) for a in actions]

    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, target_kg)

        applied = 0
        failures: list[KgUpdateFailure] = []
        for i, action in enumerate(actions):
            try:
                _apply_one(s, target_kg, action)
                applied += 1
            except ValueError as exc:
                failures.append(KgUpdateFailure(action_index=i, reason=str(exc)))
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    KgUpdateFailure(action_index=i, reason=f"{type(exc).__name__}: {exc}")
                )

        # 重新统计 + Quality Gate
        new_concepts_rows = s.query(ConceptRow).filter_by(kg_id=target_kg).all()
        new_edges_rows = s.query(RelationRow).filter_by(kg_id=target_kg).all()

        new_concepts = [Concept.model_validate(r.full_json) for r in new_concepts_rows if r.full_json]
        new_edges = [
            RelationSchema(
                from_id=r.from_id,
                to_id=r.to_id,
                type=r.type,
                weight=r.weight,
                explanation=r.explanation,
                confidence=r.confidence,
                deprecated=bool(r.deprecated),
            )
            for r in new_edges_rows
        ]

        quality = (
            _compute_quality(new_concepts, new_edges)
            if new_concepts
            else QualityReport(
                overall="fail",
                chapter_coverage=0.0,
                isolated_nodes=0,
                cycles=0,
                avg_confidence=0.0,
                warnings=["KG 已空"],
            )
        )

        # BUG.3 fix: versioned 模式下 Concept.id (full_json, base id) 与
        # Relation 端点 (ORM row.id, 带 @v 后缀) 不同空间；用 ORM id 重算
        # isolated 覆盖到 quality 报告，避免 100% 误报。
        if mode == "versioned" and new_concepts_rows:
            row_ids = {r.id for r in new_concepts_rows}
            endpoint_ids = (
                {r.from_id for r in new_edges_rows}
                | {r.to_id for r in new_edges_rows}
            )
            true_isolated = row_ids - endpoint_ids
            warnings = [w for w in quality.warnings if "孤立节点" not in w]
            if true_isolated:
                warnings.append(f"{len(true_isolated)} 个孤立节点（无边连接）")
            quality = quality.model_copy(update={
                "isolated_nodes": len(true_isolated),
                "warnings": warnings,
            })

        kg.node_count = len(new_concepts_rows)
        kg.edge_count = len(new_edges_rows)
        kg.quality_json = quality.model_dump(mode="json")

        # audit trail
        manifest = copy.deepcopy(kg.manifest_json or {})
        history = manifest.get("update_history") or []
        history.append({
            "at": datetime.utcnow().isoformat() + "Z",
            "mode": mode,
            "parent_kg_id": (kg_id if mode == "versioned" else None),
            "actions": [a.model_dump(mode="json") for a in actions],
            "applied": applied,
            "failed": [f.model_dump(mode="json") for f in failures],
        })
        manifest["update_history"] = history
        kg.manifest_json = manifest

        s.commit()

    logger.info(
        "update_kg.done",
        mode=mode,
        parent_kg=kg_id,
        target_kg=target_kg,
        applied=applied,
        failed=len(failures),
        new_node_count=len(new_concepts_rows),
    )

    version_label = (
        f"versioned@{datetime.utcnow().isoformat()}Z"
        if mode == "versioned"
        else f"in-place@{datetime.utcnow().isoformat()}Z"
    )
    return KgUpdateResult(
        kg_id=target_kg,
        new_version=version_label,
        applied=applied,
        failed=failures,
        new_quality_report=quality,
    )
