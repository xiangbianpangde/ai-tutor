"""backend.middleware.FileManager 测试（M-017 / spec 03 功能2）。"""
from __future__ import annotations

import pytest

from backend.middleware import FileManager
from shared.errors import TutorError


@pytest.fixture
def fm(tmp_path):
    return FileManager(tmp_path)


def test_human_readable_layout_no_uuid(fm, tmp_path):
    """spec 场景1：data/{user}/{subject}/{kind}/file，路径人类可读无 UUID。"""
    p = fm.write_text("yhn", "gaoshu", "corpora", "gaoshu_xiace.md", "内容")
    rel = p.relative_to(tmp_path).as_posix()
    assert rel == "yhn/gaoshu/corpora/gaoshu_xiace.md"
    assert fm.read_text("yhn", "gaoshu", "corpora", "gaoshu_xiace.md") == "内容"


def test_kg_version_dir(fm, tmp_path):
    d = fm.kg_version_dir("yhn", "gaoshu", 1)
    assert d.relative_to(tmp_path).as_posix() == "yhn/gaoshu/knowledge_graphs/v1"


def test_export_path(fm, tmp_path):
    """spec 场景2：导出到 exports/。"""
    p = fm.write_text("yhn", "gaoshu", "exports", "review_plan_2026-05-29.md", "计划")
    assert p.relative_to(tmp_path).as_posix() == "yhn/gaoshu/exports/review_plan_2026-05-29.md"


def test_list_files(fm):
    fm.write_text("yhn", "ml", "corpora", "a.md", "x")
    fm.write_text("yhn", "ml", "corpora", "b.md", "y")
    names = [p.name for p in fm.list_files("yhn", "ml", "corpora")]
    assert names == ["a.md", "b.md"]
    assert fm.list_files("yhn", "ml", "output") == []  # 不存在目录返回空


def test_unknown_kind_rejected(fm):
    with pytest.raises(TutorError) as ei:
        fm.dir_for("yhn", "gaoshu", "secrets")
    assert ei.value.code == "INVALID_PATH"


@pytest.mark.parametrize("evil", ["..", "../etc", "a/b", "a\\b", "", "."])
def test_path_traversal_blocked(fm, evil):
    """目录穿越/非法段一律拒绝。"""
    with pytest.raises(TutorError):
        fm.path_for("yhn", evil, "corpora", "x.md")
    with pytest.raises(TutorError):
        fm.write_text("yhn", "gaoshu", "corpora", evil, "x")
