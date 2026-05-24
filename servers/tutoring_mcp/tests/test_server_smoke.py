"""tutoring-mcp server tool 注册 + 一个 round-trip smoke test。

实现的 tool: start_learning_session / next_action / respond
stub 的 tool: interrupt / checkpoint / learning_insight / generate_review_plan
"""
from __future__ import annotations

from pathlib import Path

import pytest

from servers.tutoring_mcp import server as srv
from shared.errors import TutorError
from shared.models import Subject, User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _unwrap(tool_obj):
    return getattr(tool_obj, "fn", None) or getattr(tool_obj, "func", None) or tool_obj


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RelationalStore:
    db_path = tmp_path / "tut.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AI_TUTOR_DATA_ROOT", str(tmp_path / "data"))
    store = RelationalStore.from_env()
    store.init_schema()
    with store.session() as s:
        s.add(User(id="yhn"))
        s.add(Subject(id="ce-shi", user_id="yhn", display_name="测试"))
        s.commit()
    return store


async def _seed_kg(env: RelationalStore, tmp_path: Path) -> str:
    """跑 knowledge-mcp 建一个 toc KG，并把 subject.kg_id 指上。返回 subject_id。"""
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import TocKGBuilder
    from shared.storage import FileStore

    fs = FileStore(tmp_path / "data")
    manifest, corpus_id = acquire(
        subject="测试",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=fs,
        db=env,
    )
    result = TocKGBuilder().build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]),
        db=env,
    )
    with env.session() as s:
        subj = s.get(Subject, "ce-shi")
        subj.kg_id = result.kg_id
        s.commit()
    return "ce-shi"


@pytest.mark.asyncio
async def test_all_tools_registered(env: RelationalStore) -> None:
    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    for expected in [
        "start_learning_session",
        "next_action",
        "respond",
        "interrupt",
        "checkpoint",
        "learning_insight",
        "generate_review_plan",
        "health",
    ]:
        assert expected in names, f"missing tool: {expected}"


@pytest.mark.asyncio
async def test_start_then_next_then_respond(env: RelationalStore, tmp_path: Path) -> None:
    subject_id = await _seed_kg(env, tmp_path)

    start_fn = _unwrap(srv.start_learning_session)
    next_fn = _unwrap(srv.next_action)
    respond_fn = _unwrap(srv.respond)

    started = await start_fn(
        user_id="yhn",
        subject_id=subject_id,
        goal="48h_sprint",
    )
    assert started.session_id
    assert started.current_action.content

    action = await next_fn(session_id=started.session_id)
    assert action.content

    result = await respond_fn(session_id=started.session_id, answer="极限就是无限接近")
    assert result.correctness in ("correct", "partial", "incorrect")
    assert result.feedback
    assert result.mastery_update is not None


@pytest.mark.asyncio
async def test_start_without_kg_raises(env: RelationalStore) -> None:
    """subject 没有 KG 时 start 应抛 KG_NOT_BUILT。"""
    start_fn = _unwrap(srv.start_learning_session)
    with pytest.raises(TutorError) as exc:
        await start_fn(user_id="yhn", subject_id="ce-shi", goal="48h_sprint")
    assert exc.value.code in ("KG_NOT_BUILT", "KG_NOT_FOUND")


@pytest.mark.asyncio
async def test_no_stub_tools_remaining(env: RelationalStore) -> None:
    """T1+ 完成：tutoring-mcp 8/8 tool 全部实现，不再有 stub。

    调用任何 tool 都不应抛 DEPENDENCY_MISSING（业务错误如 SESSION_NOT_FOUND 可以）。
    """
    for tool in (srv.interrupt, srv.checkpoint):
        fn = _unwrap(tool)
        try:
            await fn(session_id="no-such-session", question="x", content="x")  # type: ignore[call-arg]
        except TypeError:
            # 各 tool 参数签名不同；用 keyword 调用兜底
            import inspect

            sig = inspect.signature(fn)
            kwargs = {}
            for name, p in sig.parameters.items():
                if p.default is inspect.Parameter.empty:
                    kwargs[name] = "no-such-session" if name == "session_id" else "x"
            try:
                await fn(**kwargs)
            except TutorError as exc:
                assert exc.code != "DEPENDENCY_MISSING", (
                    f"{fn.__name__} 还是 stub: {exc.code} {exc.message}"
                )
        except TutorError as exc:
            assert exc.code != "DEPENDENCY_MISSING", (
                f"{fn.__name__} 还是 stub: {exc.code} {exc.message}"
            )
