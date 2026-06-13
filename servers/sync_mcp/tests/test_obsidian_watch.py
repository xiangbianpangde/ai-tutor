"""obsidian_watch poll_changes 契约测试。

poll_changes(vault_path, subject_id, since_ts) → list[ChangeEvent]
- 返回 since_ts 之后 mtime 变化的、匹配 subject 的 md 文件
- event: created / modified（基于是否在 known_files 里——简化版只看 mtime > since）
- 忽略 .obsidian / .trash 等元目录
- since_ts=None → 返回全部匹配文件（首次扫描）
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from shared.errors import TutorError


def _write(vault: Path, rel: str, content: str = "x", mtime: datetime | None = None) -> Path:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    if mtime:
        ts = mtime.timestamp()
        os.utime(p, (ts, ts))
    return p


def test_poll_first_scan_returns_all_matching(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian_watch import poll_changes

    vault = tmp_path / "v"
    vault.mkdir()
    _write(vault, "ml-a.md")
    _write(vault, "ml-b.md")
    _write(vault, "other.md")  # 不匹配 subject

    changes = poll_changes(vault_path=vault, subject_id="ml", since_ts=None)
    names = {c["filename"] for c in changes}
    assert "ml-a.md" in names
    assert "ml-b.md" in names
    assert "other.md" not in names


def test_poll_only_returns_changed_since(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian_watch import poll_changes

    vault = tmp_path / "v"
    vault.mkdir()
    old = datetime.utcnow() - timedelta(hours=2)
    _write(vault, "ml-old.md", mtime=old)
    # since = 1 小时前 → 只有新文件被返回
    since = datetime.utcnow() - timedelta(hours=1)
    _write(vault, "ml-new.md")  # 现在写的

    changes = poll_changes(vault_path=vault, subject_id="ml", since_ts=since)
    names = {c["filename"] for c in changes}
    assert "ml-new.md" in names
    assert "ml-old.md" not in names


def test_poll_ignores_meta_dirs(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian_watch import poll_changes

    vault = tmp_path / "v"
    vault.mkdir()
    _write(vault, ".obsidian/ml-template.md")
    _write(vault, ".trash/ml-deleted.md")
    _write(vault, "real/ml-note.md")

    changes = poll_changes(vault_path=vault, subject_id="ml", since_ts=None)
    paths = {c["relative_path"] for c in changes}
    assert all("obsidian" not in p and "trash" not in p for p in paths)
    assert any("ml-note" in c["filename"] for c in changes)


def test_poll_change_event_has_fields(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian_watch import poll_changes

    vault = tmp_path / "v"
    vault.mkdir()
    _write(vault, "ml-x.md", content="内容")

    changes = poll_changes(vault_path=vault, subject_id="ml", since_ts=None)
    assert changes
    c = changes[0]
    assert "filename" in c
    assert "relative_path" in c
    assert "modified_at" in c
    assert "event" in c  # created / modified


def test_poll_empty_when_no_match(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian_watch import poll_changes

    vault = tmp_path / "v"
    vault.mkdir()
    _write(vault, "unrelated.md")
    assert poll_changes(vault_path=vault, subject_id="ml", since_ts=None) == []


def test_poll_missing_vault_raises(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian_watch import poll_changes

    with pytest.raises(TutorError) as exc:
        poll_changes(vault_path=tmp_path / "no-such", subject_id="ml", since_ts=None)
    assert exc.value.code == "CORPUS_NOT_FOUND"


def test_poll_sorted_by_mtime_desc(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian_watch import poll_changes

    vault = tmp_path / "v"
    vault.mkdir()
    p1 = _write(vault, "ml-1.md", mtime=datetime.utcnow() - timedelta(minutes=10))
    p2 = _write(vault, "ml-2.md", mtime=datetime.utcnow())

    changes = poll_changes(vault_path=vault, subject_id="ml", since_ts=None)
    assert changes[0]["filename"] == "ml-2.md"
