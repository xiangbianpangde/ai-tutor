"""push_to_obsidian 契约测试。

push_to_obsidian(vault_path, subject_id, artifacts, subdir="AI-Tutor")
- 把 ArtifactURI 列表里的本地文件复制到 vault_path/subdir/{subject_id}/ 下
- 自动建子目录
- 同名文件：默认覆盖；选 skip_existing 时跳过
- vault_path 不存在 → 抛 CORPUS_NOT_FOUND
- artifacts 中的 file:// URI 解析正确
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.errors import TutorError
from shared.schemas import ArtifactURI


def _make_artifact(tmp_path: Path, name: str, content: str = "hello") -> ArtifactURI:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return ArtifactURI(
        uri=f"file:///{p.as_posix()}",
        mime_type="text/markdown",
        size_bytes=p.stat().st_size,
    )


def test_push_copies_files_to_vault(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import push_to_obsidian

    vault = tmp_path / "my-vault"
    vault.mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    a1 = _make_artifact(src_dir, "mindmap.mmd", "graph TD\n  A-->B")
    a2 = _make_artifact(src_dir, "notes.md", "# 笔记\n\n正文")

    result = push_to_obsidian(
        vault_path=vault, subject_id="ml-demo", artifacts=[a1, a2]
    )
    target_dir = vault / "AI-Tutor" / "ml-demo"
    assert (target_dir / "mindmap.mmd").exists()
    assert (target_dir / "notes.md").exists()
    assert (target_dir / "notes.md").read_text(encoding="utf-8") == "# 笔记\n\n正文"
    assert result.pushed_count == 2
    assert len(result.target_files) == 2


def test_push_respects_custom_subdir(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import push_to_obsidian

    vault = tmp_path / "v"
    vault.mkdir()
    src = tmp_path / "x.md"
    src.write_text("x", encoding="utf-8")
    artifact = ArtifactURI(
        uri=f"file:///{src.as_posix()}", mime_type="text/markdown", size_bytes=1
    )
    result = push_to_obsidian(
        vault_path=vault,
        subject_id="ml",
        artifacts=[artifact],
        subdir="07. 学习/Auto-Gen",
    )
    assert (vault / "07. 学习" / "Auto-Gen" / "ml" / "x.md").exists()


def test_push_overwrites_by_default(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import push_to_obsidian

    vault = tmp_path / "v"
    vault.mkdir()
    # 先在目标位置放一个旧文件
    target = vault / "AI-Tutor" / "ml" / "x.md"
    target.parent.mkdir(parents=True)
    target.write_text("OLD", encoding="utf-8")

    src = tmp_path / "x.md"
    src.write_text("NEW", encoding="utf-8")
    artifact = ArtifactURI(
        uri=f"file:///{src.as_posix()}", mime_type="text/markdown", size_bytes=3
    )
    result = push_to_obsidian(
        vault_path=vault, subject_id="ml", artifacts=[artifact],
    )
    assert target.read_text(encoding="utf-8") == "NEW"
    assert result.skipped_count == 0


def test_push_skip_existing(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import push_to_obsidian

    vault = tmp_path / "v"
    vault.mkdir()
    target = vault / "AI-Tutor" / "ml" / "x.md"
    target.parent.mkdir(parents=True)
    target.write_text("OLD", encoding="utf-8")

    src = tmp_path / "x.md"
    src.write_text("NEW", encoding="utf-8")
    artifact = ArtifactURI(
        uri=f"file:///{src.as_posix()}", mime_type="text/markdown", size_bytes=3
    )
    result = push_to_obsidian(
        vault_path=vault, subject_id="ml", artifacts=[artifact],
        on_conflict="skip",
    )
    assert target.read_text(encoding="utf-8") == "OLD"  # 未覆盖
    assert result.skipped_count == 1
    assert result.pushed_count == 0


def test_push_missing_vault_raises(tmp_path: Path) -> None:
    from servers.sync_mcp.obsidian import push_to_obsidian

    nonexistent = tmp_path / "no-such-vault"
    src = tmp_path / "x.md"
    src.write_text("x", encoding="utf-8")
    artifact = ArtifactURI(
        uri=f"file:///{src.as_posix()}", mime_type="text/markdown", size_bytes=1
    )
    with pytest.raises(TutorError) as exc:
        push_to_obsidian(
            vault_path=nonexistent, subject_id="ml", artifacts=[artifact]
        )
    assert exc.value.code == "CORPUS_NOT_FOUND"


def test_push_missing_artifact_source_records_failure(tmp_path: Path) -> None:
    """artifact 指向不存在的文件 → 失败列表记录，其他继续。"""
    from servers.sync_mcp.obsidian import push_to_obsidian

    vault = tmp_path / "v"
    vault.mkdir()
    good = tmp_path / "good.md"
    good.write_text("ok", encoding="utf-8")
    bad_artifact = ArtifactURI(
        uri="file:///nonexistent/zzz.md", mime_type="text/markdown", size_bytes=0
    )
    good_artifact = ArtifactURI(
        uri=f"file:///{good.as_posix()}", mime_type="text/markdown", size_bytes=2
    )

    result = push_to_obsidian(
        vault_path=vault, subject_id="ml", artifacts=[bad_artifact, good_artifact]
    )
    assert result.pushed_count == 1
    assert len(result.failed) == 1
    assert "zzz.md" in result.failed[0]


def test_push_handles_windows_drive_letter_uri(tmp_path: Path) -> None:
    """Windows 路径 file:///C:/... 应正确解析。"""
    from servers.sync_mcp.obsidian import push_to_obsidian

    vault = tmp_path / "v"
    vault.mkdir()
    src = tmp_path / "win.md"
    src.write_text("win", encoding="utf-8")
    # 模拟 demo 脚本写出的 URI 风格
    artifact = ArtifactURI(
        uri=f"file:///{src.as_posix()}",  # POSIX 风格 forward-slash
        mime_type="text/markdown", size_bytes=3,
    )
    result = push_to_obsidian(
        vault_path=vault, subject_id="ml", artifacts=[artifact]
    )
    assert result.pushed_count == 1
