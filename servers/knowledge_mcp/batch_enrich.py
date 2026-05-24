"""批量 KG 富化 (P1 #5) — 有界并行 + 断点续跑。

问题（SYSTEM-AUDIT #5）：_enrich_concepts 逐个 concept 串行调 LLM，800 概念 ~40min，
中途失败要从头再来。已验证最大规模仅 20 概念。

方案：
- 有界并行：ThreadPoolExecutor（LLM 调用是 I/O 密集），max_workers 限流避免触发 rate limit。
  enricher 无状态、LLM provider 线程安全（MockLLM 已加锁，OpenAI client 本身并发安全）。
- 断点续跑：EnrichCheckpoint 以 JSONL 增量落盘，每完成一个 concept 追加一行；重启时
  load() 跳过已完成的，只富化剩余。append-only，崩溃最多丢最后一行（下次重做该条）。
- 容错语义与原串行版一致：单 concept 失败保留 toc 默认 + warning；整体 provider 不可用
  （PLUGIN_NOT_AVAILABLE）则上抛让调用方降级。结果按原 concept 顺序组装。
"""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.schemas import Concept

logger = get_logger("knowledge_mcp.batch_enrich")


class EnrichCheckpoint:
    """JSONL 增量断点：concept_id → (enriched Concept, warning)。"""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._done: dict[str, tuple[Concept, str | None]] = {}
        self._lock = threading.Lock()

    def load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    concept = Concept.model_validate(rec["concept"])
                except Exception:  # noqa: BLE001 — 跳过损坏/半截行
                    continue
                self._done[concept.id] = (concept, rec.get("warning"))

    def get(self, concept_id: str) -> tuple[Concept, str | None] | None:
        return self._done.get(concept_id)

    def record(self, concept: Concept, warning: str | None) -> None:
        with self._lock:
            if concept.id in self._done:
                return
            self._done[concept.id] = (concept, warning)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(
                {"concept": concept.model_dump(mode="json"), "warning": warning},
                ensure_ascii=False,
            )
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")


def batch_enrich(
    *,
    enricher,
    concepts: list[Concept],
    sections: dict[str, str],
    max_workers: int = 4,
    checkpoint: EnrichCheckpoint | None = None,
) -> tuple[list[Concept], list[str]]:
    """并行富化一批 concept，返回 (按原顺序的 enriched, warnings)。"""
    results: dict[str, tuple[Concept, str | None]] = {}
    todo: list[Concept] = []
    for c in concepts:
        cached = checkpoint.get(c.id) if checkpoint is not None else None
        if cached is not None:
            results[c.id] = cached
        else:
            todo.append(c)

    plugin_error: TutorError | None = None

    def _work(c: Concept):
        body = sections.get(c.id, "")
        try:
            ec, w = enricher.enrich(concept=c, body_text=body)
            return c.id, ec, w, None
        except TutorError as exc:
            if exc.code == "PLUGIN_NOT_AVAILABLE":
                return c.id, c, None, exc
            return c.id, c, f"{exc.code} {exc.message}", None
        except Exception as exc:  # noqa: BLE001 — 单概念非预期异常降级为 warning，不中止整批
            return c.id, c, f"enrich_failed: {type(exc).__name__}: {exc}", None

    if todo:
        workers = max(1, min(max_workers, len(todo)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for cid, ec, w, err in ex.map(_work, todo):
                if err is not None:
                    plugin_error = err
                    continue
                results[cid] = (ec, w)
                if checkpoint is not None:
                    checkpoint.record(ec, w)

    if plugin_error is not None:
        # 整体 provider 不可用：上抛，让调用方决定降级（与串行版一致）
        raise plugin_error

    enriched: list[Concept] = []
    warnings: list[str] = []
    for c in concepts:
        ec, w = results.get(c.id, (c, None))
        enriched.append(ec)
        if w:
            warnings.append(f"{c.id}: {w}")

    logger.info(
        "batch_enrich.done",
        total=len(concepts), enriched=len(todo),
        resumed=len(concepts) - len(todo), workers=max_workers,
    )
    return enriched, warnings
