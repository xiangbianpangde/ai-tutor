"""Slice D 演示: 一键 digest 真实笔记成 mindmap + notes + quiz。

流程: acquire → build_kg(depth=concept, 真实 DeepSeek/Mock) → digest(三种格式)
产物默认写到 data/output/digest/<kg_id>/

用法:
    uv run python scripts/demo_digest.py "C:/path/note.md"
    uv run python scripts/demo_digest.py "C:/path/note.md" --mock   # 不付费
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


def _canned(rng: random.Random, name: str) -> str:
    return json.dumps({
        "definition": f"{name}：从笔记上下文提取的定义（Mock）",
        "informal_description": f"通俗解释 {name}",
        "examples": [{"text": f"例：{name}", "type": "computation"}],
        "common_misconceptions": [f"误：{name}"],
        "confidence": round(rng.uniform(0.4, 0.9), 2),
    }, ensure_ascii=False)


def _make_llm(use_mock: bool, n: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds, max_size=256), f"DeepSeek({ds.model})"
    rng = random.Random(42)
    canned = [_canned(rng, f"c{i}") for i in range(n + 10)]
    return MockLLMProvider(canned_responses=canned), "Mock"


def main(md_path: Path, use_mock: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    USER_ID, SUBJECT_ID = "yhn", "demo-digest"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="Digest demo"))
        s.commit()

    # ---- acquire + build_kg ----
    section("① acquire + build_kg(depth=concept)")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    from shared.storage import FileStore

    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="digest-demo", version="d",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID, file_store=fs, db=db,
    )
    md_corpus_path = Path(manifest.file_paths["markdown"])
    skel, _ = _build_toc(subject_slug="digest-demo", markdown_path=md_corpus_path)
    llm, label = _make_llm(use_mock, len(skel))
    print(f"provider     = {label}")
    print(f"concepts     = {len(skel)}")

    t0 = time.time()
    kg_result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id,
        subject_slug="digest-demo",
        markdown_path=md_corpus_path,
        db=db,
    )
    print(f"build 耗时   = {time.time() - t0:.1f}s")
    print(f"avg conf     = {kg_result.quality_report.avg_confidence:.3f}")
    print(f"kg_id        = {kg_result.kg_id}")

    # ---- digest(mindmap + notes + quiz) ----
    section("② digest(mindmap + notes + quiz)")
    from servers.digest_mcp.orchestrator import digest

    out_dir = Path("data/output/digest") / kg_result.kg_id
    run = digest(
        db=db,
        kg_id=kg_result.kg_id,
        out_dir=out_dir,
        formats=["mindmap", "notes", "quiz", "audio"],  # audio 故意 stub 看 warning
        quiz_count=8,
        quiz_seed=42,
    )
    print(f"产物数 (artifacts) = {len(run.artifacts)}")
    for a in run.artifacts:
        rel = Path(a.uri.replace("file:///", ""))
        print(f"  [{a.mime_type:25s}] {a.size_bytes:7d} bytes  {rel.name}")
    if run.warnings:
        print(f"\nwarnings ({len(run.warnings)}):")
        for w in run.warnings:
            print(f"  - {w}")

    # ---- 预览部分产物 ----
    section("③ 产物预览")
    for a in run.artifacts:
        path = Path(a.uri.replace("file:///", ""))
        if a.mime_type == "text/vnd.mermaid":
            text = path.read_text(encoding="utf-8")
            print("\nMermaid (前 8 行):")
            for line in text.splitlines()[:8]:
                print(f"  {line}")
            print(f"  ... (+{max(0, len(text.splitlines()) - 8)} more)")
        elif a.mime_type == "text/markdown":
            text = path.read_text(encoding="utf-8")
            print("\nNotes (前 15 行):")
            for line in text.splitlines()[:15]:
                print(f"  {line}")
        elif a.mime_type == "application/json":
            qd = json.loads(path.read_text(encoding="utf-8"))
            qs = qd.get("questions", [])
            print(f"\nQuiz: {len(qs)} 题")
            for i, q in enumerate(qs[:3], 1):
                print(f"  Q{i} [{q['type']}] {q['prompt'][:60]}{'...' if len(q['prompt']) > 60 else ''}")
                if q["type"] == "multiple_choice":
                    print(f"      options: {q['options']}")
                print(f"      answer: {q['answer']}")
            if len(qs) > 3:
                print(f"  ... 还有 {len(qs) - 3} 题")

    print("\n[OK] Slice D demo 完成。")
    print(f"     产物目录: {out_dir.resolve()}")
    print("     用浏览器打开 quiz HTML 可立即做题；mindmap.mmd 可粘到 mermaid.live。")


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
