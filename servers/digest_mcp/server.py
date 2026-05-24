"""digest-mcp FastMCP server 入口。

已实现的 tool:
- digest:           按 formats 列表生成多种产物（7 种 format 全部实现）
- build_quiz_html:  spec §三 #2 独立入口，复用 quiz generator
- compile_slides:   spec §三 #3 独立入口，复用 slides generator（缺 pptx → HTML）
- health:           自检

支持的 format（全部 ✅）:
- mindmap     text/vnd.mermaid
- notes       text/markdown
- quiz        text/html + application/json
- simulation  text/html（自包含交互闪卡）
- multi_agent application/json（三角色对话；有 DeepSeek key 时 LLM 生成）
- slides      text/html（装 python-pptx 则升级 .pptx）
- audio       text/markdown 讲稿（装 edge-tts 则合成 .mp3）
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from shared.logging_config import configure_logging, get_logger
from shared.models import KnowledgeGraphRow
from shared.schemas import DigestResult
from shared.storage import RelationalStore

from .orchestrator import digest as digest_impl

configure_logging()
logger = get_logger("digest_mcp.server")

mcp: FastMCP = FastMCP("digest-mcp")


def _db() -> RelationalStore:
    return RelationalStore.from_env()


def _data_root() -> Path:
    root = os.environ.get("AI_TUTOR_DATA_ROOT", str(Path("data").resolve()))
    p = Path(root)
    p.mkdir(parents=True, exist_ok=True)
    return p


@mcp.tool()
async def digest(
    kg_id: str,
    formats: list[str] | None = None,
    corpus_id: str | None = None,
    grade: str = "college",
    learning_style: str | None = None,
    quiz_count: int = 10,
) -> DigestResult:
    """对给定 KG 生成多模态产物。

    Args:
        kg_id:    要消化的 KG ID（必填）
        formats:  ["mindmap"|"notes"|"quiz"|"slides"|"audio"|"simulation"|"multi_agent"]
                  默认 ["mindmap", "quiz"]
        grade:    年级适配，notes format 据此调整（"high_school" 直觉优先 /
                  "college" 形式化优先，默认 college）
        corpus_id, learning_style: spec 保留参数（当前未使用，预留给 slides/audio）
        quiz_count: quiz format 的题目数；默认 10
    """
    db = _db()
    db.init_schema()
    out_dir = _data_root() / "output" / "digest" / kg_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # multi_agent 可选用 LLM：有 DeepSeek key 则生成自然对话，否则模板兜底
    llm = None
    try:
        from shared.providers.deepseek import DeepSeekProvider
        llm = DeepSeekProvider.from_env()
    except Exception:  # noqa: BLE001 — 无 key / 无依赖 → 模板模式
        llm = None

    run = digest_impl(
        db=db,
        kg_id=kg_id,
        out_dir=out_dir,
        formats=formats,
        quiz_count=quiz_count,
        grade=grade,
        llm=llm,
    )
    if run.warnings:
        logger.warning("digest.partial", warnings=run.warnings)
    return run.to_schema


@mcp.tool()
async def build_quiz_html(
    kg_id: str,
    quiz_count: int = 10,
    seed: int | None = None,
) -> DigestResult:
    """从 KG 直接生成交互测验（spec §三 #2 的独立 tool）。

    与 digest(formats=["quiz"]) 复用同一 generator，但作为独立入口方便 MCP host
    直接调用。产物 quiz.html 自包含、零外部依赖；附 quiz-data.json。

    Args:
        kg_id:      要出题的 KG ID（必填）
        quiz_count: 题目数；默认 10
        seed:       随机种子（None=确定性默认）
    """
    from .quiz import generate_quiz

    db = _db()
    db.init_schema()
    out_dir = _data_root() / "output" / "digest" / kg_id
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = generate_quiz(
        db=db, kg_id=kg_id, out_dir=out_dir, count=quiz_count, seed=seed,
    )
    logger.info("build_quiz_html.done", kg_id=kg_id, count=quiz_count,
                artifacts=len(artifacts))
    return DigestResult(artifacts=artifacts)


@mcp.tool()
async def compile_slides(kg_id: str) -> DigestResult:
    """从 KG 直接生成演示幻灯片（spec §三 #3 的独立 tool）。

    与 digest(formats=["slides"]) 复用同一 generator。装了 python-pptx → 输出
    可编辑 .pptx；否则优雅降级为自包含 HTML 幻灯片。

    Args:
        kg_id: 要编排的 KG ID（必填）
    """
    from .slides import generate_slides

    db = _db()
    db.init_schema()
    out_dir = _data_root() / "output" / "digest" / kg_id
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact = generate_slides(db=db, kg_id=kg_id, out_dir=out_dir)
    logger.info("compile_slides.done", kg_id=kg_id, uri=artifact.uri)
    return DigestResult(artifacts=[artifact])


@mcp.tool()
async def health() -> dict[str, Any]:
    """轻量自检：DB 可达 + KG 数。"""
    db = _db()
    try:
        with db.session() as s:
            n = s.query(KnowledgeGraphRow).count()
        return {
            "ok": True,
            "server": "digest-mcp",
            "version": "0.1.0",
            "kg_count": n,
            "db_url": db.url,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> None:
    import sys

    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]
    logger.info("digest_mcp.start", transport=transport)
    if transport == "http":
        mcp.run(transport="sse", host="0.0.0.0", port=8003)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
