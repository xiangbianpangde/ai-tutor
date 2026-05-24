"""git_sync 契约测试（用真实临时 git repo，不碰远程）。

接口:
- init_repo(repo_path, remote_url=None) → {initialized, repo_path, remote}
- commit_artifacts(repo_path, artifacts, message, subdir) → {commit_sha, files_committed}
- push_to_remote(repo_path, branch) → {pushed, ...}  （无 remote → 抛错；真 push 需凭证）
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from shared.errors import TutorError
from shared.schemas import ArtifactURI


def _artifact(tmp: Path, name: str, content: str = "hello") -> ArtifactURI:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return ArtifactURI(uri=f"file:///{p.as_posix()}", mime_type="text/markdown", size_bytes=len(content))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    ).stdout.strip()


def test_init_repo_creates_git_dir(tmp_path: Path) -> None:
    from servers.sync_mcp.git_sync import init_repo

    repo = tmp_path / "myrepo"
    result = init_repo(repo_path=repo)
    assert result["initialized"] is True
    assert (repo / ".git").exists()


def test_init_repo_idempotent(tmp_path: Path) -> None:
    from servers.sync_mcp.git_sync import init_repo

    repo = tmp_path / "r"
    init_repo(repo_path=repo)
    # 再 init 一次不应报错
    result = init_repo(repo_path=repo)
    assert (repo / ".git").exists()


def test_init_repo_configures_user(tmp_path: Path) -> None:
    """init 后应配好 user.name/email，否则 commit 会失败。"""
    from servers.sync_mcp.git_sync import init_repo

    repo = tmp_path / "r"
    init_repo(repo_path=repo)
    name = _git(repo, "config", "user.name")
    email = _git(repo, "config", "user.email")
    assert name
    assert email


def test_init_repo_with_remote(tmp_path: Path) -> None:
    from servers.sync_mcp.git_sync import init_repo

    repo = tmp_path / "r"
    result = init_repo(repo_path=repo, remote_url="https://github.com/u/repo.git")
    assert result["remote"] == "https://github.com/u/repo.git"
    remotes = _git(repo, "remote", "-v")
    assert "github.com/u/repo" in remotes


def test_commit_artifacts_creates_commit(tmp_path: Path) -> None:
    from servers.sync_mcp.git_sync import commit_artifacts, init_repo

    repo = tmp_path / "repo"
    init_repo(repo_path=repo)
    src = tmp_path / "src"
    src.mkdir()
    a1 = _artifact(src, "notes.md", "# 笔记")
    a2 = _artifact(src, "quiz.html", "<html></html>")

    result = commit_artifacts(
        repo_path=repo, artifacts=[a1, a2],
        message="add notes + quiz", subdir="ml",
    )
    assert result["commit_sha"]
    assert result["files_committed"] == 2
    # 文件真的进了 repo
    assert (repo / "ml" / "notes.md").exists()
    assert (repo / "ml" / "quiz.html").exists()
    # git log 有这条 commit
    log = _git(repo, "log", "--oneline")
    assert "add notes + quiz" in log


def test_commit_artifacts_second_commit_has_parent(tmp_path: Path) -> None:
    from servers.sync_mcp.git_sync import commit_artifacts, init_repo

    repo = tmp_path / "repo"
    init_repo(repo_path=repo)
    src = tmp_path / "src"
    src.mkdir()

    commit_artifacts(repo_path=repo, artifacts=[_artifact(src, "a.md")], message="c1", subdir="x")
    commit_artifacts(repo_path=repo, artifacts=[_artifact(src, "b.md")], message="c2", subdir="x")

    count = _git(repo, "rev-list", "--count", "HEAD")
    assert int(count) == 2


def test_commit_no_changes_returns_no_commit(tmp_path: Path) -> None:
    """没有任何文件变更时，不应产生空 commit。"""
    from servers.sync_mcp.git_sync import commit_artifacts, init_repo

    repo = tmp_path / "repo"
    init_repo(repo_path=repo)
    result = commit_artifacts(repo_path=repo, artifacts=[], message="empty", subdir="x")
    assert result["files_committed"] == 0
    assert result["commit_sha"] is None


def test_commit_missing_source_recorded(tmp_path: Path) -> None:
    from servers.sync_mcp.git_sync import commit_artifacts, init_repo

    repo = tmp_path / "repo"
    init_repo(repo_path=repo)
    bad = ArtifactURI(uri="file:///nonexistent/zzz.md", mime_type="text/markdown", size_bytes=0)
    result = commit_artifacts(repo_path=repo, artifacts=[bad], message="x", subdir="x")
    assert result["files_committed"] == 0
    assert result["failed"]


def test_commit_on_uninitialized_repo_raises(tmp_path: Path) -> None:
    from servers.sync_mcp.git_sync import commit_artifacts

    src = tmp_path / "src"
    src.mkdir()
    with pytest.raises(TutorError) as exc:
        commit_artifacts(
            repo_path=tmp_path / "not-a-repo",
            artifacts=[_artifact(src, "a.md")],
            message="x", subdir="x",
        )
    assert exc.value.code in ("CORPUS_NOT_FOUND", "DEPENDENCY_MISSING")


def test_push_without_remote_raises(tmp_path: Path) -> None:
    from servers.sync_mcp.git_sync import init_repo, push_to_remote

    repo = tmp_path / "repo"
    init_repo(repo_path=repo)  # 无 remote
    with pytest.raises(TutorError) as exc:
        push_to_remote(repo_path=repo)
    assert exc.value.code in ("DEPENDENCY_MISSING", "PLUGIN_NOT_AVAILABLE")
