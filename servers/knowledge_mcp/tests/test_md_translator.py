"""md_translator 测试 —— 从 pdf2zh/translate_md.py 并入的 markdown 翻译。

全程用假 OpenAI 客户端，不触网、不需 key。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from servers.knowledge_mcp import md_translator
from shared.errors import TutorError


class _FakeClient:
    """模拟 OpenAI 客户端：把每块前缀成 译:<原文前8字>，便于断言顺序与内容。"""

    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.calls = 0

    def _create(self, model, messages, temperature, stream):  # noqa: ANN001
        self.calls += 1
        user = messages[-1]["content"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=f"译:{user[:8]}"))]
        )


# ----------------------------- chunk_markdown ----------------------------- #

def test_chunk_respects_max_chars():
    md = "\n\n".join(["段落" * 50 for _ in range(10)])  # 每段 100 字
    chunks = md_translator.chunk_markdown(md, max_chars=250)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)  # 容许单段略超，但不会无限堆叠


def test_chunk_keeps_short_md_single():
    chunks = md_translator.chunk_markdown("# 标题\n\n一段话", max_chars=3000)
    assert len(chunks) == 1


# ----------------------------- translate_markdown ----------------------------- #

def test_translate_empty_returns_empty():
    assert md_translator.translate_markdown("   ") == ""


def test_translate_with_injected_client_preserves_order():
    client = _FakeClient()
    md = "AAAAAAAA\n\nBBBBBBBB\n\nCCCCCCCC"
    out = md_translator.translate_markdown(md, client=client, model="m", max_workers=4, chunk_size=10)
    # 每段一块，译文按原序拼接
    parts = out.split("\n\n")
    assert parts[0].startswith("译:AAAA")
    assert parts[1].startswith("译:BBBB")
    assert parts[2].startswith("译:CCCC")
    assert client.calls == 3


def test_translate_serial_path_when_single_worker():
    client = _FakeClient()
    out = md_translator.translate_markdown("X\n\nY", client=client, max_workers=1, chunk_size=5)
    assert "译:X" in out and "译:Y" in out


def test_translate_no_config_raises(monkeypatch):
    """未注入 client 且无 DeepSeek 配置 → DEPENDENCY_MISSING（不触网）。"""
    monkeypatch.setattr(md_translator, "get_deepseek_config", lambda: None)
    with pytest.raises(TutorError) as exc:
        md_translator.translate_markdown("some english text")
    assert exc.value.code == "DEPENDENCY_MISSING"


def test_translate_builds_client_from_config(monkeypatch):
    """有配置时自建客户端：monkeypatch OpenAI 以免真实网络。"""
    monkeypatch.setattr(md_translator, "get_deepseek_config",
                        lambda: {"api_key": "k", "base_url": "u", "model": "deepseek-chat"})
    captured = {}

    def _fake_openai(api_key, base_url):  # noqa: ANN001
        captured["api_key"] = api_key
        captured["base_url"] = base_url
        return _FakeClient()

    import openai
    monkeypatch.setattr(openai, "OpenAI", _fake_openai)

    out = md_translator.translate_markdown("hello world")
    assert out.startswith("译:")
    assert captured == {"api_key": "k", "base_url": "u"}
