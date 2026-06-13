"""backend.pipeline.data_pipeline —— 采集→清洗→结构化建图编排（M-014）。

三阶段管线，每阶段一个可注入 runner（默认包 v1 research_adapter/acquisition_adapter/
kg_enrich_adapter；测试注入假 runner，不碰网络/LLM/演示资产）。建图后过 NoiseGate 红线。

设计为可经 M-007 TaskManager 后台异步跑（`pipeline.run` 接 ProgressReporter）。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .noise_gate import NoiseGate


class _Reporter(Protocol):
    def update(self, progress: float, message: str | None = None) -> None: ...


# 阶段 runner：(reporter, context) -> 新 context（dict 累积传递）
StageRunner = Callable[[_Reporter, dict[str, Any]], dict[str, Any]]


class DataPipeline:
    """采集→清洗→结构化三阶段编排 + 噪声红线。stage runner 注入。"""

    def __init__(
        self,
        *,
        acquire: StageRunner,
        clean: StageRunner,
        structure: StageRunner,
        noise_gate: NoiseGate | None = None,
    ) -> None:
        self._acquire = acquire
        self._clean = clean
        self._structure = structure
        self._noise_gate = noise_gate or NoiseGate()

    def run(self, reporter: _Reporter, *, subject_id: str, sources: list[Any]) -> dict[str, Any]:
        ctx: dict[str, Any] = {"subject_id": subject_id, "sources": sources}

        reporter.update(0.05, "采集")
        ctx = self._acquire(reporter, ctx)
        reporter.update(0.4, "清洗去噪")
        ctx = self._clean(reporter, ctx)
        reporter.update(0.7, "结构化建图")
        ctx = self._structure(reporter, ctx)

        reporter.update(0.95, "噪声红线审计")
        audit = self._noise_gate.audit(ctx.get("concept_names", []))
        reporter.update(1.0, "完成")

        return {
            "subject_id": subject_id,
            "corpus_id": ctx.get("corpus_id"),
            "kg_id": ctx.get("kg_id"),
            "noise_audit": audit,
        }
