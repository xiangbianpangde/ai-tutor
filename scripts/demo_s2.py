"""Slice S2 演示：本地 git 版本控制学习产物 + Obsidian 变更监听。

1. init_subject_repo → 建本地 git 仓库
2. digest 出产物 → push_artifacts 提交到 git（带 commit sha）
3. 再 digest 一次 → 第二个 commit（版本历史）
4. watch_obsidian → 轮询 vault 最近变更

用法:
    uv run python scripts/demo_s2.py [--mock]
"""
from __future__ import annotations

import asyncio
import json
import random
import subprocess
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


DEFAULT_VAULT = Path(r"C:\Users\yhn\Documents\GitHub\xbpd_obsidian")
DEFAULT_MD = DEFAULT_VAULT / "07.学习笔记/大一下/机器学习/机器学习笔记/4月24日-星期四-聚类.md"


def section(t: str) -> None:
    print(f"\n{'━' * 60}\n  {t}\n{'━' * 60}")


def _enrich(rng: random.Random, name: str) -> str:
    return json.dumps({"definition": f"{name}（Mock）", "confidence": round(rng.uniform(0.7, 0.95), 2)}, ensure_ascii=False)


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

    import os
    git_root = Path("data/git_repos").resolve()
    os.environ["AI_TUTOR_GIT_ROOT"] = str(git_root)

    from shared.models import Subject, User
    USER_ID, SUBJECT_ID = "yhn", "demo-s2"
    with db.session() as s:
        if s.get(User, USER_ID) is None:
            s.add(User(id=USER_ID))
        if s.get(Subject, SUBJECT_ID) is None:
            s.add(Subject(id=SUBJECT_ID, user_id=USER_ID, display_name="S2 demo"))
        s.commit()

    # ① 建 KG + digest 产物
    section("① 建 KG + 生成 digest 产物")
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder
    from servers.knowledge_mcp.kg_enrich_adapter import _build_toc
    from servers.digest_mcp.orchestrator import digest
    from shared.storage import FileStore

    fs = FileStore(Path("data"))
    manifest, corpus_id = acquire(
        subject="demo-s2", version="v1",
        sources=[AcquireSource(type="file", uri=str(md_path))],
        user_id=USER_ID, file_store=fs, db=db,
    )
    md_corpus = Path(manifest.file_paths["markdown"])
    skeleton, _ = _build_toc(subject_slug="demo-s2", markdown_path=md_corpus)
    llm, label = _make_llm(use_mock, len(skeleton))
    kg = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id, subject_slug="demo-s2",
        markdown_path=md_corpus, db=db,
    )
    out_dir = (Path("data/output/digest") / kg.kg_id).resolve()
    run = digest(db=db, kg_id=kg.kg_id, out_dir=out_dir, formats=["mindmap", "notes", "quiz"])
    print(f"  provider = {label}")
    print(f"  artifacts = {len(run.artifacts)}")

    # ② init_subject_repo
    section("② init_subject_repo → 本地 git 仓库")
    from servers.sync_mcp import server as ss
    init_fn = getattr(ss.init_subject_repo, "fn", ss.init_subject_repo)
    repo = asyncio.run(init_fn(user_id=USER_ID, subject_id=SUBJECT_ID))
    print(f"  repo_path = {repo['repo_path']}")
    print(f"  remote    = {repo['remote']}")

    # ③ push_artifacts（第一次 commit）
    section("③ push_artifacts → git commit #1")
    push_fn = getattr(ss.push_artifacts, "fn", ss.push_artifacts)
    arts = [{"uri": a.uri, "mime_type": a.mime_type, "size_bytes": a.size_bytes} for a in run.artifacts]
    r1 = asyncio.run(push_fn(
        subject_id=SUBJECT_ID, artifacts=arts,
        commit_message="第一次同步：mindmap + notes + quiz",
        user_id=USER_ID,
    ))
    print(f"  commit_sha      = {r1['commit_sha'][:10] if r1['commit_sha'] else None}")
    print(f"  files_committed = {r1['files_committed']}")

    # ④ 再生成 + 第二次 commit
    section("④ 改 KG → push_artifacts → git commit #2（版本历史）")
    from servers.knowledge_mcp.kg_update import update_kg
    from shared.schemas import KgEditAction
    with db.session() as s:
        from shared.models import ConceptRow
        cid = s.query(ConceptRow).filter_by(kg_id=kg.kg_id).first().id
    upd = update_kg(db=db, kg_id=kg.kg_id, actions=[
        KgEditAction(op="edit_definition", concept_id=cid, new_definition="(v2 修订) 更精准的定义"),
    ], mode="in_place")
    run2 = digest(db=db, kg_id=kg.kg_id, out_dir=out_dir, formats=["notes"])
    arts2 = [{"uri": a.uri, "mime_type": a.mime_type, "size_bytes": a.size_bytes} for a in run2.artifacts]
    r2 = asyncio.run(push_fn(
        subject_id=SUBJECT_ID, artifacts=arts2,
        commit_message="第二次同步：修订 notes",
        user_id=USER_ID,
    ))
    print(f"  commit_sha      = {r2['commit_sha'][:10] if r2['commit_sha'] else None}")

    # git log
    repo_path = Path(repo["repo_path"])
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo_path,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout or ""
    print(f"\n  git log:")
    for line in log.strip().splitlines():
        print(f"    {line}")

    # ⑤ watch_obsidian
    section("⑤ watch_obsidian → 轮询 vault 最近变更")
    watch_fn = getattr(ss.watch_obsidian, "fn", ss.watch_obsidian)
    vault = DEFAULT_VAULT
    if vault.exists():
        changes = asyncio.run(watch_fn(vault_path=str(vault), subject_id="机器学习"))
        print(f"  发现 {len(changes)} 个匹配文件（首次扫描）:")
        for c in changes[:5]:
            print(f"    [{c['modified_at'][:10]}] {c['relative_path']}")
    else:
        print(f"  (vault 不存在: {vault})")

    print(f"\n[OK] Slice S2 demo 完成。本地 git 仓库 = {repo['repo_path']}")
    print(f"     学习产物现在有完整版本历史，可 git diff / git checkout 任意版本")


if __name__ == "__main__":
    args = sys.argv[1:]
    use_mock = "--mock" in args
    args = [a for a in args if a != "--mock"]
    md_path = Path(args[0]) if args else DEFAULT_MD
    if not md_path.exists():
        md_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "mini_subject.md"
    main(md_path, use_mock=use_mock)
