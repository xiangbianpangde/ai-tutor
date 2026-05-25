"""research_adapter 测试 —— 全部 mock 掉 research-tool 管道，不触网。

覆盖：markdown 合并、PipelineConfig 构造（搜索引擎随 tavily key 变化）、
acquire_web 成功/空结果/缺 uri 三条路径。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from servers.knowledge_mcp import research_adapter
from shared.errors import TutorError

# ----------------------------- _merge_markdown ----------------------------- #

def test_merge_markdown_builds_hierarchy(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("正文A", encoding="utf-8")
    (tmp_path / "b.md").write_text("正文B", encoding="utf-8")
    out = tmp_path / "corpus.md"
    research_adapter._merge_markdown([tmp_path / "a.md", tmp_path / "b.md"], "向量空间", out)

    text = out.read_text(encoding="utf-8")
    assert text.startswith("# 向量空间")
    assert "## a" in text and "## b" in text
    assert "正文A" in text and "正文B" in text


def test_merge_markdown_skips_empty_and_unreadable(tmp_path: Path) -> None:
    (tmp_path / "empty.md").write_text("   ", encoding="utf-8")
    (tmp_path / "ok.md").write_text("有内容", encoding="utf-8")
    out = tmp_path / "c.md"
    research_adapter._merge_markdown(
        [tmp_path / "empty.md", tmp_path / "ok.md", tmp_path / "missing.md"], "主题", out
    )
    text = out.read_text(encoding="utf-8")
    assert "有内容" in text
    assert "## empty" not in text  # 空文件不产出标题


# ----------------------------- _build_config ----------------------------- #

def _isolate_env(monkeypatch) -> None:
    """隔离环境：不读真实 .env，DeepSeek 给假 key，避免测试依赖外部配置。"""
    monkeypatch.setattr(research_adapter, "load_env", lambda: None)
    monkeypatch.setattr(research_adapter, "get_deepseek_config",
                        lambda: {"api_key": "ds-x", "base_url": "https://api.deepseek.com", "model": "deepseek-chat"})


def test_build_config_with_tavily(tmp_path: Path, monkeypatch) -> None:
    _isolate_env(monkeypatch)
    monkeypatch.setattr(research_adapter, "get_tavily_config", lambda: {"api_key": "tv-x"})

    cfg = research_adapter._build_config("向量空间", tmp_path)
    assert cfg.stages == ["collect", "clean"]
    assert cfg.collector.search_engines == ["tavily", "web"]
    assert cfg.collector.tavily_api_key == "tv-x"
    assert cfg.topic == "向量空间"


def test_build_config_without_tavily_falls_back_to_web(tmp_path: Path, monkeypatch) -> None:
    _isolate_env(monkeypatch)
    monkeypatch.setattr(research_adapter, "get_tavily_config", lambda: None)

    cfg = research_adapter._build_config("主题", tmp_path)
    assert cfg.collector.search_engines == ["web"]  # 无 key → 仅免费 duckduckgo
    assert cfg.collector.tavily_api_key is None


# ----------------------------- acquire_web ----------------------------- #

def _patch_pipeline(monkeypatch, *, clean_files: list[Path], failed_stage=None, topic_dir: Path):
    """把 research_tool.create_pipeline 换成写好 clean 文件的假管道。"""
    import research_tool

    result = SimpleNamespace(
        failed_stage=failed_stage,
        topic_dir=topic_dir,
        clean_result=SimpleNamespace(files=clean_files) if clean_files else None,
    )

    class FakePipeline:
        async def run(self, topic):  # noqa: ANN001
            return result

    monkeypatch.setattr(research_tool, "create_pipeline", lambda cfg: FakePipeline())


def test_acquire_web_success(tmp_path: Path, monkeypatch) -> None:
    _isolate_env(monkeypatch)
    monkeypatch.setattr(research_adapter, "get_tavily_config", lambda: None)
    clean_dir = tmp_path / "t" / "clean"
    clean_dir.mkdir(parents=True)
    f1 = clean_dir / "page1.md"
    f1.write_text("网页正文一", encoding="utf-8")
    f2 = clean_dir / "page2.md"
    f2.write_text("网页正文二", encoding="utf-8")
    _patch_pipeline(monkeypatch, clean_files=[f1, f2], topic_dir=tmp_path / "t")

    src = SimpleNamespace(uri="向量空间")
    cs, md = research_adapter.acquire_web(src, tmp_path)

    assert cs.type == "web" and cs.parser == "research-tool" and cs.format == "md"
    assert cs.original_file == "向量空间"
    assert md.exists()
    text = md.read_text(encoding="utf-8")
    assert "# 向量空间" in text and "网页正文一" in text and "网页正文二" in text


def test_acquire_web_empty_uri_raises(tmp_path: Path) -> None:
    with pytest.raises(TutorError) as exc:
        research_adapter.acquire_web(SimpleNamespace(uri="  "), tmp_path)
    assert exc.value.code == "DEPENDENCY_MISSING"


def test_acquire_web_no_results_raises_corpus_not_found(tmp_path: Path, monkeypatch) -> None:
    _isolate_env(monkeypatch)
    monkeypatch.setattr(research_adapter, "get_tavily_config", lambda: None)
    _patch_pipeline(monkeypatch, clean_files=[], topic_dir=tmp_path / "t")

    with pytest.raises(TutorError) as exc:
        research_adapter.acquire_web(SimpleNamespace(uri="无结果主题"), tmp_path)
    assert exc.value.code == "CORPUS_NOT_FOUND"


def test_acquire_web_failed_stage_raises(tmp_path: Path, monkeypatch) -> None:
    _isolate_env(monkeypatch)
    monkeypatch.setattr(research_adapter, "get_tavily_config", lambda: None)
    _patch_pipeline(monkeypatch, clean_files=[], failed_stage="collect", topic_dir=tmp_path / "t")

    with pytest.raises(TutorError) as exc:
        research_adapter.acquire_web(SimpleNamespace(uri="主题"), tmp_path)
    assert exc.value.code == "CORPUS_NOT_FOUND"
