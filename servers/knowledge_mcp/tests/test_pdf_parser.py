"""pdf_parser 测试 —— 全程 mock subprocess + which，不需要真实 pdf2zh/mineru CLI。

验证隔离 CLI 管道：缺 CLI → DEPENDENCY_MISSING；translate 顺序 pdf2zh→mineru；
非零退出 → PLUGIN_NOT_AVAILABLE。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from servers.knowledge_mcp import pdf_parser
from shared.errors import TutorError


def _fake_run_factory(calls: list[str]):
    """返回一个假 subprocess.run：按 cmd 产出对应输出文件并记录调用的工具名。"""
    def _run(cmd, capture_output=True, text=True):  # noqa: ANN001, FBT002
        tool = cmd[0]
        calls.append(tool)
        out_dir = Path(cmd[cmd.index("-o") + 1])
        if tool == "pdf2zh":
            src = Path(cmd[1])
            (out_dir / f"{src.stem}-mono.pdf").write_bytes(b"%PDF translated")
        elif tool == "mineru":
            src = Path(cmd[cmd.index("-p") + 1])
            (out_dir / f"{src.stem}.md").write_text("# 抽取标题\n正文", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")
    return _run


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return p


def _all_available(monkeypatch) -> list[str]:
    monkeypatch.setattr(pdf_parser, "_which", lambda _c: True)
    calls: list[str] = []
    monkeypatch.setattr(pdf_parser.subprocess, "run", _fake_run_factory(calls))
    return calls


# ----------------------------- convert_to_markdown ----------------------------- #

def test_convert_missing_mineru_raises(pdf, tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_parser, "_which", lambda _c: False)
    with pytest.raises(TutorError) as exc:
        pdf_parser.convert_to_markdown(pdf, tmp_path)
    assert exc.value.code == "DEPENDENCY_MISSING"
    assert "mineru" in (exc.value.hint or "")


def test_convert_success(pdf, tmp_path, monkeypatch):
    _all_available(monkeypatch)
    md = pdf_parser.convert_to_markdown(pdf, tmp_path)
    assert md.exists() and md.suffix == ".md"
    assert "抽取标题" in md.read_text(encoding="utf-8")


# ----------------------------- translate_pdf ----------------------------- #

def test_translate_missing_pdf2zh_raises(pdf, tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_parser, "_which", lambda _c: False)
    with pytest.raises(TutorError) as exc:
        pdf_parser.translate_pdf(pdf, tmp_path)
    assert exc.value.code == "DEPENDENCY_MISSING"
    assert "pdf2zh" in (exc.value.hint or "")


def test_translate_success_returns_mono(pdf, tmp_path, monkeypatch):
    _all_available(monkeypatch)
    out = pdf_parser.translate_pdf(pdf, tmp_path, lang_out="zh")
    assert out.exists() and out.name == "doc-mono.pdf"


# ----------------------------- parse_pdf ----------------------------- #

def test_parse_no_translate_only_mineru(pdf, tmp_path, monkeypatch):
    calls = _all_available(monkeypatch)
    md = pdf_parser.parse_pdf(pdf, tmp_path, translate=False)
    assert md.suffix == ".md"
    assert calls == ["mineru"]  # 未触发 pdf2zh


def test_parse_with_translate_runs_both_in_order(pdf, tmp_path, monkeypatch):
    calls = _all_available(monkeypatch)
    md = pdf_parser.parse_pdf(pdf, tmp_path, translate=True)
    assert md.suffix == ".md"
    assert calls == ["pdf2zh", "mineru"]  # 先翻译后抽取
    # mineru 抽的是译版 PDF（doc-mono）→ 产出 doc-mono.md
    assert md.name == "doc-mono.md"


def test_nonzero_exit_raises_plugin_not_available(pdf, tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_parser, "_which", lambda _c: True)

    def _fail_run(cmd, capture_output=True, text=True):  # noqa: ANN001, FBT002
        return SimpleNamespace(returncode=2, stderr="boom")

    monkeypatch.setattr(pdf_parser.subprocess, "run", _fail_run)
    with pytest.raises(TutorError) as exc:
        pdf_parser.convert_to_markdown(pdf, tmp_path)
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"
    assert "boom" in (exc.value.hint or "")


# ----------------------------- MinerUPdfParser 插件 ----------------------------- #

def test_plugin_health_reflects_cli_presence(monkeypatch):
    parser = pdf_parser.MinerUPdfParser()
    monkeypatch.setattr(pdf_parser, "_which", lambda c: c == "mineru")  # 只有 mineru
    h = parser.health()
    assert h.ok is True
    assert h.extra["translate_available"] is False  # pdf2zh 缺失

    monkeypatch.setattr(pdf_parser, "_which", lambda _c: False)
    assert parser.health().ok is False


def test_plugin_is_registry_compatible():
    from shared.plugins import Plugin
    parser = pdf_parser.MinerUPdfParser()
    assert isinstance(parser, Plugin)  # 满足 category/name/health Protocol
    assert parser.category == "pdf_parse"
