"""backend.middleware.file_manager —— 统一文件管理（M-017 / spec 03 功能2）。

替换 v1 `shared.storage.FileStore`（按 corpus_id/kg_id 等 ID 建目录，常是 UUID）为
**人类可读结构**：``{root}/{user_id}/{subject_slug}/{kind}/...``，kind ∈ corpora/knowledge_graphs/output/exports。

安全：所有路径段过 `_safe`，拒绝空 / `.` / `..` / 路径分隔符 / 空字节——防目录穿越。
"""
from __future__ import annotations

from pathlib import Path

from shared.errors import TutorError

ALLOWED_KINDS = frozenset({"corpora", "knowledge_graphs", "output", "exports"})


class FileManager:
    """按 用户/科目/类别 组织本地文件，禁 UUID 目录。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @staticmethod
    def _safe(segment: str, *, what: str) -> str:
        bad = not segment or segment in (".", "..") or any(c in segment for c in ("/", "\\", "\x00"))
        if bad:
            raise TutorError("INVALID_PATH", f"非法{what}: {segment!r}", hint="禁止空/./../路径分隔符")
        return segment

    def subject_dir(self, user_id: str, subject_slug: str) -> Path:
        return self.root / self._safe(user_id, what="user_id") / self._safe(subject_slug, what="subject")

    def dir_for(self, user_id: str, subject_slug: str, kind: str) -> Path:
        if kind not in ALLOWED_KINDS:
            raise TutorError("INVALID_PATH", f"未知类别: {kind!r}", hint=f"允许: {sorted(ALLOWED_KINDS)}")
        return self.subject_dir(user_id, subject_slug) / kind

    def path_for(self, user_id: str, subject_slug: str, kind: str, filename: str) -> Path:
        return self.dir_for(user_id, subject_slug, kind) / self._safe(filename, what="filename")

    def kg_version_dir(self, user_id: str, subject_slug: str, version: int) -> Path:
        return self.dir_for(user_id, subject_slug, "knowledge_graphs") / f"v{int(version)}"

    def write_text(
        self, user_id: str, subject_slug: str, kind: str, filename: str,
        content: str, *, encoding: str = "utf-8",
    ) -> Path:
        p = self.path_for(user_id, subject_slug, kind, filename)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return p

    def read_text(
        self, user_id: str, subject_slug: str, kind: str, filename: str, *, encoding: str = "utf-8"
    ) -> str:
        return self.path_for(user_id, subject_slug, kind, filename).read_text(encoding=encoding)

    def list_files(self, user_id: str, subject_slug: str, kind: str) -> list[Path]:
        d = self.dir_for(user_id, subject_slug, kind)
        return sorted(p for p in d.glob("*") if p.is_file()) if d.exists() else []

    def exists(self, user_id: str, subject_slug: str, kind: str, filename: str) -> bool:
        return self.path_for(user_id, subject_slug, kind, filename).exists()
