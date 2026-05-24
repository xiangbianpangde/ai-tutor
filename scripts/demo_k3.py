"""Slice K3 演示：KG 版本树 + diff + rollback。

完整流程:
1. build KG v1 → 关联到 subject
2. 学几个 concept，BKT 累积
3. update_kg(mode='versioned') → KG v2，改一个定义 + 删一个 concept
4. diff_kg(v1, v2) → 看具体差异
5. 切到 v2 学习（BKT 因 base_id 跨版本继承）
6. rollback_kg → 回到 v1（不删 v2）
7. 验证 BKT 数据无丢失

用法:
    uv run python scripts/demo_k3.py [--mock]
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config import load_env
from shared.llm_cache import CachedLLMProvider
from shared.llm_client import LLMProvider, MockLLMProvider
from shared.logging_config import configure_logging
from shared.providers.deepseek import DeepSeekProvider
from shared.storage import RelationalStore


def section(t: str) -> None:
    print(f"\n{'━' * 64}\n  {t}\n{'━' * 64}")


def _enrich(rng: random.Random, name: str) -> str:
    return json.dumps({"definition": f"{name} 的原始定义", "confidence": round(rng.uniform(0.7, 0.95), 2)}, ensure_ascii=False)


def _make_llm(use_mock: bool, n: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds), f"DeepSeek({ds.model})"
    rng = random.Random(42)
    return MockLLMProvider(canned_responses=[_enrich(rng, f"c{i}") for i in range(n + 10)]), "Mock"


def main(md_path: Path, use_mock: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    from shared.models import Subject, User
    USER_ID, SUBJECT_ID = "yhn", "demo-k3"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="K3 demo"))
        s.commit()

    # ───────────── ① build KG v1 ─────────────
    section("① 建 KG v1")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    from shared.storage import FileStore

    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="demo-k3", version="v1",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID, file_store=fs, db=db,
    )
    md_corpus = Path(manifest.file_paths["markdown"])
    skeleton, _ = _build_toc(subject_slug="demo-k3", markdown_path=md_corpus)
    llm, label = _make_llm(use_mock, len(skeleton))
    print(f"  provider = {label} · {len(skeleton)} concepts")

    kg_v1 = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="demo-k3",
        markdown_path=md_corpus, db=db,
    )
    print(f"  v1 kg_id = {kg_v1.kg_id}")

    with db.session() as s:
        s.get(Subject, SUBJECT_ID).kg_id = kg_v1.kg_id
        s.commit()

    # ───────────── ② 模拟学习几个 concept ─────────────
    section("② 学几个 concept（BKT 累积）")
    from servers.tutoring_mcp.bkt_store import BKTStore
    from shared.schemas import BKTParams
    from shared.models import ConceptRow

    with db.session() as s:
        rows = (
            s.query(ConceptRow)
            .filter_by(kg_id=kg_v1.kg_id)
            .order_by(ConceptRow.id)
            .limit(3)
            .all()
        )
        ids = [c.id for c in rows]
        names = {c.id: c.name_primary for c in rows}

    bkt = BKTStore(db)
    bkt.save(USER_ID, BKTParams(concept_id=ids[0], p_mastery=0.85, n_observations=5))
    bkt.save(USER_ID, BKTParams(concept_id=ids[1], p_mastery=0.65, n_observations=4))
    bkt.save(USER_ID, BKTParams(concept_id=ids[2], p_mastery=0.45, n_observations=3))
    print(f"  BKT 记录前 3 个 concept：")
    for cid in ids:
        m = bkt.load(USER_ID, cid)
        print(f"    [{m.p_mastery:.2f}] {names[cid]} ({cid})")

    # ───────────── ③ versioned update → KG v2 ─────────────
    section("③ update_kg(mode='versioned')  —  改 1 定义 + 删 1 节点")
    from servers.knowledge_mcp.kg_update import update_kg
    from shared.schemas import KgEditAction

    edit_target = ids[0]
    delete_target = ids[2]
    upd = update_kg(
        db=db, kg_id=kg_v1.kg_id,
        actions=[
            KgEditAction(op="edit_definition", concept_id=edit_target,
                          new_definition="(K3 v2) 这是人工校对过的精准定义。"),
            KgEditAction(op="delete_concept", concept_id=delete_target),
        ],
        mode="versioned",
    )
    kg_v2 = upd.kg_id
    print(f"  v2 kg_id = {kg_v2}")
    print(f"  applied={upd.applied}  failed={upd.failed}")

    # ───────────── ④ diff_kg(v1, v2) ─────────────
    section("④ diff_kg(v1, v2)")
    from servers.knowledge_mcp.kg_diff import diff_kg
    d = diff_kg(db=db, kg_id_a=kg_v1.kg_id, kg_id_b=kg_v2)
    print(f"  summary: {d.summary}")
    if d.definition_changed:
        print(f"  definition_changed:")
        for c in d.definition_changed:
            print(f"    · {c['name']}  (base={c['base_id']})")
            print(f"        from: {c['from'][:50]}")
            print(f"        to:   {c['to'][:50]}")
    if d.removed:
        print(f"  removed:")
        for c in d.removed:
            print(f"    · {c['name']}  (base={c['base_id']})")

    # ───────────── ⑤ 切到 v2 ─────────────
    section("⑤ 切到 v2 + BKT 自动跟随（base_id 设计）")
    with db.session() as s:
        s.get(Subject, SUBJECT_ID).kg_id = kg_v2
        s.commit()
    # 注意：BKT.concept_id 用的是 v1 时的 id。如果 host 要查 v2 concept 对应的 BKT，
    # 需要用 base_id 做映射。这里演示 base_id 一致性
    with db.session() as s:
        from shared.models import ConceptRow
        v2_first = (
            s.query(ConceptRow)
            .filter_by(kg_id=kg_v2, base_id=edit_target)
            .first()
        )
        print(f"  edited concept in v2:")
        print(f"    id        = {v2_first.id}")
        print(f"    base_id   = {v2_first.base_id}")
        print(f"    definition= {v2_first.definition[:60]}")
        print(f"    BKT (via base_id) mastery = {bkt.load(USER_ID, edit_target).p_mastery}")
        print(f"  注：BKT 用 base_id 作 PK，所以同一 concept 跨 v1/v2 共享 mastery")

    # ───────────── ⑥ rollback ─────────────
    section("⑥ rollback_kg → v1")
    from servers.knowledge_mcp.kg_rollback import rollback_kg
    r = rollback_kg(db=db, subject_id=SUBJECT_ID, target_kg_id=kg_v1.kg_id)
    print(f"  {r}")
    with db.session() as s:
        cur = s.get(Subject, SUBJECT_ID).kg_id
        print(f"  当前 subject.kg_id = {cur}")
        # v2 仍存在
        from shared.models import KnowledgeGraphRow
        v2_row = s.get(KnowledgeGraphRow, kg_v2)
        print(f"  v2 是否还存在: {v2_row is not None}（应 True，rollback 不删除）")

    # ───────────── ⑦ BKT 数据无丢失 ─────────────
    section("⑦ rollback 后 BKT 数据完整性")
    for cid in ids:
        m = bkt.load(USER_ID, cid)
        print(f"    [{m.p_mastery:.2f}] {names.get(cid, cid)}  (n_obs={m.n_observations})")

    print(f"\n[OK] Slice K3 demo 完成。provider = {label}")
    print(f"     版本树：v1 ←—— v2  (subject 当前指向 v1)")


if __name__ == "__main__":
    args = sys.argv[1:]
    use_mock = "--mock" in args
    args = [a for a in args if a != "--mock"]
    md_arg = args[0] if args else None
    md_path = (
        Path(md_arg) if md_arg
        else Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "mini_subject.md"
    )
    if not md_path.exists():
        sys.exit(f"markdown 不存在: {md_path}")
    main(md_path, use_mock=use_mock)
