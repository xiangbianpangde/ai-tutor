"""Markdown 翻译（英→中）—— 从用户的 pdf2zh/translate_md.py 树内并入。

为什么并入而非 subprocess/独立包：pdf2zh 的真正核心就是这段 markdown 分块 +
并发 LLM 翻译，唯一依赖是 `openai`——ai-tutor 早已依赖（DeepSeek 走 OpenAI 兼容
接口）。故直接搬进来，复用 shared.config.get_deepseek_config 的配置。

保留原设计要点：
- 按段落（\\n\\n）分块，每块 ≤ max_chars，避免超 LLM context。
- 并发翻译（ThreadPoolExecutor），结果按原序组装。
- SYSTEM_PROMPT 严格保留 Markdown 语法 / 公式 $...$ / 代码块 / 图片引用 / 专有名词。

PDF 解析（PDF→英文 md）仍由 mineru 隔离 CLI 负责（见 pdf_parser），不在此处。
"""
from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from shared.config import get_deepseek_config
from shared.errors import TutorError
from shared.logging_config import get_logger

logger = get_logger("knowledge_mcp.md_translator")

SYSTEM_PROMPT = """你是专业的学术论文翻译助手。将用户给出的英文 Markdown 翻译成中文，严格遵守以下规则：

1. 保留所有 Markdown 语法：标题（#、##）、列表、加粗、斜体、表格、代码块、引用块。
2. 行内公式 $...$ 和块级公式 $$...$$ 保持原样，不翻译公式内部任何字符。
3. 图片引用 ![](images/...) 与 HTML <img> 保持原样。
4. 代码块 ```lang ... ``` 保持原样，注释也不翻译。
5. 文献引用编号、URL、专有名词（人名、机构、模型名、数据集名）保持英文；首次出现时可在括号内附中文译名。
6. 表格内容翻译，表格分隔符（| --- |）保持原样。
7. 输出只包含翻译后的 Markdown 正文，不要添加"以下是翻译"之类的说明、前言或后记。
"""


def chunk_markdown(md: str, max_chars: int = 3000) -> list[str]:
    """按段落分块，每块不超过 max_chars。优先在 \\n\\n 处切。"""
    paragraphs = md.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for p in paragraphs:
        p_len = len(p) + 2
        if current_len + p_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [p]
            current_len = p_len
        else:
            current.append(p)
            current_len += p_len
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def translate_chunk(client: Any, chunk: str, model: str = "deepseek-chat", retries: int = 3) -> str:
    """翻译单块，带简单指数退避重试。"""
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": chunk},
                ],
                temperature=0.3,
                stream=False,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 — 重试，最后一次抛出
            if attempt < retries - 1:
                time.sleep(2**attempt)
                logger.info("md_translate.retry", attempt=attempt + 1, error=str(exc))
            else:
                raise
    return ""  # unreachable


def translate_chunks_concurrent(
    client: Any,
    chunks: list[str],
    model: str = "deepseek-chat",
    max_workers: int = 8,
    on_progress: Callable[[int, int, int], None] | None = None,
) -> list[str]:
    """并发翻译所有块，结果按原始顺序返回。"""
    n = len(chunks)
    results: list[str] = [""] * n
    if n == 0:
        return results
    if max_workers <= 1:
        for i, chunk in enumerate(chunks):
            results[i] = translate_chunk(client, chunk, model=model)
            if on_progress:
                on_progress(i + 1, n, i)
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_to_idx = {
            ex.submit(translate_chunk, client, chunk, model): i
            for i, chunk in enumerate(chunks)
        }
        completed = 0
        for fut in as_completed(fut_to_idx):
            idx = fut_to_idx[fut]
            results[idx] = fut.result()
            completed += 1
            if on_progress:
                on_progress(completed, n, idx)
    return results


def _build_deepseek_client() -> tuple[Any, str]:
    """用 shared.config 的 DeepSeek 配置构造 OpenAI 兼容客户端。无 key → DEPENDENCY_MISSING。"""
    cfg = get_deepseek_config()
    if not cfg:
        raise TutorError(
            "DEPENDENCY_MISSING",
            hint="markdown 翻译需要 DeepSeek：在 .env 设 DEEPSEEK_API_KEY",
        )
    from openai import OpenAI

    return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"]), cfg["model"]


def translate_markdown(
    md: str,
    *,
    lang_out: str = "zh",  # noqa: ARG001 — 当前 SYSTEM_PROMPT 固定译中文；保留参数供日后扩展
    client: Any | None = None,
    model: str | None = None,
    max_workers: int = 8,
    chunk_size: int = 3000,
) -> str:
    """把英文 Markdown 翻译成中文，返回译文。

    client 为空时用 shared.config 的 DeepSeek 配置自建（测试可注入假 client）。
    """
    if not md.strip():
        return ""
    if client is None:
        client, default_model = _build_deepseek_client()
        model = model or default_model
    model = model or "deepseek-chat"

    chunks = chunk_markdown(md, chunk_size)
    logger.info("md_translate.start", chunks=len(chunks), model=model, workers=max_workers)
    translated = translate_chunks_concurrent(client, chunks, model=model, max_workers=max_workers)
    logger.info("md_translate.done", chunks=len(chunks))
    return "\n\n".join(translated)
