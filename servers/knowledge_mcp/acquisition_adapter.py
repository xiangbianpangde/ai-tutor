"""acquire_subject 的适配层。

签名（v3.0 spec 一致）：
    acquire(*, subject, version, sources: list[AcquireSource], ...)

`AcquireSource.type` 决定走哪条采集路径：
- file:  本地 pdf/md/txt（spine v1 已实现）
- web:   research_tool.pipeline 的 Collect+Clean（**待接入**）
- video: yt-dlp + whisper（**待接入**）
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse  # noqa: F401  保留用于未来 http(s) 源

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import Corpus as CorpusRow
from shared.schemas import CorpusManifest, CorpusSource
from shared.slug import slugify_dash as _slugify
from shared.storage import FileStore, RelationalStore

logger = get_logger("knowledge_mcp.acquisition")


# --------------------------------------------------------------------------- #
# AcquireSource: 显式声明每条采集来源的类型
# --------------------------------------------------------------------------- #


@dataclass
class AcquireSource:
    type: Literal["file", "web", "video"]
    uri: str
    # 仅 file(pdf) 生效：True 时先 mineru 抽源语言 md 再翻成中文（外文教材）
    translate: bool = False
    # 仅 web 生效：True 时 LLM 把主题拆 3-5 个互补子面分别采集后归并（#9 覆盖不足）
    deepen: bool = False


_WIN_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")


def _corpus_id(subject: str, version: str | None) -> str:
    digest = hashlib.sha1(f"{subject}|{version or 'auto'}|{datetime.utcnow()}".encode()).hexdigest()[:10]
    return f"{_slugify(subject)}-{digest}"


# --------------------------------------------------------------------------- #
# file 路径解析
# --------------------------------------------------------------------------- #


def _resolve_file(source_uri: str) -> tuple[Path, str]:
    """将 file://... 或本地路径解析为 (绝对路径, 后缀)。

    支持: `C:\\path\\x.md`、`/abs/path.md`、`./rel.md`、`file:///path/x.md`。
    Windows 盘符路径会被 urlparse 误判 scheme，所以先用 regex 直查。
    """
    if _WIN_DRIVE_RE.match(source_uri):
        path = Path(source_uri).expanduser()
    else:
        parsed = urlparse(source_uri)
        if parsed.scheme in ("", "file"):
            raw = parsed.path if parsed.scheme == "file" else source_uri
            # file:///C:/... → parsed.path == "/C:/..."；Windows 需剥前导 /
            if _WIN_DRIVE_RE.match(raw.lstrip("/")):
                raw = raw.lstrip("/")
            path = Path(raw).expanduser()
        else:
            raise TutorError(
                "DEPENDENCY_MISSING",
                hint=f"file 源只支持本地路径或 file://，收到 scheme={parsed.scheme!r}",
            )
    if not path.exists():
        raise TutorError("CORPUS_NOT_FOUND", hint=f"文件不存在: {path}")
    return path.resolve(), path.suffix.lstrip(".").lower()


def _convert_pdf(
    pdf: Path, out_dir: Path, mineru_cmd: str | None, *, translate: bool = False
) -> Path:
    """PDF → markdown，委托 pdf_parser.parse_pdf。

    translate=True 时 mineru 抽源语言 md → 树内 md_translator 译成中文；默认 False
    （中文教材直接 mineru 抽中文）。mineru 为隔离 CLI，翻译为树内（DeepSeek）。
    """
    from .pdf_parser import parse_pdf

    return parse_pdf(
        pdf, out_dir, translate=translate, mineru_cmd=mineru_cmd or "mineru"
    )


# --------------------------------------------------------------------------- #
# 各 source 类型的处理
# --------------------------------------------------------------------------- #


def _acquire_file(
    src: AcquireSource, corpus_dir: Path, mineru_cmd: str | None
) -> tuple[CorpusSource, Path]:
    src_path, fmt = _resolve_file(src.uri)
    if fmt == "pdf":
        md_path = _convert_pdf(src_path, corpus_dir, mineru_cmd, translate=src.translate)
        return (
            CorpusSource(
                type="textbook",
                format="pdf",
                original_file=str(src_path),
                converted_file=str(md_path),
                language="zh",
                parser="mineru",
            ),
            md_path,
        )
    if fmt in ("md", "markdown", "txt"):
        md_path = corpus_dir / src_path.name
        md_path.write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")
        return (
            CorpusSource(
                type="textbook",
                format=fmt,
                original_file=str(src_path),
                converted_file=str(md_path),
                language="zh",
            ),
            md_path,
        )
    raise TutorError(
        "DEPENDENCY_MISSING",
        hint=f"file 源暂不支持格式 .{fmt}（当前切片只接 pdf/md/txt）",
    )


def _acquire_web(src: AcquireSource, corpus_dir: Path) -> tuple[CorpusSource, Path]:
    """web 源：委托 research-tool 采集 + 清洗（collect+clean），合并为 corpus markdown。

    延迟导入 research_adapter，使本模块在未安装 research-tool 时仍可导入；真正缺依赖
    时由 acquire_web 抛 DEPENDENCY_MISSING（含安装提示）。
    """
    from .research_adapter import acquire_web

    return acquire_web(src, corpus_dir)


def _acquire_video(src: AcquireSource, corpus_dir: Path) -> tuple[CorpusSource, Path]:
    raise TutorError(
        "DEPENDENCY_MISSING",
        hint=(
            "video 源待接入：将在下一切片调用 yt-dlp 下载音频 + faster-whisper "
            "转写，写入 corpus_dir"
        ),
    )


_DISPATCH = {
    "file": _acquire_file,
    "web": _acquire_web,
    "video": _acquire_video,
}


# --------------------------------------------------------------------------- #
# 多源合并 —— KG 消费的是单一 markdown，必须把所有来源并进去
# --------------------------------------------------------------------------- #


def _source_label(cs: CorpusSource) -> str:
    """来源的展示标签：web 源是调研主题，file 源是文件名。"""
    if cs.type == "web":
        return cs.original_file
    return Path(cs.original_file).stem


def _merge_sources_markdown(
    *, subject: str, entries: list[tuple[str, Path]], out_path: Path
) -> Path:
    """多源合并为单一 corpus markdown：`# subject` 伞 + 各源正文降级到 ≥2 级。

    修复「KG 只吃第一个源」：build_knowledge_graph 只读 file_paths["markdown"]，
    旧实现把它指到 md_paths[0]，其余来源被静默丢弃（用户被迫手工合并，见 #8/#14）。
    没有任何标题的来源（纯文本）补一个 `## label` 锚点，保证内容有归属层级。
    """
    from .kg_enrich_adapter import _HEADING_RE, demote_headings, iter_markdown_lines

    parts = [f"# {subject}\n"]
    for label, md_path in entries:
        try:
            body = md_path.read_text(encoding="utf-8").strip()
        except OSError:
            logger.warning("acquire.merge.unreadable", file=str(md_path))
            continue
        if not body:
            continue
        has_heading = any(
            not in_code and _HEADING_RE.match(line)
            for _no, line, in_code in iter_markdown_lines(body)
        )
        if has_heading:
            parts.append("\n" + demote_headings(body, min_level=2) + "\n")
        else:
            parts.append(f"\n## {label}\n\n{body}\n")
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #


def acquire(
    *,
    subject: str,
    version: str | None,
    sources: list[AcquireSource],
    user_id: str,
    file_store: FileStore,
    db: RelationalStore,
    mineru_cmd: str | None = None,
) -> tuple[CorpusManifest, str]:
    """从一个或多个来源采集语料。返回 (manifest, corpus_id)。

    当前切片：file 源已实现；web/video 源 stub 抛 DEPENDENCY_MISSING。
    """
    if not sources:
        raise TutorError(
            "DEPENDENCY_MISSING",
            hint="sources 列表不能为空",
        )

    corpus_id = _corpus_id(subject, version)
    corpus_dir = file_store.path("corpora", corpus_id)
    corpus_dir.parent.mkdir(parents=True, exist_ok=True)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    corpus_sources: list[CorpusSource] = []
    md_paths: list[Path] = []
    for src in sources:
        handler = _DISPATCH.get(src.type)
        if handler is None:
            raise TutorError(
                "DEPENDENCY_MISSING",
                hint=f"未知 source.type={src.type!r}（支持: file/web/video）",
            )
        # file 类型需要 mineru_cmd
        if src.type == "file":
            corpus_source, md_path = _acquire_file(src, corpus_dir, mineru_cmd)
        else:
            corpus_source, md_path = handler(src, corpus_dir)  # type: ignore[operator]
        corpus_sources.append(corpus_source)
        md_paths.append(md_path)

    # 多源 → 合并为单一 corpus markdown；KG（build_knowledge_graph）只消费
    # file_paths["markdown"]，不合并的话除第一个源外全部被丢弃。
    primary_md = md_paths[0]
    if len(md_paths) > 1:
        entries = [(_source_label(cs), p) for cs, p in zip(corpus_sources, md_paths)]
        primary_md = _merge_sources_markdown(
            subject=subject, entries=entries, out_path=corpus_dir / "00_corpus.md"
        )

    # 统计：基于 KG 实际消费的 markdown 的 # / ##
    text = primary_md.read_text(encoding="utf-8")
    total_chapters = sum(1 for line in text.splitlines() if line.startswith("# "))
    total_sections = sum(1 for line in text.splitlines() if line.startswith("## "))

    # file_paths：保留每个原始来源 + "markdown" 指向 KG 消费的主文件
    file_paths = {f"markdown_{i}": str(p) for i, p in enumerate(md_paths)}
    file_paths["markdown"] = str(primary_md)

    manifest = CorpusManifest(
        corpus_id=corpus_id,
        subject=subject,
        version=version or "auto",
        created_at=datetime.utcnow(),
        sources=corpus_sources,
        total_chapters=total_chapters,
        total_sections=total_sections,
        estimated_concepts=total_sections or total_chapters,
        file_paths=file_paths,
    )

    with db.session() as s:
        s.add(
            CorpusRow(
                id=corpus_id,
                subject_id=_slugify(subject),
                user_id=user_id,
                manifest_json=manifest.model_dump(mode="json"),
            )
        )
        s.commit()

    logger.info(
        "acquire.done",
        corpus_id=corpus_id,
        sources=len(sources),
        chapters=total_chapters,
        sections=total_sections,
    )
    return manifest, corpus_id
