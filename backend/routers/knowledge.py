"""knowledge 引擎 router（前缀 /api/knowledge）。

C1：/health。C2：POST /subjects/{id}/graphs（**异步**构建 KG，M-007）。
C3：POST /rag/query + /rag/validate（M-008 RAG 引擎，#9 AgenticRAG）。
后续波次迁入 acquire / query / review / update / diff / rollback / conflicts。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Body, Request

from ..middleware import ProgressReporter
from ..pipeline import NoiseGate
from ..rag import AnswerValidator, KGChunkSource, LexicalRetriever, RAGEngine
from ..responses import ok
from ._common import engine_router

router = engine_router("knowledge")


@router.get("/graphs/{kg_id}/view", summary="KG 可视化数据：概念 + 边（#5 力导向图）")
async def graph_view(kg_id: str, request: Request, limit: int = 500) -> dict:
    """只读返回 KG 的节点（概念）+ 边（关系），供前端力导向图渲染。"""
    from shared.errors import TutorError
    from shared.models import ConceptRow, RelationRow

    store = request.app.state.store
    if store is None:
        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")
    with store.session() as s:
        concepts = s.query(ConceptRow).filter_by(kg_id=kg_id).limit(limit).all()
        nodes = [
            {"id": c.id, "name": c.name_primary, "category": c.category,
             "abstract_level": c.abstract_level, "load": c.cognitive_load_estimate}
            for c in concepts
        ]
        ids = {c.id for c in concepts}
        edges = [
            {"from": e.from_id, "to": e.to_id, "type": e.type}
            for e in s.query(RelationRow).filter_by(kg_id=kg_id).all()
            if not e.deprecated and e.from_id in ids and e.to_id in ids
        ]
    return ok({"kg_id": kg_id, "nodes": nodes, "edges": edges,
               "node_count": len(nodes), "edge_count": len(edges)})


def _get_rag_engine(request: Request, kg_id: str) -> RAGEngine:
    """按 kg_id 取/建 RAG 引擎（每 kg_id 缓存——避免每次请求重扫概念建索引）。

    共享 app 的 cache（M-005）+ events（M-006）；LLM 法官经 app.state.rag_judge 注入（默认无）。
    """
    from shared.errors import TutorError

    store = request.app.state.store
    if store is None:
        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")
    engines: dict[str, RAGEngine] = getattr(request.app.state, "rag_engines", None)
    if engines is None:
        engines = {}
        request.app.state.rag_engines = engines
    engine = engines.get(kg_id)
    if engine is None:
        retriever = LexicalRetriever(KGChunkSource(store, kg_id))
        validator = AnswerValidator(llm_judge=getattr(request.app.state, "rag_judge", None))
        engine = RAGEngine(
            retriever, validator,
            cache=getattr(request.app.state, "cache", None),
            events=getattr(request.app.state, "events", None),
        )
        engines[kg_id] = engine
    return engine


@router.post("/rag/query", summary="RAG 检索（M-008，自主重检索 ≤3 轮）")
async def rag_query(
    request: Request,
    kg_id: str = Body(..., embed=True),
    query: str = Body(..., embed=True),
    top_k: int = Body(5, embed=True),
) -> dict:
    """在指定 KG 上做 RAG 检索，透明披露轮次/是否达标/top_score。"""
    engine = _get_rag_engine(request, kg_id)
    result = await engine.retrieve(query, top_k=top_k)
    return ok(result.to_dict())


@router.post("/rag/validate", summary="答案-引用源一致性验证（M-008，NLI 风格）")
async def rag_validate(
    request: Request,
    answer: str = Body(..., embed=True),
    sources: list[str] = Body(..., embed=True),
) -> dict:
    """验证答案是否被引用源支撑（回退启发式永不过度授信）。"""
    validator = AnswerValidator(llm_judge=getattr(request.app.state, "rag_judge", None))
    result = validator.validate(answer, sources)
    return ok(result.to_dict())


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
