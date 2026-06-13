"""CR2 代码审查回归测试。

CR2.1 audio._run_async 在已运行的 event loop 内不应 RuntimeError（用 worker thread）
CR2.2 multi_agent LLM 返回 content=None → 回退模板，不 AttributeError
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


# ---------------- CR2.1 ---------------- #


def test_run_async_works_without_loop() -> None:
    from servers.digest_mcp.audio import _run_async

    async def coro():
        return 42

    assert _run_async(coro()) == 42


@pytest.mark.asyncio
async def test_run_async_works_inside_running_loop() -> None:
    """旧 bug：在 async 上下文（有 running loop）里 asyncio.run 会 RuntimeError。
    _run_async 应检测到 running loop 并在 worker thread 跑，正常返回。
    """
    from servers.digest_mcp.audio import _run_async

    async def coro():
        return "ok"

    # 当前就在 pytest-asyncio 的 running loop 里
    result = _run_async(coro())
    assert result == "ok"


# ---------------- CR2.2 ---------------- #


class _NoneContentResp:
    content = None


class _NoneContentProvider:
    category = "llm"
    name = "none-content"

    def chat(self, *, messages, temperature=0.3, max_tokens=1024):
        return _NoneContentResp()


@pytest.fixture
def kg_with_content(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ce-shi", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    canned = [json.dumps({"definition": f"d{i}", "confidence": 0.85}, ensure_ascii=False)
              for i in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id, subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    return tmp_db, r.kg_id


def test_multi_agent_none_content_falls_back_to_template(kg_with_content, tmp_path: Path) -> None:
    from servers.digest_mcp.multi_agent import generate_multi_agent

    db, kg_id = kg_with_content
    # provider 返回 content=None；不应抛 AttributeError，应模板兜底
    art = generate_multi_agent(db=db, kg_id=kg_id, out_dir=tmp_path, llm=_NoneContentProvider())
    doc = json.loads(Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8"))
    # 每个 scene 仍有对话（模板兜底）
    assert doc["scenes"]
    assert all(sc["dialogue"] for sc in doc["scenes"])
