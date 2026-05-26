"""PDF 解析管道：mineru（PDF→英文 markdown，隔离 CLI）→ 可选 markdown 翻译（树内）。

两段职责清晰分离：
- **解析**：mineru CLI（重依赖，非本项目代码 → 保持 subprocess 隔离，不进核心 venv）。
- **翻译**：md_translator（从用户 pdf2zh/translate_md.py 树内并入，仅依赖已有的 openai）。
  这取代了早期"pdf2zh 把 PDF 翻成译版 PDF"的 subprocess 方案——你的 pdf2zh 实际
  是 markdown 层翻译（mineru→翻译 md），故并入后翻译在进程内完成，无需 pdf2zh CLI。

管道：
- translate=False：mineru 直接抽中文 markdown（中文教材常态）。
- translate=True ：mineru 抽源语言（默认 en）markdown → translate_markdown 译成中文。
缺 mineru CLI → DEPENDENCY_MISSING；翻译缺 DeepSeek key → DEPENDENCY_MISSING（见 md_translator）。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

from shared.config import get_deepseek_config
from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.plugins import HealthStatus

logger = get_logger("knowledge_mcp.pdf_parser")

_MINERU_INSTALL = "mineru 未安装：建议 `uv tool install mineru`（隔离安装，避免污染核心 venv）"


def _which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run(cmd: list[str], *, what: str) -> None:
    """跑外部 CLI；非零退出 → PLUGIN_NOT_AVAILABLE（带 stderr 尾巴）。"""
    logger.info("pdf.exec", what=what, cmd=cmd)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise TutorError(
            "PLUGIN_NOT_AVAILABLE",
            hint=f"{what} 失败 (exit={proc.returncode}): {(proc.stderr or '')[-500:]}",
        )


def convert_to_markdown(
    pdf: Path, out_dir: Path, *, mineru_cmd: str = "mineru", lang: str = "zh"
) -> Path:
    """用 mineru 把 PDF 抽成 markdown，返回 .md 路径。缺 CLI → DEPENDENCY_MISSING。"""
    if not _which(mineru_cmd):
        raise TutorError("DEPENDENCY_MISSING", hint=_MINERU_INSTALL)
    _run(
        [mineru_cmd, "-p", str(pdf), "-o", str(out_dir), "-b", "pipeline", "-l", lang],
        what="mineru",
    )
    cands = list(out_dir.rglob(f"{pdf.stem}*.md"))
    if not cands:
        raise TutorError(
            "CORPUS_NOT_FOUND", hint=f"mineru 完成但没找到 {pdf.stem}.md 在 {out_dir}"
        )
    return cands[0]


def parse_pdf(
    pdf: Path,
    out_dir: Path,
    *,
    translate: bool = False,
    source_lang: str = "en",
    lang_out: str = "zh",
    mineru_cmd: str = "mineru",
) -> Path:
    """PDF → markdown，可选把外文译成中文。

    translate=False：mineru 按 lang_out 抽 markdown（中文教材常态），返回该 md。
    translate=True ：mineru 按 source_lang 抽源语言 markdown → md_translator 译成中文，
                     写 `<stem>_zh.md` 返回。
    """
    mineru_lang = source_lang if translate else lang_out
    md = convert_to_markdown(pdf, out_dir, mineru_cmd=mineru_cmd, lang=mineru_lang)
    if not translate:
        return md

    from .md_translator import translate_markdown

    zh_text = translate_markdown(md.read_text(encoding="utf-8"), lang_out=lang_out)
    zh_path = md.with_name(f"{md.stem}_zh.md")
    zh_path.write_text(zh_text, encoding="utf-8")
    logger.info("pdf.translated", src=str(md), out=str(zh_path))
    return zh_path


class MinerUPdfParser:
    """PluginRegistry 用的 pdf_parse 插件：mineru 抽取（可选树内 markdown 翻译）。

    health() 检查 mineru CLI 是否在 PATH；翻译是否可用看 DeepSeek 配置（树内，不依赖 CLI）。
    """

    category: ClassVar[str] = "pdf_parse"
    name: ClassVar[str] = "mineru"

    def __init__(self, *, mineru_cmd: str = "mineru") -> None:
        self.mineru_cmd = mineru_cmd

    def health(self) -> HealthStatus:
        ok = _which(self.mineru_cmd)
        return HealthStatus(
            ok=ok,
            reason=None if ok else _MINERU_INSTALL,
            extra={"translate_available": get_deepseek_config() is not None},
        )

    def parse(
        self, pdf: Path, out_dir: Path, *, translate: bool = False, lang_out: str = "zh"
    ) -> Path:
        return parse_pdf(
            pdf, out_dir, translate=translate, lang_out=lang_out, mineru_cmd=self.mineru_cmd
        )
