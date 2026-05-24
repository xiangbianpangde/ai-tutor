"""audio generator — 朗读讲稿（可选合成 .mp3）。

默认：生成朗读讲稿 markdown（每概念一段口语化讲解 + [停顿] 标记），
人或 TTS 都能直接念。若环境装了 edge-tts，则额外把全文合成 narration-{kg_id}.mp3。

讲稿措辞偏口语 + 短句，适合听觉学习（步行 / 通勤复习）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from shared.logging_config import get_logger
from shared.schemas import ArtifactURI
from shared.storage import RelationalStore

from ._kg_read import load_sorted_concepts

logger = get_logger("digest_mcp.audio")

_HAS_EDGE_TTS = importlib.util.find_spec("edge_tts") is not None
_VOICE = "zh-CN-XiaoxiaoNeural"


def _narration_text(kg, rows) -> str:
    """生成纯朗读文本（不含 markdown 标记，给 TTS 用）。"""
    parts: list[str] = [
        f"欢迎来到 {kg.subject_id} 的音频复习。本节共 {len(rows)} 个概念。",
    ]
    for idx, r in enumerate(rows, 1):
        full = r.full_json or {}
        seg = [f"第 {idx} 个，{r.name_primary or r.id}。"]
        if r.definition:
            seg.append(r.definition)
        if r.informal_description:
            seg.append(f"通俗地说，{r.informal_description}")
        examples = [e.get("text", "") for e in (full.get("examples") or []) if e.get("text")]
        if examples:
            seg.append(f"举个例子，{examples[0]}")
        parts.append(" ".join(seg))
    parts.append("本节复习结束，记得回顾薄弱的概念。")
    return "\n".join(parts)


def _narration_markdown(kg, rows) -> str:
    """带 [停顿] 标记和结构的讲稿 markdown（给人读 / 编辑）。"""
    lines = [
        f"# 🎧 音频讲稿 — {kg.subject_id}",
        "",
        f"> {len(rows)} 个概念 · 朗读约 {max(1, len(rows))} 分钟 · `[停顿]` = 1 秒停顿",
        "",
        f"开场：欢迎来到 {kg.subject_id} 的音频复习。本节共 {len(rows)} 个概念。[停顿]",
        "",
    ]
    for idx, r in enumerate(rows, 1):
        full = r.full_json or {}
        lines.append(f"## {idx}. {r.name_primary or r.id}")
        lines.append("")
        if r.definition:
            lines.append(f"{r.definition}[停顿]")
        if r.informal_description:
            lines.append(f"通俗地说，{r.informal_description}[停顿]")
        examples = [e.get("text", "") for e in (full.get("examples") or []) if e.get("text")]
        if examples:
            lines.append(f"举个例子：{examples[0]}")
        lines.append("")
    lines.append("结束语：本节复习结束，记得回顾薄弱的概念。")
    return "\n".join(lines)


async def _synthesize_mp3(text: str, out_path: Path) -> None:
    import edge_tts  # noqa: PLC0415

    communicate = edge_tts.Communicate(text, _VOICE)
    await communicate.save(str(out_path))


def _run_async(coro):
    """跑一个 coroutine 到完成。

    若当前已在运行的 event loop 里（被 async MCP tool 间接调用），
    asyncio.run 会 RuntimeError → 改在独立 worker thread 里跑。
    否则直接 asyncio.run。
    """
    import asyncio as _aio

    try:
        _aio.get_running_loop()
    except RuntimeError:
        return _aio.run(coro)  # 无运行中的 loop

    # 有 running loop：放到独立线程（带自己的新 loop）执行
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_aio.run, coro).result()


def generate_audio(
    *, db: RelationalStore, kg_id: str, out_dir: Path,
    synthesize: bool = True,
) -> ArtifactURI:
    """生成朗读讲稿 .md。装了 edge-tts 且 synthesize=True → 额外合成 .mp3 并返回它。"""
    kg, rows = load_sorted_concepts(db, kg_id)
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 讲稿 markdown 总是生成（基线产物）
    md_path = out_dir / f"narration-{kg_id}.md"
    md_path.write_text(_narration_markdown(kg, rows), encoding="utf-8")
    md_artifact = ArtifactURI(
        uri=f"file:///{md_path.as_posix()}",
        mime_type="text/markdown",
        size_bytes=md_path.stat().st_size,
    )

    if _HAS_EDGE_TTS and synthesize and rows:
        mp3_path = out_dir / f"narration-{kg_id}.mp3"
        try:
            _run_async(_synthesize_mp3(_narration_text(kg, rows), mp3_path))
            if mp3_path.exists() and mp3_path.stat().st_size > 0:
                logger.info("audio.done", kg_id=kg_id, fmt="mp3", file=str(mp3_path))
                return ArtifactURI(
                    uri=f"file:///{mp3_path.as_posix()}",
                    mime_type="audio/mpeg",
                    size_bytes=mp3_path.stat().st_size,
                )
        except Exception as exc:  # noqa: BLE001 — TTS（多半网络）失败回退讲稿
            logger.warning("audio.tts_failed_fallback_script", error=str(exc))

    logger.info("audio.done", kg_id=kg_id, fmt="script_md", concepts=len(rows), file=str(md_path))
    return md_artifact
