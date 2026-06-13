"""Slice K1+K2 演示: depth=concept + 真实 DeepSeek + review_kg + update_kg。

默认走真实 DeepSeek（需要 .env 里有 DEEPSEEK_API_KEY）。
没 key 时退回 MockLLMProvider，仍能跑全流程（不付费）。

用法:
    uv run python scripts/demo_concept_mode.py "C:/path/to/note.md"
    uv run python scripts/demo_concept_mode.py "C:/path/to/note.md" --mock
"""
from __future__ import annotations

import json
import random
import sys
import time
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
from shared.models import Subject, User
from shared.providers.deepseek import DeepSeekProvider
from shared.storage import RelationalStore


def section(t: str) -> None:
    print(f"\n{'─' * 60}\n{t}\n{'─' * 60}")


def _canned_enrichment(rng: random.Random, name: str) -> str:
    return json.dumps({
        "definition": f"{name}（Mock 填充）",
        "informal_description": f"通俗解释 {name}（Mock）",
        "examples": [{"text": f"{name} 的例子（Mock）", "type": "computation"}],
        "common_misconceptions": [f"误解 {name}"],
        "bloom_level": rng.choice(["remember", "understand", "apply"]),
        "confidence": round(rng.uniform(0.35, 0.95), 2),
    }, ensure_ascii=False)


def _make_llm(use_mock: bool, num_concepts: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds, max_size=256), f"DeepSeek({ds.model})"
    # fallback
    rng = random.Random(42)
    canned = [_canned_enrichment(rng, f"concept{i}") for i in range(num_concepts + 5)]
    return MockLLMProvider(canned_responses=canned), "Mock"


def main(md_path: Path, use_mock: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    USER_ID, SUBJECT_ID = "yhn", "demo-k2-ml"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="ML K2 demo"))
        s.commit()

    # ---- acquire ----
    section("① acquire_subject")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from shared.storage import FileStore

    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="ml-k2-demo",
        version="k2",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID,
        file_store=fs,
        db=db,
    )
    md_corpus_path = Path(manifest.file_paths["markdown"])
    print(f"corpus_id    = {corpus_id}")
    print(f"chapters/sec = {manifest.total_chapters}/{manifest.total_sections}")

    # ---- build_kg(depth=concept) ----
    section("② build_knowledge_graph(depth=concept) — 调真实 LLM")
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc

    skeleton, _ = _build_toc(subject_slug="ml-k2-demo", markdown_path=md_corpus_path)
    n_concepts = len(skeleton)
    llm, provider_label = _make_llm(use_mock=use_mock, num_concepts=n_concepts)
    print(f"provider     = {provider_label}")
    print(f"concepts     = {n_concepts}（每个一次 LLM 调用 + 一次缓存查找）")

    t0 = time.time()
    result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id,
        subject_slug="ml-k2-demo",
        markdown_path=md_corpus_path,
        db=db,
    )
    elapsed = time.time() - t0
    print(f"耗时         = {elapsed:.1f}s ({elapsed / max(n_concepts,1):.2f}s/concept)")
    print(f"avg conf     = {result.quality_report.avg_confidence:.3f}")
    print(f"quality      = {result.quality_report.overall}")
    if isinstance(llm, CachedLLMProvider):
        print(f"cache stats  = {llm.stats()}")

    # ---- 展示几个 enrich 后的 concept ----
    section("③ enrich 后的概念（按置信度降序前 5）")
    from shared.models import ConceptRow
    with db.session() as s:
        rows = (
            s.query(ConceptRow)
            .filter_by(kg_id=result.kg_id)
            .order_by(ConceptRow.confidence.desc())
            .limit(5)
            .all()
        )
        for r in rows:
            print(f"  [{r.confidence:.2f}] {r.name_primary}")
            print(f"        定义: {r.definition[:80]}")

    # ---- review_kg ----
    section("④ review_kg(mode=quick, limit=3)")
    from servers.knowledge_mcp.kg_review import review_kg
    rv = review_kg(db=db, kg_id=result.kg_id, mode="quick", limit=3)
    print(f"低置信概念 ({len(rv.low_confidence_concepts)}):")
    for c in rv.low_confidence_concepts:
        print(f"  [{c.confidence:.2f}] {c.name}  — {c.definition_preview[:50]}")
    print("\nsuggested_actions:")
    for a in rv.suggested_actions:
        print(f"  - op={a.op}  note={a.note}")

    # ---- update_kg: 演示批准 + 改一个定义 ----
    section("⑤ update_kg: 改第一个低置信概念的定义 + approve_all")
    from servers.knowledge_mcp.kg_update import update_kg
    from shared.schemas import KgEditAction

    actions = []
    if rv.low_confidence_concepts:
        actions.append(
            KgEditAction(
                op="edit_definition",
                concept_id=rv.low_confidence_concepts[0].concept_id,
                new_definition="（人工校正版）" + rv.low_confidence_concepts[0].name,
            )
        )
    actions.append(KgEditAction(op="approve_all"))
    upd = update_kg(db=db, kg_id=result.kg_id, actions=actions)
    print(f"applied      = {upd.applied}")
    print(f"failed       = {upd.failed}")
    print(f"new quality  = {upd.new_quality_report.overall}  "
          f"avg_conf={upd.new_quality_report.avg_confidence:.3f}")

    # ---- 关联到 subject 让 tutoring 用 ----
    with db.session() as s:
        subj = s.get(Subject, SUBJECT_ID)
        subj.kg_id = result.kg_id
        s.commit()

    print(f"\n[OK] K2 demo 完成。LLM provider = {provider_label}")
    print(f"     KG = {result.kg_id}")
    print("     接下来可跑 scripts/run_e2e_demo.py 接续学习会话。")


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
        sys.exit(f"markdown 文件不存在: {md_path}")
    main(md_path, use_mock=use_mock)
