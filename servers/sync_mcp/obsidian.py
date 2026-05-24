"""Obsidian vault 同步 — push/pull 实现。

push_to_obsidian:
- 把 ArtifactURI 列表（file:// 协议）复制到 vault_path/subdir/{subject_id}/
- on_conflict ∈ {overwrite (默认), skip}
- 失败的 artifact 记入 failed 列表，整体不抛错（除 vault 缺失）

pull_homework_from_obsidian:
- 递归扫描 vault，按多种方式过滤 subject_id：
  1. 文件名包含 subject_id
  2. frontmatter 中含 subject_id 字段
  3. tags 含 subject_id（去除 hyphen 后比较）
- 忽略 .obsidian / .git / .trash 等元目录

后续切片可加: watch（watchdog 长运行 tool）+ Obsidian wiki link 解析。
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.schemas import ArtifactURI

logger = get_logger("sync_mcp.obsidian")


_WIN_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")
_IGNORED_DIRS = {".obsidian", ".trash", ".git", "node_modules", ".vscode"}


@dataclass
class PushResult:
    target_dir: Path
    pushed_count: int = 0
    skipped_count: int = 0
    target_files: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


@dataclass
class HomeworkFile:
    filename: str
    relative_path: str
    content: str
    modified_at: datetime


def _uri_to_path(uri: str) -> Path:
    """`file:///C:/path/x.md` → Path('C:/path/x.md')。"""
    if _WIN_DRIVE_RE.match(uri):
        return Path(uri)
    parsed = urlparse(uri)
    if parsed.scheme in ("", "file"):
        raw = parsed.path if parsed.scheme == "file" else uri
        if _WIN_DRIVE_RE.match(raw.lstrip("/")):
            raw = raw.lstrip("/")
        return Path(raw)
    raise ValueError(f"不支持的 URI scheme: {uri}")


def push_to_obsidian(
    *,
    vault_path: Path | str,
    subject_id: str,
    artifacts: list[ArtifactURI],
    subdir: str = "AI-Tutor",
    on_conflict: Literal["overwrite", "skip"] = "overwrite",
) -> PushResult:
    """把 artifact 文件复制到 Obsidian vault 的指定子目录。"""
    vault = Path(vault_path)
    if not vault.exists() or not vault.is_dir():
        raise TutorError("CORPUS_NOT_FOUND", hint=f"Obsidian vault 不存在: {vault}")

    target_dir = vault / subdir / subject_id
    target_dir.mkdir(parents=True, exist_ok=True)
    result = PushResult(target_dir=target_dir)

    for art in artifacts:
        try:
            src = _uri_to_path(art.uri)
            if not src.exists():
                result.failed.append(f"source 不存在: {src}")
                continue
            dst = target_dir / src.name
            if dst.exists() and on_conflict == "skip":
                result.skipped_count += 1
                continue
            shutil.copy2(src, dst)
            result.pushed_count += 1
            result.target_files.append(str(dst))
        except Exception as exc:  # noqa: BLE001
            logger.warning("push.failed", uri=art.uri, error=str(exc))
            result.failed.append(f"{art.uri}: {type(exc).__name__}: {exc}")

    logger.info(
        "push.done",
        target=str(target_dir),
        pushed=result.pushed_count,
        skipped=result.skipped_count,
        failed=len(result.failed),
    )
    return result


# --------------------------------------------------------------------------- #
# pull
# --------------------------------------------------------------------------- #


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _extract_frontmatter(text: str) -> dict[str, str]:
    """极简 frontmatter 解析：只取 key: value 行。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _matches_subject(file_path: Path, content: str, subject_id: str) -> bool:
    """三种匹配方式：文件名 / frontmatter / tag。"""
    sid_low = subject_id.lower()
    # 1. 文件名（去除 hyphen 和大小写差异）
    fname = file_path.stem.lower().replace("-", "").replace("_", "")
    if sid_low.replace("-", "").replace("_", "") in fname:
        return True
    # 2/3. frontmatter
    fm = _extract_frontmatter(content)
    if fm.get("subject_id", "").lower() == sid_low:
        return True
    if fm.get("subject", "").lower() == sid_low:
        return True
    tags = fm.get("tags", "")
    if isinstance(tags, str) and sid_low in tags.lower():
        return True
    return False


def pull_homework_from_obsidian(
    *,
    vault_path: Path | str,
    subject_id: str,
    limit: int | None = None,
) -> list[HomeworkFile]:
    """递归扫描 vault，找出与 subject_id 关联的 markdown 文件。"""
    vault = Path(vault_path)
    if not vault.exists() or not vault.is_dir():
        raise TutorError("CORPUS_NOT_FOUND", hint=f"Obsidian vault 不存在: {vault}")

    out: list[HomeworkFile] = []
    for md in vault.rglob("*.md"):
        # 跳过元目录
        if any(part in _IGNORED_DIRS for part in md.parts):
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            logger.warning("pull.read_failed", path=str(md), error=str(exc))
            continue
        if not _matches_subject(md, content, subject_id):
            continue
        try:
            mtime = datetime.fromtimestamp(md.stat().st_mtime)
        except OSError:
            mtime = datetime.utcnow()
        out.append(
            HomeworkFile(
                filename=md.name,
                relative_path=str(md.relative_to(vault)),
                content=content,
                modified_at=mtime,
            )
        )

    # 按修改时间倒序
    out.sort(key=lambda h: h.modified_at, reverse=True)
    if limit is not None:
        out = out[:limit]
    logger.info("pull.done", vault=str(vault), subject_id=subject_id, count=len(out))
    return out
