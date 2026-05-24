"""Slice S 演示：digest 产物自动 push 到 Obsidian + 反向 pull 已有笔记。

用法:
    uv run python scripts/demo_sync.py "<你的-md>" --vault "C:/Users/yhn/Documents/GitHub/xbpd_obsidian"

默认 vault 指向你已知的 xbpd_obsidian。--dry-run 只演示不真实写 vault。
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


DEFAULT_VAULT = r"C:\Users\yhn\Documents\GitHub\xbpd_obsidian"
DEFAULT_NOTE = r"C:\Users\yhn\Documents\GitHub\xbpd_obsidian\07.学习笔记\大一下\机器学习\机器学习笔记\4月24日-星期四-聚类.md"


def section(t: str) -> None:
    print(f"\n{'─' * 60}\n{t}\n{'─' * 60}")


def _canned_enrichment(rng: random.Random, name: str) -> str:
    return json.dumps({
        "definition": f"{name}（Mock 填充）",
        "confidence": round(rng.uniform(0.6, 0.95), 2),
    }, ensure_ascii=False)


def _make_llm(use_mock: bool, n: int) -> tuple[LLMProvider, str]:
    if not use_mock:
        load_env()
        ds = DeepSeekProvider.from_env()
        if ds is not None:
            return CachedLLMProvider(inner=ds), f"DeepSeek({ds.model})"
    rng = random.Random(42)
    canned = [_canned_enrichment(rng, f"c{i}") for i in range(n + 10)]
    return MockLLMProvider(canned_responses=canned), "Mock"


def main(md_path: Path, vault_path: Path, use_mock: bool, dry_run: bool) -> None:
    configure_logging("WARNING")
    db = RelationalStore.from_env()
    db.init_schema()

    print(f"vault    = {vault_path}")
    print(f"note     = {md_path}")
    print(f"dry-run  = {dry_run}")

    if not vault_path.exists():
        sys.exit(f"vault 不存在：{vault_path}")

    # ---- ① build KG (concept 模式) ----
    section("① 准备 KG（depth=concept）")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    from shared.storage import FileStore
    from shared.models import Subject, User

    with db.session() as s:
        if s.get(User, "yhn") is None:
            s.add(User(id="yhn"))
        if s.get(Subject, "demo-sync") is None:
            s.add(Subject(id="demo-sync", user_id="yhn", display_name="Sync demo"))
        s.commit()

    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="demo-sync", version="s",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id="yhn", file_store=fs, db=db,
    )
    md_corpus = Path(manifest.file_paths["markdown"])
    skeleton, _ = _build_toc(subject_slug="demo-sync", markdown_path=md_corpus)
    llm, label = _make_llm(use_mock, len(skeleton))
    print(f"provider = {label}")

    result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="demo-sync",
        markdown_path=md_corpus, db=db,
    )
    print(f"kg_id    = {result.kg_id}")

    # ---- ② digest ----
    section("② 生成 digest 产物")
    from servers.digest_mcp.orchestrator import digest
    out_dir = (Path("data/output/digest") / result.kg_id).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    run = digest(
        db=db, kg_id=result.kg_id, out_dir=out_dir,
        formats=["mindmap", "notes", "quiz"],
    )
    for a in run.artifacts:
        size_kb = a.size_bytes / 1024
        print(f"  [{a.mime_type:24s}] {size_kb:5.1f} KB  {Path(a.uri.replace('file:///','')).name}")

    # ---- ③ push 到 Obsidian ----
    section("③ push_to_obsidian → vault/AI-Tutor/demo-sync/")
    from servers.sync_mcp.obsidian import push_to_obsidian

    if dry_run:
        target = vault_path / "AI-Tutor" / "demo-sync"
        print(f"  (dry-run) 将写入 {target}")
        for a in run.artifacts:
            name = Path(a.uri.replace("file:///", "")).name
            print(f"    → {target / name}")
    else:
        push = push_to_obsidian(
            vault_path=vault_path,
            subject_id="demo-sync",
            artifacts=run.artifacts,
            subdir="AI-Tutor",
        )
        print(f"  target_dir   = {push.target_dir}")
        print(f"  pushed_count = {push.pushed_count}")
        print(f"  skipped      = {push.skipped_count}")
        if push.failed:
            for f in push.failed:
                print(f"  failed       = {f}")
        else:
            for f in push.target_files:
                print(f"    ✓ {f}")

    # ---- ④ pull：找 vault 中跟"机器学习"相关的笔记 ----
    section("④ pull_homework_from_obsidian（查 ml 相关笔记）")
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    # 直接用文件名/路径里的"机器学习"作为 subject_id
    # 但 pull 的匹配是大小写/-/_ 不敏感的简化版，对中文文件名实际只能靠 frontmatter
    # 这里演示用 "机器学习" 直接搜文件名包含的（Obsidian 笔记按主题命名）
    found = pull_homework_from_obsidian(
        vault_path=vault_path,
        subject_id="机器学习",
        limit=5,
    )
    print(f"  发现 {len(found)} 个匹配文件（最近 5 个）:")
    for h in found:
        size = len(h.content)
        print(f"    [{h.modified_at.strftime('%Y-%m-%d')}] {h.relative_path}  ({size} chars)")

    # ---- ⑤ 真实场景：让 host 拉笔记 → 调 acquire 摄入 ----
    section("⑤ 端到端反向场景示意")
    print("  典型 host LLM 编排:")
    print("    1. sync.pull_homework_from_obsidian(...)  # 看学生最近写了什么")
    print("    2. knowledge.acquire_subject(... uri=found[0].path)  # 摄入到 KG")
    print("    3. digest(... formats=['quiz'])           # 出测验")
    print("    4. sync.push_to_obsidian(... artifacts)   # 测验回到 vault 给学生用")

    print(f"\n[OK] Slice S demo 完成。provider = {label}")


if __name__ == "__main__":
    args = sys.argv[1:]
    use_mock = "--mock" in args
    dry_run = "--dry-run" in args
    args = [a for a in args if a not in ("--mock", "--dry-run")]

    vault_path = Path(DEFAULT_VAULT)
    if "--vault" in args:
        i = args.index("--vault")
        vault_path = Path(args[i + 1])
        args = args[:i] + args[i + 2:]

    md_path = Path(args[0]) if args else Path(DEFAULT_NOTE)
    if not md_path.exists():
        sys.exit(f"markdown 文件不存在: {md_path}")
    main(md_path, vault_path, use_mock=use_mock, dry_run=dry_run)
