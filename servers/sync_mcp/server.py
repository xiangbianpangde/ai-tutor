"""sync-mcp FastMCP server 入口。

已实现的 tool:
- push_to_obsidian            把 digest/notes/quiz 等产物拷贝到 Obsidian vault
- pull_homework_from_obsidian 递归扫描 vault 中跟 subject 相关的 markdown
- health

Stub（待 S2+/S3 切片）:
- push_artifacts        通过 git push 推到 GitHub（PyGithub + git）
- init_subject_repo     创建 GitHub 远程仓库
- watch_obsidian        watchdog 长运行 + MCP notifications/progress 推送变更
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from shared.logging_config import configure_logging, get_logger

from .git_sync import (
    commit_artifacts as commit_impl,
)
from .git_sync import (
    init_repo as init_repo_impl,
)
from .git_sync import (
    push_to_remote as push_remote_impl,
)
from .obsidian import (
    pull_homework_from_obsidian as pull_impl,
)
from .obsidian import (
    push_to_obsidian as push_impl,
)
from .obsidian_watch import poll_changes as poll_impl

configure_logging()
logger = get_logger("sync_mcp.server")

mcp: FastMCP = FastMCP("sync-mcp")


# --------------------------------------------------------------------------- #
# 已实现的 tool
# --------------------------------------------------------------------------- #


@mcp.tool()
async def push_to_obsidian(
    vault_path: str,
    subject_id: str,
    artifacts: list[dict],
    subdir: str = "AI-Tutor",
    on_conflict: str = "overwrite",
) -> dict[str, Any]:
    """把 ArtifactURI 列表拷贝到 Obsidian vault 的指定子目录。

    Args:
        vault_path: Obsidian vault 绝对路径
        subject_id: 用作子目录名，目标 = {vault}/{subdir}/{subject_id}/
        artifacts: ArtifactURI 列表（dict 形式：{uri, mime_type, size_bytes}）
        subdir:    vault 内根目录，默认 "AI-Tutor"
        on_conflict: "overwrite" (默认) | "skip"
    """
    from shared.schemas import ArtifactURI

    typed = [ArtifactURI.model_validate(a) for a in artifacts]
    result = push_impl(
        vault_path=Path(vault_path),
        subject_id=subject_id,
        artifacts=typed,
        subdir=subdir,
        on_conflict=on_conflict,  # type: ignore[arg-type]
    )
    return {
        "target_dir": str(result.target_dir),
        "pushed_count": result.pushed_count,
        "skipped_count": result.skipped_count,
        "target_files": result.target_files,
        "failed": result.failed,
    }


@mcp.tool()
async def pull_homework_from_obsidian(
    vault_path: str,
    subject_id: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """递归扫描 vault，找出与 subject 关联的 markdown 文件。

    匹配方式（任一命中即收）:
    1. 文件名包含 subject_id
    2. frontmatter 中 subject_id / subject 字段
    3. frontmatter tags 含 subject_id

    Returns:
        按 modified_at 倒序排列的列表，每项 {filename, relative_path, content, modified_at}
    """
    out = pull_impl(
        vault_path=Path(vault_path),
        subject_id=subject_id,
        limit=limit,
    )
    return [
        {
            "filename": h.filename,
            "relative_path": h.relative_path,
            "content": h.content,
            "modified_at": h.modified_at.isoformat(),
        }
        for h in out
    ]


@mcp.tool()
async def health() -> dict[str, Any]:
    """轻量自检。"""
    return {"ok": True, "server": "sync-mcp", "version": "0.1.0"}


# --------------------------------------------------------------------------- #
# git 同步 tool（S2）
# --------------------------------------------------------------------------- #


def _repo_root() -> Path:
    root = os.environ.get("AI_TUTOR_GIT_ROOT", str(Path("data") / "git_repos"))
    return Path(root)


@mcp.tool()
async def init_subject_repo(
    user_id: str,
    subject_id: str,
    github_org: str = "my-ai-learning",
    remote_url: str | None = None,
) -> dict[str, Any]:
    """为 subject 初始化一个本地 git 仓库（可选关联 GitHub remote）。

    本地仓库路径：{AI_TUTOR_GIT_ROOT}/{github_org}__{user_id}-{subject_id}/
    remote_url 给定时（如 https://<token>@github.com/org/repo.git）会配 origin，
    之后 push_artifacts 可推到远程；不给则纯本地版本控制。
    """
    repo = _repo_root() / f"{github_org}__{user_id}-{subject_id}"
    result = init_repo_impl(repo_path=repo, remote_url=remote_url)
    return {
        "repo_path": result["repo_path"],
        "remote": result["remote"],
        "was_existing": result["was_existing"],
    }


@mcp.tool()
async def push_artifacts(
    subject_id: str,
    artifacts: list[dict],
    commit_message: str = "auto: sync ai-tutor artifacts",
    user_id: str = "default",
    github_org: str = "my-ai-learning",
    push_remote: bool = False,
) -> dict[str, Any]:
    """把 artifact 提交到 subject 的本地 git 仓库（可选 push 到远程）。

    artifacts: ArtifactURI dict 列表（{uri, mime_type, size_bytes}）。
    push_remote=True 时尝试 git push origin main（需 init_subject_repo 配过 remote + 凭证）。
    """
    from shared.schemas import ArtifactURI

    repo = _repo_root() / f"{github_org}__{user_id}-{subject_id}"
    if not (repo / ".git").exists():
        # 自动 init（幂等）
        init_repo_impl(repo_path=repo)

    typed = [ArtifactURI.model_validate(a) for a in artifacts]
    result = commit_impl(
        repo_path=repo, artifacts=typed,
        message=commit_message, subdir=subject_id,
    )
    pushed = False
    if push_remote and result.get("commit_sha"):
        push_remote_impl(repo_path=repo)
        pushed = True
    return {
        "repo_path": str(repo),
        "commit_sha": result["commit_sha"],
        "files_committed": result["files_committed"],
        "failed": result.get("failed", []),
        "pushed_remote": pushed,
    }


@mcp.tool()
async def watch_obsidian(
    vault_path: str,
    subject_id: str,
    since_iso: str | None = None,
) -> list[dict[str, Any]]:
    """轮询一次 vault，返回自 since_iso 之后变更的匹配 subject 的 md 文件。

    注意：MCP host 应周期性调用此 tool（host 侧定时），把上次返回的最大
    modified_at 作为下次 since_iso。真持续长运行（notifications/progress）见
    obsidian_watch.watch()，需 host 支持流式 tool。
    """
    from datetime import datetime

    since = None
    if since_iso:
        try:
            since = datetime.fromisoformat(since_iso)
        except ValueError:
            since = None
    return poll_impl(vault_path=Path(vault_path), subject_id=subject_id, since_ts=since)


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #


def main() -> None:
    import sys

    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]
    logger.info("sync_mcp.start", transport=transport)
    if transport == "http":
        mcp.run(transport="sse", host="0.0.0.0", port=8004)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
