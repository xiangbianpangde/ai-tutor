"""research-tool 适配层 —— 把 web 采集接到桌面已有的调研引擎。

research-tool 是本地路径依赖（pyproject [project.optional-dependencies] research，
见 [tool.uv.sources]）。未安装时（没跑 `uv sync --extra research`）→ DEPENDENCY_MISSING
+ 安装提示，调用方据此降级。

流程：
  create_pipeline(PipelineConfig(stages=["collect","clean"])).run(topic)
  → 把 topic_dir/clean/*.md 合并成单个 corpus markdown 返回。

设计要点：
- 只跑 collect + clean 两阶段（不做 extract/organize/report）——我们要的是干净正文，
  概念抽取交给本项目的 KG builder。
- 搜索引擎：有 Tavily key → ["tavily","web"]；否则 ["web"]（duckduckgo，免费）。
- 网页抓取：research-tool 的 Fetcher 在无 crawl4ai 时自动回退 httpx，无需浏览器。
- LLM（query expansion）默认关，故 collect+clean 不强依赖 DeepSeek；有 key 则带上。
- 异步管道用 _run_async 兜底：无论调用方是否已在事件循环里都能跑。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from shared.config import get_deepseek_config, get_tavily_config, load_env
from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.schemas import CorpusSource
from shared.slug import slugify

logger = get_logger("knowledge_mcp.research_adapter")

_INSTALL_HINT = (
    "web 源需要 research-tool：请在项目根目录运行 "
    "`uv sync --extra research --extra dev` 安装后重试"
)


def _run_async(coro: Any) -> Any:
    """安全跑协程到完成：无运行中的事件循环 → asyncio.run；否则丢到独立线程跑。

    acquisition 链是同步函数，但可能被 async 的 MCP 工具间接调用——直接 asyncio.run
    会在已有 loop 时报错，故在那种情况下用单独线程跑一个新 loop。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # 没有运行中的 loop，直接跑
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro)).result()


def _merge_markdown(files: list[Path], topic: str, out_path: Path) -> Path:
    """把多个 clean/*.md 合并成一个带层级标题的 corpus markdown。

    顶层 `# topic` + 每个来源一个 `## 文件名`，保证 toc 模式 KG builder 有标题锚点。
    """
    parts = [f"# {topic}\n"]
    for f in sorted(files):
        try:
            text = f.read_text(encoding="utf-8").strip()
        except Exception:  # noqa: BLE001 — 单文件读失败跳过，不中断合并
            continue
        if not text:
            continue
        title = f.stem.replace("_", " ").strip() or "片段"
        parts.append(f"\n## {title}\n\n{text}\n")
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path


def _build_config(topic: str, corpus_dir: Path) -> Any:
    """构造 research-tool 的 PipelineConfig（collect+clean）。延迟导入。"""
    from research_tool import CollectorConfig, LLMConfig, PipelineConfig

    load_env()  # 确保 .env 里的 key 进了 os.environ
    tavily = get_tavily_config()
    engines = ["tavily", "web"] if tavily else ["web"]

    collector = CollectorConfig(
        search_engines=engines,
        tavily_api_key=(tavily or {}).get("api_key"),
        max_results_per_engine=8,
    )

    ds = get_deepseek_config()
    llm = LLMConfig(
        provider="deepseek",
        model=(ds or {}).get("model", "deepseek-chat"),
        api_key=(ds or {}).get("api_key"),
        base_url=(ds or {}).get("base_url"),
    )

    return PipelineConfig(
        topic=topic,
        work_dir=corpus_dir,
        stages=["collect", "clean"],
        collector=collector,
        llm=llm,
        resume=True,
    )


def acquire_web(src: Any, corpus_dir: Path) -> tuple[CorpusSource, Path]:
    """web 源采集：src.uri 作为调研 topic（或 URL 关键词）。

    返回 (CorpusSource, 合并后的 markdown 路径)。
    research-tool 未装 → DEPENDENCY_MISSING；采集到 0 篇 → CORPUS_NOT_FOUND。
    """
    topic = (getattr(src, "uri", "") or "").strip()
    if not topic:
        raise TutorError("DEPENDENCY_MISSING", hint="web 源缺少 uri（作为调研主题/关键词）")

    try:
        from research_tool import create_pipeline  # noqa: F401  延迟导入探测
    except ImportError as exc:
        raise TutorError("DEPENDENCY_MISSING", hint=_INSTALL_HINT) from exc

    config = _build_config(topic, corpus_dir)
    pipeline = create_pipeline(config)

    logger.info("research.collect.start", topic=topic, work_dir=str(corpus_dir))
    try:
        result = _run_async(pipeline.run(topic))
    except TutorError:
        raise
    except Exception as exc:  # noqa: BLE001 — 采集失败转成结构化错误
        logger.warning("research.collect.failed", topic=topic, error=str(exc))
        raise TutorError("DEPENDENCY_MISSING", hint=f"research-tool 采集失败: {exc}") from exc

    if result.failed_stage:
        raise TutorError(
            "CORPUS_NOT_FOUND",
            hint=f"research-tool 在 {result.failed_stage} 阶段失败，未产出干净正文",
        )

    clean_files: list[Path] = []
    if result.clean_result is not None:
        clean_files = list(result.clean_result.files)
    if not clean_files:
        # 兜底扫描 clean 目录
        clean_dir = result.topic_dir / "clean"
        if clean_dir.exists():
            clean_files = list(clean_dir.glob("*.md"))
    if not clean_files:
        raise TutorError(
            "CORPUS_NOT_FOUND",
            hint=f"主题「{topic}」没采集到可用网页正文（换个关键词或检查网络/搜索 key）",
        )

    md_path = corpus_dir / f"{slugify(topic)}.md"
    _merge_markdown(clean_files, topic, md_path)
    logger.info("research.collect.done", topic=topic, sources=len(clean_files), md=str(md_path))

    return (
        CorpusSource(
            type="web",
            format="md",
            original_file=topic,
            converted_file=str(md_path),
            language="zh",
            parser="research-tool",
        ),
        md_path,
    )
