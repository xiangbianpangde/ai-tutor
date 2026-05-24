"""Obsidian vault 变更监听（基于 mtime 轮询，零额外依赖）。

设计:
- poll_changes(vault, subject, since_ts) → 自 since_ts 之后变更的匹配文件（可测核心）
- watch(vault, subject, poll_interval, on_change) → 长运行轮询循环（生产用）

不依赖 watchdog——纯 mtime 轮询足够（教学场景秒级延迟可接受）。
真要 inotify 级实时，后续切片可换 watchdog Observer。
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from shared.errors import TutorError
from shared.logging_config import get_logger

from .obsidian import _matches_subject  # 复用 pull 的匹配逻辑

logger = get_logger("sync_mcp.obsidian_watch")

_IGNORED_DIRS = {".obsidian", ".trash", ".git", "node_modules", ".vscode"}


def _now_ref() -> datetime:
    """统一的"当前时间"参考点 — 必须与 poll_changes 内 mtime
    (datetime.fromtimestamp(st_mtime)) 同时区（naive local time），否则
    BUG.4 复现：last_ts(utcnow) vs mtime(local) → UTC+8 下 8 小时错位。
    """
    return datetime.fromtimestamp(time.time())


def poll_changes(
    *,
    vault_path: Path | str,
    subject_id: str,
    since_ts: datetime | None = None,
) -> list[dict[str, Any]]:
    """扫描 vault，返回 since_ts 之后修改的匹配 subject 的 md 文件。

    since_ts=None → 返回全部匹配（首次扫描）。
    """
    vault = Path(vault_path)
    if not vault.exists() or not vault.is_dir():
        raise TutorError("CORPUS_NOT_FOUND", hint=f"vault 不存在: {vault}")

    out: list[dict[str, Any]] = []
    for md in vault.rglob("*.md"):
        if any(part in _IGNORED_DIRS for part in md.parts):
            continue
        try:
            mtime = datetime.fromtimestamp(md.stat().st_mtime)
        except OSError:
            continue
        if since_ts is not None and mtime <= since_ts:
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not _matches_subject(md, content, subject_id):
            continue
        out.append({
            "filename": md.name,
            "relative_path": str(md.relative_to(vault)),
            "modified_at": mtime.isoformat(),
            "event": "modified" if since_ts is not None else "created",
        })

    out.sort(key=lambda c: c["modified_at"], reverse=True)
    logger.info("watch.poll", vault=str(vault), subject=subject_id, changes=len(out))
    return out


def watch(
    *,
    vault_path: Path | str,
    subject_id: str,
    poll_interval_sec: int = 30,
    on_change: Callable[[list[dict[str, Any]]], None] | None = None,
    max_iterations: int | None = None,
) -> None:
    """长运行：每 poll_interval_sec 扫一次，把新变更交给 on_change 回调。

    max_iterations 用于测试（限制循环次数）；生产留 None = 无限循环。
    真实 MCP 长运行 tool 会通过 notifications/progress 推送 on_change 结果。
    """
    last_ts = _now_ref()
    iterations = 0
    while True:
        time.sleep(poll_interval_sec)
        changes = poll_changes(
            vault_path=vault_path, subject_id=subject_id, since_ts=last_ts,
        )
        if changes and on_change:
            on_change(changes)
        last_ts = _now_ref()
        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            break
