"""git 同步 — 用 git CLI subprocess 把 artifact 存进版本库。

零额外依赖（不要 PyGithub）。GitHub remote 通过标准 git remote + push 实现；
本地 git init + commit 不需要任何 token。

接口:
- init_repo(repo_path, remote_url=None)         幂等 git init + 配 user + 可选 remote
- commit_artifacts(repo_path, artifacts, ...)    copy + add + commit，返回 sha
- push_to_remote(repo_path, branch)              git push（需 remote + 凭证）
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.schemas import ArtifactURI

logger = get_logger("sync_mcp.git_sync")

_WIN_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")
_DEFAULT_USER = ("ai-tutor", "ai-tutor@localhost")


class _GitResult:
    """对 subprocess.CompletedProcess 的轻量替代，绕开 Python 3.14 subprocess
    在 Windows + text=True + 中文 stdout 下 _readerthread 解码崩溃的 bug。
    """

    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _run(repo: Path, *args: str, check: bool = True) -> _GitResult:
    """bytes mode 跑 git，手动 utf-8 decode 防 Windows GBK 解码后台线程崩溃。"""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=False,  # 显式 bytes mode
    )
    stdout = (proc.stdout or b"").decode("utf-8", errors="replace")
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise TutorError(
            "DEPENDENCY_MISSING",
            hint=f"git {' '.join(args)} 失败: {stderr.strip()[:300]}",
        )
    return _GitResult(returncode=proc.returncode, stdout=stdout, stderr=stderr)


def _uri_to_path(uri: str) -> Path:
    if _WIN_DRIVE_RE.match(uri):
        return Path(uri)
    parsed = urlparse(uri)
    raw = parsed.path if parsed.scheme == "file" else uri
    if _WIN_DRIVE_RE.match(raw.lstrip("/")):
        raw = raw.lstrip("/")
    return Path(raw)


def init_repo(*, repo_path: Path | str, remote_url: str | None = None) -> dict[str, Any]:
    """幂等地 git init + 配 user + 可选加 remote origin。"""
    repo = Path(repo_path)
    repo.mkdir(parents=True, exist_ok=True)
    already = (repo / ".git").exists()
    if not already:
        _run(repo, "init")
        # 默认分支统一 main
        _run(repo, "checkout", "-B", "main", check=False)

    # 配 user（若未配）—— 否则 commit 报错
    name = _run(repo, "config", "user.name", check=False).stdout.strip()
    if not name:
        _run(repo, "config", "user.name", _DEFAULT_USER[0])
        _run(repo, "config", "user.email", _DEFAULT_USER[1])

    remote = None
    if remote_url:
        # 若已有 origin 先移除再加（幂等）
        existing = _run(repo, "remote", check=False).stdout.split()
        if "origin" in existing:
            _run(repo, "remote", "remove", "origin", check=False)
        _run(repo, "remote", "add", "origin", remote_url)
        remote = remote_url

    logger.info("git.init", repo=str(repo), already=already, remote=remote)
    return {"initialized": True, "repo_path": str(repo), "remote": remote, "was_existing": already}


def commit_artifacts(
    *,
    repo_path: Path | str,
    artifacts: list[ArtifactURI],
    message: str,
    subdir: str = "",
) -> dict[str, Any]:
    """把 artifact 文件复制进 repo/subdir，git add + commit。"""
    repo = Path(repo_path)
    if not (repo / ".git").exists():
        raise TutorError("CORPUS_NOT_FOUND", hint=f"不是 git 仓库: {repo}（先 init_repo）")

    target_dir = repo / subdir if subdir else repo
    target_dir.mkdir(parents=True, exist_ok=True)

    committed = 0
    failed: list[str] = []
    for art in artifacts:
        try:
            src = _uri_to_path(art.uri)
            if not src.exists():
                failed.append(f"source 不存在: {src}")
                continue
            shutil.copy2(src, target_dir / src.name)
            committed += 1
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{art.uri}: {exc}")

    if committed == 0:
        return {"commit_sha": None, "files_committed": 0, "failed": failed}

    _run(repo, "add", "-A")
    # 检查有无实际变更
    status = _run(repo, "status", "--porcelain").stdout.strip()
    if not status:
        return {"commit_sha": None, "files_committed": 0, "failed": failed,
                "note": "无变更，跳过 commit"}

    _run(repo, "commit", "-m", message)
    sha = _run(repo, "rev-parse", "HEAD").stdout.strip()

    logger.info("git.commit", repo=str(repo), sha=sha[:8], files=committed, failed=len(failed))
    return {"commit_sha": sha, "files_committed": committed, "failed": failed}


def push_to_remote(
    *, repo_path: Path | str, branch: str = "main",
) -> dict[str, Any]:
    """git push origin <branch>。需 remote 已配 + 凭证（token in URL 或 credential helper）。"""
    repo = Path(repo_path)
    if not (repo / ".git").exists():
        raise TutorError("CORPUS_NOT_FOUND", hint=str(repo))
    remotes = _run(repo, "remote", check=False).stdout.split()
    if "origin" not in remotes:
        raise TutorError(
            "DEPENDENCY_MISSING",
            hint="未配置 origin remote。先 init_subject_repo(github_org=...) 或手动 git remote add。",
        )
    proc = _run(repo, "push", "-u", "origin", branch, check=False)
    if proc.returncode != 0:
        raise TutorError(
            "PLUGIN_NOT_AVAILABLE",
            hint=f"git push 失败（检查凭证 / 网络）: {proc.stderr.strip()[:300]}",
        )
    logger.info("git.push", repo=str(repo), branch=branch)
    return {"pushed": True, "branch": branch}
