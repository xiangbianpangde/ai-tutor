"""pdf_parser 测试 —— mock subprocess(mineru) + which，翻译走树内 md_translator（mock）。

不需要真实 mineru CLI、不触网。验证：缺 mineru→DEPENDENCY_MISSING；translate 走
mineru→md_translator（无 pdf2zh subprocess）；非零退出→PLUGIN_NOT_AVAILABLE。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from servers.knowledge_mcp import pdf_parser
from shared.errors import TutorError


def _fake_run_factory(calls: list[str]):
    """假 subprocess.run：mineru 产出 {stem}.md 并记录调用。"""
    def _run(cmd, capture_output=True, text=True):  # noqa: ANN001, FBT002
        calls.append(cmd[0])
        out_dir = Path(cmd[cmd.index("-o") + 1])
        src = Path(cmd[cmd.index("-p") + 1])
        (out_dir / f"{src.stem}.md").write_text("# Title\nbody", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")
    return _run


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return p


def _mineru_available(monkeypatch) -> list[str]:
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
    _mineru_available(monkeypatch)
    md = pdf_parser.convert_to_markdown(pdf, tmp_path)
    assert md.exists() and md.suffix == ".md"


def test_nonzero_exit_raises_plugin_not_available(pdf, tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_parser, "_which", lambda _c: True)
    monkeypatch.setattr(
        pdf_parser.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=2, stderr="boom"),
    )
    with pytest.raises(TutorError) as exc:
        pdf_parser.convert_to_markdown(pdf, tmp_path)
    assert exc.value.code == "PLUGIN_NOT_AVAILABLE"
    assert "boom" in (exc.value.hint or "")


# ----------------------------- parse_pdf ----------------------------- #

def test_parse_no_translate_only_mineru(pdf, tmp_path, monkeypatch):
    calls = _mineru_available(monkeypatch)
    md = pdf_parser.parse_pdf(pdf, tmp_path, translate=False)
    assert md.suffix == ".md" and md.name == "doc.md"
    assert calls == ["mineru"]


def test_parse_with_translate_uses_md_translator(pdf, tmp_path, monkeypatch):
    """translate=True：mineru 抽 md → 树内 translate_markdown（mock），无 pdf2zh subprocess。"""
    calls = _mineru_available(monkeypatch)
    from servers.knowledge_mcp import md_translator

    monkeypatch.setattr(md_translator, "translate_markdown", lambda md, **kw: "# 标题\n译文内容")

    out = pdf_parser.parse_pdf(pdf, tmp_path, translate=True)
    assert out.name == "doc_zh.md"
    assert "译文内容" in out.read_text(encoding="utf-8")
    assert calls == ["mineru"]  # 翻译在进程内，未起任何额外 subprocess


# ----------------------------- MinerUPdfParser 插件 ----------------------------- #

def test_plugin_health_reflects_mineru_and_deepseek(monkeypatch):
    parser = pdf_parser.MinerUPdfParser()
    monkeypatch.setattr(pdf_parser, "_which", lambda _c: True)
    monkeypatch.setattr(pdf_parser, "get_deepseek_config",
                        lambda: {"api_key": "x", "base_url": "y", "model": "m"})
    h = parser.health()
    assert h.ok is True
    assert h.extra["translate_available"] is True

    monkeypatch.setattr(pdf_parser, "get_deepseek_config", lambda: None)
    assert parser.health().extra["translate_available"] is False  # 无 key → 翻译不可用

    monkeypatch.setattr(pdf_parser, "_which", lambda _c: False)
    assert parser.health().ok is False  # 无 mineru → 整体不健康


def test_plugin_is_registry_compatible():
    from shared.plugins import Plugin
    parser = pdf_parser.MinerUPdfParser()
    assert isinstance(parser, Plugin)
    assert parser.category == "pdf_parse"
