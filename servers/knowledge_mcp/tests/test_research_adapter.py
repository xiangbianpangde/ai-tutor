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

def _long(text: str) -> str:
    """凑够 _MIN_BODY_CHARS 的有效正文（清洗后过薄的来源会被跳过）。"""
    return text + "\n\n" + "这是为凑齐有效正文长度而填充的概念讲解文字，模拟真实清洗产物。" * 10


def test_merge_markdown_builds_hierarchy(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(_long("正文A"), encoding="utf-8")
    (tmp_path / "b.md").write_text(_long("正文B"), encoding="utf-8")
    out = tmp_path / "corpus.md"
    _, kept = research_adapter._merge_markdown(
        [tmp_path / "a.md", tmp_path / "b.md"], "向量空间", out
    )

    assert kept == 2
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# 向量空间")
    assert "## a" in text and "## b" in text  # 无元数据时退回文件名
    assert "正文A" in text and "正文B" in text


def test_merge_markdown_uses_meta_title_and_strips_comments(tmp_path: Path) -> None:
    """来源节标题取 <!-- title --> 真实标题；元数据注释剥掉（#22：文件名曾变成概念）。"""
    f = tmp_path / "01-blog.csdn.net-03b7bb.md"
    f.write_text(
        "<!-- source: https://blog.csdn.net/x/123 -->\n"
        "<!-- title: 阿里云大模型ACP考试大纲解析 -->\n"
        "<!-- fetched: 2026-05-27T00:13:47Z -->\n\n" + _long("考纲正文"),
        encoding="utf-8",
    )
    out = tmp_path / "c.md"
    _, kept = research_adapter._merge_markdown([f], "ACP", out)

    assert kept == 1
    text = out.read_text(encoding="utf-8")
    assert "## 阿里云大模型ACP考试大纲解析" in text
    assert "01-blog.csdn.net-03b7bb" not in text
    assert "<!-- fetched" not in text
    assert "> 来源：https://blog.csdn.net/x/123" in text


def test_merge_markdown_demotes_body_headings(tmp_path: Path) -> None:
    """来源正文里的 H1 降到 H3，不会跳出所属来源的层级变成顶层章节。"""
    f = tmp_path / "page.md"
    f.write_text("# 源内一级标题\n\n" + _long("正文"), encoding="utf-8")
    out = tmp_path / "c.md"
    research_adapter._merge_markdown([f], "主题", out)

    text = out.read_text(encoding="utf-8")
    assert "### 源内一级标题" in text
    assert "\n# 源内一级标题" not in text


def test_merge_markdown_skips_thin_and_unreadable(tmp_path: Path) -> None:
    (tmp_path / "thin.md").write_text("只有一点点残文", encoding="utf-8")
    (tmp_path / "ok.md").write_text(_long("有内容"), encoding="utf-8")
    out = tmp_path / "c.md"
    _, kept = research_adapter._merge_markdown(
        [tmp_path / "thin.md", tmp_path / "ok.md", tmp_path / "missing.md"], "主题", out
    )
    assert kept == 1
    text = out.read_text(encoding="utf-8")
    assert "有内容" in text
    assert "## thin" not in text  # 薄残文不产出标题


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
    f1.write_text(_long("网页正文一"), encoding="utf-8")
    f2 = clean_dir / "page2.md"
    f2.write_text(_long("网页正文二"), encoding="utf-8")
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


# ----------------------------- FIX-I：deepen 多面采集（#9） ----------------------------- #


class _FacetLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def chat(self, **_kw):  # noqa: ANN003
        return SimpleNamespace(content=self.reply)


def test_expand_facets_parses_json_array() -> None:
    llm = _FacetLLM('["基础概念", "核心方法", "实践应用"]')
    out = research_adapter.expand_topic_facets("ACP认证", llm=llm)
    assert out[0] == "ACP认证"  # 主题本身永远是第一面
    assert "基础概念" in out
    assert len(out) <= 5


def test_expand_facets_bad_output_falls_back() -> None:
    out = research_adapter.expand_topic_facets("主题", llm=_FacetLLM("不是JSON"))
    assert out == ["主题"]


def test_expand_facets_no_llm_falls_back(monkeypatch) -> None:
    import shared.providers.deepseek as ds

    monkeypatch.setattr(ds.DeepSeekProvider, "from_env", classmethod(lambda cls: None))
    out = research_adapter.expand_topic_facets("主题")
    assert out == ["主题"]


def test_acquire_web_deepen_merges_facets(tmp_path: Path, monkeypatch) -> None:
    """deepen=True：每个子面独立采集，clean 文件统一归并进一个 corpus markdown。"""
    _isolate_env(monkeypatch)
    monkeypatch.setattr(research_adapter, "get_tavily_config", lambda: None)
    monkeypatch.setattr(
        research_adapter, "expand_topic_facets", lambda topic, llm=None: [topic, "子面A"]
    )

    import research_tool

    class FakePipeline:
        def __init__(self, cfg) -> None:  # noqa: ANN001
            self.cfg = cfg

        async def run(self, topic):  # noqa: ANN001
            clean = Path(self.cfg.work_dir) / "t" / "clean"
            clean.mkdir(parents=True, exist_ok=True)
            f = clean / "page.md"
            f.write_text(_long(f"{topic}的正文"), encoding="utf-8")
            return SimpleNamespace(
                failed_stage=None,
                topic_dir=Path(self.cfg.work_dir) / "t",
                clean_result=SimpleNamespace(files=[f]),
            )

    monkeypatch.setattr(research_tool, "create_pipeline", lambda cfg: FakePipeline(cfg))

    src = SimpleNamespace(uri="主题", deepen=True)
    _cs, md = research_adapter.acquire_web(src, tmp_path)

    text = md.read_text(encoding="utf-8")
    assert "主题的正文" in text
    assert "子面A的正文" in text
