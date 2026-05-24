"""pull_homework_from_obsidian 契约测试。

三种匹配方式（任一命中即返回）:
1. 文件名包含 subject_id
2. frontmatter 中 subject_id 或 subject 字段
3. frontmatter tags 含 subject_id
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.errors import TutorError


def _write_md(vault: Path, rel: str, content: str) -> Path:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_pull_matches_by_filename(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_md(vault, "ml-notes/intro.md", "irrelevant")
    _write_md(vault, "ml-notes/词袋模型.md", "正文")  # 含中文，无 ml 关键字
    _write_md(vault, "ml-notes/ml-overview.md", "match!")  # 文件名含 ml
    _write_md(vault, "其他/cs101.md", "无关")

    out = pull_homework_from_obsidian(vault_path=vault, subject_id="ml")
    filenames = {h.filename for h in out}
    assert "ml-overview.md" in filenames
    assert "cs101.md" not in filenames


def test_pull_matches_by_frontmatter_subject(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_md(vault, "随便起的文件名.md", """---
subject_id: ml
created: 2026-05-21
---

# 词袋

正文
""")
    _write_md(vault, "其他.md", "无关")

    out = pull_homework_from_obsidian(vault_path=vault, subject_id="ml")
    assert any(h.filename == "随便起的文件名.md" for h in out)


def test_pull_matches_by_tags(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_md(vault, "笔记.md", """---
tags: 机器学习, ml-demo
---

正文
""")
    out = pull_homework_from_obsidian(vault_path=vault, subject_id="ml-demo")
    assert len(out) == 1


def test_pull_ignores_obsidian_meta_dirs(tmp_path: Path) -> None:
    """.obsidian/ 等元目录里的 .md 不应被扫描。"""
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_md(vault, ".obsidian/templates/ml-template.md", "我有 ml 关键字但是模板")
    _write_md(vault, ".trash/old-ml.md", "在回收站")
    _write_md(vault, "正常/ml-notes.md", "我应被收到")

    out = pull_homework_from_obsidian(vault_path=vault, subject_id="ml")
    assert all("obsidian" not in h.relative_path and "trash" not in h.relative_path for h in out)
    assert any("ml-notes" in h.filename for h in out)


def test_pull_sorts_by_modified_desc(tmp_path: Path) -> None:
    """结果按修改时间倒序。"""
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian
    import time
    import os

    vault = tmp_path / "vault"
    vault.mkdir()
    p1 = _write_md(vault, "ml-old.md", "old")
    time.sleep(0.05)
    p2 = _write_md(vault, "ml-new.md", "new")
    # 显式设置 mtime 确保顺序
    os.utime(p1, (p1.stat().st_atime, p2.stat().st_mtime - 10))

    out = pull_homework_from_obsidian(vault_path=vault, subject_id="ml")
    assert out[0].filename == "ml-new.md"
    assert out[1].filename == "ml-old.md"


def test_pull_respects_limit(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    vault = tmp_path / "vault"
    vault.mkdir()
    for i in range(5):
        _write_md(vault, f"ml-{i}.md", f"file {i}")

    out = pull_homework_from_obsidian(vault_path=vault, subject_id="ml", limit=3)
    assert len(out) == 3


def test_pull_missing_vault_raises(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    with pytest.raises(TutorError) as exc:
        pull_homework_from_obsidian(vault_path=tmp_path / "no-such", subject_id="x")
    assert exc.value.code == "CORPUS_NOT_FOUND"


def test_pull_empty_when_no_match(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_md(vault, "unrelated.md", "无关内容")
    out = pull_homework_from_obsidian(vault_path=vault, subject_id="ml")
    assert out == []


def test_pull_includes_content_and_relative_path(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import pull_homework_from_obsidian

    vault = tmp_path / "vault"
    vault.mkdir()
    p = _write_md(vault, "sub/ml-test.md", "完整内容\n第二行")
    out = pull_homework_from_obsidian(vault_path=vault, subject_id="ml")
    assert len(out) == 1
    h = out[0]
    assert "完整内容" in h.content
    assert "sub" in h.relative_path
    assert h.modified_at is not None
