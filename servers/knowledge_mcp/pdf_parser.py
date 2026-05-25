"""PDF 解析 —— 隔离 CLI 管道：pdf2zh（翻译）→ mineru（PDF→markdown）。

为什么走 subprocess 而非 pip 依赖：`uv add pdf2zh` 会强制降级 pydantic
（2.13→2.11）并拉入 gradio/onnx/huggingface/babeldoc 等 76 个包，污染核心 venv
并可能压垮本项目的 pydantic schema 层。故把两个工具当**独立 CLI**（用
`uv tool install` / pipx 单独装），后端只通过 subprocess 调用，藏在 PdfParser
插件（PluginRegistry category="pdf_parse"）后面——重依赖隔离在外。

管道：
- translate=True 且 pdf2zh 可用 → 先把外文 PDF 翻成目标语言 PDF（pdf2zh）
- 然后 mineru 把 PDF 抽成 markdown
缺对应 CLI → DEPENDENCY_MISSING（含隔离安装提示），调用方决定降级。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.plugins import HealthStatus

logger = get_logger("knowledge_mcp.pdf_parser")

_PDF2ZH_INSTALL = "pdf2zh 未安装：建议 `uv tool install pdf2zh`（隔离安装，避免污染核心 venv）"
_MINERU_INSTALL = "mineru 未安装：建议 `uv tool install mineru`（隔离安装）"


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


def translate_pdf(
    pdf: Path, out_dir: Path, *, pdf2zh_cmd: str = "pdf2zh", lang_out: str = "zh"
) -> Path:
    """用 pdf2zh 把 PDF 翻成 lang_out，返回译版 PDF 路径。缺 CLI → DEPENDENCY_MISSING。"""
    if not _which(pdf2zh_cmd):
        raise TutorError("DEPENDENCY_MISSING", hint=_PDF2ZH_INSTALL)
    _run([pdf2zh_cmd, str(pdf), "-lo", lang_out, "-o", str(out_dir)], what="pdf2zh")
    # pdf2zh 产出 {stem}-mono.pdf（纯译文）/ {stem}-dual.pdf（双语）
    for suffix in ("-mono.pdf", f"-{lang_out}.pdf", "-dual.pdf"):
        cand = out_dir / f"{pdf.stem}{suffix}"
        if cand.exists():
            return cand
    cands = sorted(p for p in out_dir.glob(f"{pdf.stem}*.pdf") if p.name != pdf.name)
    if cands:
        return cands[0]
    raise TutorError("CORPUS_NOT_FOUND", hint=f"pdf2zh 完成但未找到译版 PDF（{out_dir}）")


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
    lang_out: str = "zh",
    pdf2zh_cmd: str = "pdf2zh",
    mineru_cmd: str = "mineru",
) -> Path:
    """PDF → markdown，可选先翻译。

    translate=True：pdf2zh 译版 PDF → mineru 抽 markdown。
    translate=False：直接 mineru 抽 markdown（中文教材常态）。
    """
    source = pdf
    if translate:
        source = translate_pdf(pdf, out_dir, pdf2zh_cmd=pdf2zh_cmd, lang_out=lang_out)
    return convert_to_markdown(source, out_dir, mineru_cmd=mineru_cmd, lang=lang_out)


class MinerUPdfParser:
    """PluginRegistry 用的 pdf_parse 插件：mineru 抽取（可选 pdf2zh 前置翻译）。

    health() 检查 mineru CLI 是否在 PATH；翻译是否可用由 translate_pdf 自身探测。
    """

    category: ClassVar[str] = "pdf_parse"
    name: ClassVar[str] = "mineru"

    def __init__(self, *, mineru_cmd: str = "mineru", pdf2zh_cmd: str = "pdf2zh") -> None:
        self.mineru_cmd = mineru_cmd
        self.pdf2zh_cmd = pdf2zh_cmd

    def health(self) -> HealthStatus:
        ok = _which(self.mineru_cmd)
        return HealthStatus(
            ok=ok,
            reason=None if ok else _MINERU_INSTALL,
            extra={"translate_available": _which(self.pdf2zh_cmd)},
        )

    def parse(
        self, pdf: Path, out_dir: Path, *, translate: bool = False, lang_out: str = "zh"
    ) -> Path:
        return parse_pdf(
            pdf, out_dir, translate=translate, lang_out=lang_out,
            pdf2zh_cmd=self.pdf2zh_cmd, mineru_cmd=self.mineru_cmd,
        )
