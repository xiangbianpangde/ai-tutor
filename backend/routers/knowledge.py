"""knowledge 引擎 router（前缀 /api/knowledge）。

C1：/health。C2：POST /subjects/{id}/graphs（**异步**构建 KG，M-007）。
后续波次迁入 acquire / query / review / update / diff / rollback / conflicts。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Body, Request

from ..middleware import ProgressReporter
from ..pipeline import NoiseGate
from ..responses import ok
from ._common import engine_router

router = engine_router("knowledge")


@router.get("/graphs/{kg_id}/noise", summary="KG 噪声红线审计（M-014，噪声<5%）")
async def kg_noise(kg_id: str, request: Request, threshold: float = 0.05) -> dict:
    """只读审计：禁类概念占比 + 是否过线。不改任何数据。"""
    store = request.app.state.store
    return ok(NoiseGate(threshold=threshold).audit_kg(store, kg_id))


def default_build_runner(
    reporter: ProgressReporter, *, store: Any, corpus_id: str, depth: str, **_: Any
) -> dict[str, Any]:
    """真实构建任务体：复用 v1 builder（toc 纯规则免 LLM；concept/full 需 LLM 注入，后续波次）。

    ⚠️ 仅供 demo/牺牲品语料运行——会写 KG。**不得对演示科目跑**（资产保护红线）。
    与 v1 server.py 不同：本 runner 不回写 subject.kg_id（避免改动既有 Subject 资产）。
    """
    from servers.knowledge_mcp.kg_builder import get_builder
    from shared.errors import TutorError
    from shared.models import Corpus

    reporter.update(0.1, "读取语料")
    with store.session() as s:
        corpus = s.get(Corpus, corpus_id)
        if corpus is None:
            raise TutorError("CORPUS_NOT_FOUND", hint=corpus_id)
        manifest = corpus.manifest_json
        subject_slug = corpus.subject_id
    md_path = Path(manifest["file_paths"]["markdown"])
    reporter.update(0.4, f"构建 KG（depth={depth}）")
    result = get_builder(depth).build(
        corpus_id=corpus_id, subject_slug=subject_slug, markdown_path=md_path, db=store
    )
    reporter.update(1.0, "完成")
    return {"kg_id": result.kg_id, "subject_slug": subject_slug, "depth": depth}


@router.post("/subjects/{subject_id}/graphs", status_code=202, summary="异步构建知识图谱（M-007）")
async def build_graph(
    subject_id: str,
    request: Request,
    corpus_id: str = Body(..., embed=True),
    depth: str = Body("toc", embed=True),
) -> dict:
    """提交后台构建任务，**立即**返回 task_id；进度经 GET /api/tasks/{id} 轮询（不阻塞 HTTP）。"""
    manager = request.app.state.tasks
    store = request.app.state.store
    # build_runner 可经 app.state 注入（测试用假 runner，避免真建图碰演示资产）
    runner = getattr(request.app.state, "build_runner", None) or default_build_runner

    def job(reporter: ProgressReporter) -> Any:
        return runner(reporter, store=store, corpus_id=corpus_id, depth=depth, subject_id=subject_id)

    task_id = manager.submit("build_kg", job)
    return ok({"task_id": task_id})
