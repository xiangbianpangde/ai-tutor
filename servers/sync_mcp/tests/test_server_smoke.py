"""sync-mcp server tool 注册 + 调用 smoke test。"""
from __future__ import annotations

from pathlib import Path

import pytest

from servers.sync_mcp import server as srv


def _unwrap(tool):
    return getattr(tool, "fn", None) or getattr(tool, "func", None) or tool


@pytest.mark.asyncio
async def test_all_tools_registered() -> None:
    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    for expected in [
        "push_to_obsidian",
        "pull_homework_from_obsidian",
        "push_artifacts",         # GitHub stub
        "init_subject_repo",      # GitHub stub
        "watch_obsidian",         # 长运行 stub
        "health",
    ]:
        assert expected in names, f"missing tool: {expected}"


@pytest.mark.asyncio
async def test_push_tool_round_trip(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    src = tmp_path / "x.md"
    src.write_text("hello", encoding="utf-8")

    fn = _unwrap(srv.push_to_obsidian)
    result = await fn(
        vault_path=str(vault),
        subject_id="ml-demo",
        artifacts=[{"uri": f"file:///{src.as_posix()}", "mime_type": "text/markdown", "size_bytes": 5}],
    )
    assert result["pushed_count"] == 1
    assert (vault / "AI-Tutor" / "ml-demo" / "x.md").exists()


@pytest.mark.asyncio
async def test_pull_tool_round_trip(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    p = vault / "ml-note.md"
    p.write_text("# 笔记内容", encoding="utf-8")

    fn = _unwrap(srv.pull_homework_from_obsidian)
    result = await fn(vault_path=str(vault), subject_id="ml")
    assert len(result) == 1
    assert result[0]["filename"] == "ml-note.md"
    assert "笔记内容" in result[0]["content"]


@pytest.mark.asyncio
async def test_init_subject_repo_creates_local_repo(tmp_path: Path, monkeypatch) -> None:
    """S2: init_subject_repo 已实现，创建本地 git 仓库。"""
    monkeypatch.setenv("AI_TUTOR_GIT_ROOT", str(tmp_path / "repos"))
    fn = _unwrap(srv.init_subject_repo)
    result = await fn(user_id="yhn", subject_id="ml")
    assert Path(result["repo_path"], ".git").exists()
    assert result["was_existing"] is False


@pytest.mark.asyncio
async def test_push_artifacts_commits_to_local_repo(tmp_path: Path, monkeypatch) -> None:
    """S2: push_artifacts 已实现，提交到本地 git 仓库。"""
    monkeypatch.setenv("AI_TUTOR_GIT_ROOT", str(tmp_path / "repos"))
    src = tmp_path / "notes.md"
    src.write_text("# 笔记", encoding="utf-8")

    fn = _unwrap(srv.push_artifacts)
    result = await fn(
        subject_id="ml",
        artifacts=[{"uri": f"file:///{src.as_posix()}", "mime_type": "text/markdown", "size_bytes": 5}],
        commit_message="test commit",
        user_id="yhn",
    )
    assert result["commit_sha"]
    assert result["files_committed"] == 1
    assert result["pushed_remote"] is False


@pytest.mark.asyncio
async def test_watch_obsidian_polls_changes(tmp_path: Path) -> None:
    """S2: watch_obsidian 已实现，轮询返回变更文件。"""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "ml-note.md").write_text("内容", encoding="utf-8")

    fn = _unwrap(srv.watch_obsidian)
    result = await fn(vault_path=str(vault), subject_id="ml")
    assert isinstance(result, list)
    assert any("ml-note" in c["filename"] for c in result)


@pytest.mark.asyncio
async def test_health() -> None:
    fn = _unwrap(srv.health)
    out = await fn()
    assert out["ok"] is True
    assert out["server"] == "sync-mcp"
