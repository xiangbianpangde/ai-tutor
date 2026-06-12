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
import hashlib
import re
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


# research-tool 的 clean 文件头部是 `<!-- key: value -->` 元数据块（source/title/fetched/via）
_META_COMMENT_RE = re.compile(r"^<!--\s*(?P<key>[\w-]+)\s*:\s*(?P<value>.*?)\s*-->$")

# 清洗后正文低于此字符数视为"无有效残文"（导航页/壳页清洗后的残渣），跳过不入料
_MIN_BODY_CHARS = 200
# 节标题超长会被 KG 的噪声标题过滤掉，提前截断保住锚点
_MAX_SOURCE_TITLE_CHARS = 60


def _parse_source_meta(text: str) -> tuple[dict[str, str], str]:
    """解析 clean 文件头部的 `<!-- key: value -->` 元数据，返回 (meta, 剥掉元数据的正文)。"""
    meta: dict[str, str] = {}
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        s = lines[idx].strip()
        if not s:
            idx += 1
            continue
        m = _META_COMMENT_RE.match(s)
        if m is None:
            break
        meta[m.group("key").lower()] = m.group("value")
        idx += 1
    return meta, "\n".join(lines[idx:]).strip()


def _merge_markdown(files: list[Path], topic: str, out_path: Path) -> tuple[Path, int]:
    """把多个 clean/*.md 合并成一个带层级标题的 corpus markdown，返回 (路径, 保留来源数)。

    顶层 `# topic` + 每个来源一个 `## 真实标题`（取自清洗文件头部的
    `<!-- title: ... -->`，缺则退回文件名——文件名当标题曾让 KG 长出
    「01-edu.aliyun.com-087e03」这类概念，见 #22）。来源正文剥掉元数据注释、
    标题整体降到 ≥3 级；清洗后几乎无残文（<200 字符）的来源跳过。

    FIX-K：deepen 的多个子面经常搜回同一篇文章（FastAPI 复跑实测 49 组重名概念），
    按 (来源URL, 正文哈希) 去重——同 URL 或同正文只入料一次。
    """
    from .kg_enrich_adapter import demote_headings

    parts = [f"# {topic}\n"]
    kept = 0
    seen: set[str] = set()
    for f in sorted(files):
        try:
            text = f.read_text(encoding="utf-8").strip()
        except Exception:  # noqa: BLE001 — 单文件读失败跳过，不中断合并
            continue
        meta, body = _parse_source_meta(text)
        if len(body) < _MIN_BODY_CHARS:
            logger.warning("research.merge.skip_thin", file=f.name, chars=len(body))
            continue
        keys = [k for k in (meta.get("source"), hashlib.sha1(body.encode()).hexdigest()) if k]
        if any(k in seen for k in keys):
            logger.info("research.merge.skip_dup", file=f.name, source=meta.get("source", "?"))
            continue
        seen.update(keys)
        title = (meta.get("title") or f.stem.replace("_", " ")).strip() or "片段"
        title = title[:_MAX_SOURCE_TITLE_CHARS]
        body = demote_headings(body, min_level=3)
        section = [f"\n## {title}\n"]
        if meta.get("source"):
            section.append(f"\n> 来源：{meta['source']}\n")
        section.append(f"\n{body}\n")
        parts.append("".join(section))
        kept += 1
    out_path.write_text("\n".join(parts), encoding="utf-8")
    return out_path, kept


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


_FACET_SYSTEM = (
    "你是调研规划助手。把给定学习主题拆成 3-5 个互补的检索子面，"
    "覆盖基础概念、核心方法、实践应用、常见考点。"
    "只输出 JSON 字符串数组，每项是一个可直接搜索的中文查询短语。"
)


def expand_topic_facets(topic: str, llm: Any | None = None) -> list[str]:
    """把调研主题拆成互补检索子面（#9：单轮单查询覆盖不足 → 多面采集）。

    llm 缺省时用 DeepSeekProvider.from_env()；LLM 不可用或输出不可解析 →
    返回 [topic]（退化为单轮，绝不阻断采集）。主题本身永远是第一面，总数 ≤5。
    """
    import json as _json

    if llm is None:
        try:
            from shared.providers.deepseek import DeepSeekProvider

            llm = DeepSeekProvider.from_env()
        except Exception:  # noqa: BLE001 — provider 构造失败按不可用处理
            llm = None
        if llm is None:
            return [topic]
    try:
        resp = llm.chat(
            messages=[
                {"role": "system", "content": _FACET_SYSTEM},
                {"role": "user", "content": f"主题：{topic}"},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        text = (resp.content or "").strip()
        if text.startswith("```"):
            text = "\n".join(
                l for l in text.splitlines() if not l.strip().startswith("```")
            ).strip()
        data = _json.loads(text)
    except Exception as exc:  # noqa: BLE001 — 拆面失败退化为单轮
        logger.warning("research.deepen.expand_failed", topic=topic, error=str(exc))
        return [topic]
    if not isinstance(data, list):
        return [topic]
    facets = [str(x).strip() for x in data if str(x).strip()]
    return ([topic] + [f for f in facets if f != topic])[:5]


def _collect_topic(topic: str, work_dir: Path, create_pipeline: Any) -> list[Path]:
    """跑一轮 collect+clean，返回 clean 文件列表（可能为空）。失败抛 TutorError。"""
    config = _build_config(topic, work_dir)
    pipeline = create_pipeline(config)

    logger.info("research.collect.start", topic=topic, work_dir=str(work_dir))
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
    return clean_files


def acquire_web(src: Any, corpus_dir: Path) -> tuple[CorpusSource, Path]:
    """web 源采集：src.uri 作为调研 topic（或 URL 关键词）。

    返回 (CorpusSource, 合并后的 markdown 路径)。
    research-tool 未装 → DEPENDENCY_MISSING；采集到 0 篇 → CORPUS_NOT_FOUND。
    src.deepen=True 时主题拆面分别采集再归并（默认关，行为与单轮一致）。
    """
    topic = (getattr(src, "uri", "") or "").strip()
    if not topic:
        raise TutorError("DEPENDENCY_MISSING", hint="web 源缺少 uri（作为调研主题/关键词）")

    try:
        from research_tool import create_pipeline  # noqa: F401  延迟导入探测
    except ImportError as exc:
        raise TutorError("DEPENDENCY_MISSING", hint=_INSTALL_HINT) from exc

    facets = [topic]
    if getattr(src, "deepen", False):
        facets = expand_topic_facets(topic)
        if len(facets) > 1:
            logger.info("research.deepen.facets", topic=topic, facets=facets)

    clean_files: list[Path] = []
    for facet in facets:
        work_dir = corpus_dir if len(facets) == 1 else corpus_dir / slugify(facet)
        try:
            clean_files.extend(_collect_topic(facet, work_dir, create_pipeline))
        except TutorError:
            if len(facets) == 1:
                raise  # 单轮：保持旧错误语义
            logger.warning("research.deepen.facet_failed", facet=facet)

    if not clean_files:
        raise TutorError(
            "CORPUS_NOT_FOUND",
            hint=f"主题「{topic}」没采集到可用网页正文（换个关键词或检查网络/搜索 key）",
        )

    md_path = corpus_dir / f"{slugify(topic)}.md"
    _, kept = _merge_markdown(clean_files, topic, md_path)
    if kept == 0:
        raise TutorError(
            "CORPUS_NOT_FOUND",
            hint=f"主题「{topic}」的 {len(clean_files)} 个网页清洗后均无有效正文",
        )
    logger.info("research.collect.done", topic=topic, sources=kept, md=str(md_path))

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
