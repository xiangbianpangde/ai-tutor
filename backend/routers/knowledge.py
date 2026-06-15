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


@router.get("/subjects", summary="列出用户的科目（供学习中心选择，免手填不透明 ID）")
async def list_subjects(request: Request, user_id: str) -> dict:
    """返回该用户已建好图谱（可学）的科目，供前端做"我的科目"选择列表。

    独立验收发现：让新用户手填不透明科目 ID（slug）很懵——改成从列表点选。
    """
    from shared.models import ConceptRow, Subject

    store = request.app.state.store
    if store is None:
        return ok([])
    with store.session() as s:
        rows = s.query(Subject).filter_by(user_id=user_id).all()
        out = []
        for r in rows:
            if not r.kg_id:
                continue
            n = s.query(ConceptRow).filter_by(kg_id=r.kg_id).count()
            out.append({"subject_id": r.id, "display_name": r.display_name,
                        "kg_id": r.kg_id, "concepts": n})
    return ok(out)


@router.post("/subjects/import", status_code=202,
             summary="导入资料一键建科目（采集→建图→建科目，#21 零门槛入口）")
async def import_subject(
    request: Request,
    user_id: str = Body(..., embed=True),
    subject_name: str = Body(..., embed=True),
    markdown: str = Body(..., embed=True),
) -> dict:
    """把粘贴的 markdown 资料一键建成可学科目：采集→toc 建图（纯规则免 LLM）→建 Subject。

    异步返回 task_id；进度经 GET /api/tasks/{id} 轮询，完成后 subject_id 即可开学。
    解决 #21 最大摩擦点：新用户零资料 → 导入即得可学科目（数据管线 M-014 串成一键）。
    """
    import tempfile

    from shared.errors import TutorError

    store = request.app.state.store
    if store is None:
        raise TutorError("DATABASE_ERROR", hint="DB 未就绪")
    if not (markdown or "").strip():
        raise TutorError("IMPORT_EMPTY", hint="资料内容不能为空")
    manager = request.app.state.tasks
    config = request.app.state.config

    from shared.slug import slugify

    subject_slug = slugify(subject_name) or "subject"

    def job(reporter: ProgressReporter) -> dict[str, Any]:
        from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
        from servers.knowledge_mcp.kg_enrich_adapter import build_kg_toc
        from shared.models import Subject, User
        from shared.storage import FileStore

        with store.session() as s:
            if s.get(User, user_id) is None:
                s.add(User(id=user_id, display_name=user_id))
                s.commit()
        reporter.update(0.15, "写入资料")
        tmp_dir = Path(tempfile.mkdtemp())
        md_file = tmp_dir / f"{subject_slug}.md"
        md_file.write_text(markdown, encoding="utf-8")

        reporter.update(0.35, "采集语料")
        fs = FileStore(str(config.files_root))
        manifest, corpus_id = acquire(
            subject=subject_name, version="v1",
            sources=[AcquireSource(type="file", uri=str(md_file))],
            user_id=user_id, file_store=fs, db=store,
        )
        md_path = Path(manifest.file_paths["markdown"])

        reporter.update(0.65, "建知识图谱")
        kg_id, concepts, _edges, _quality, _mermaid = build_kg_toc(
            corpus_id=corpus_id, subject_slug=subject_slug, markdown_path=md_path, db=store,
        )

        reporter.update(0.9, "关联科目")
        with store.session() as s:
            subj = s.get(Subject, subject_slug)
            if subj is None:
                s.add(Subject(id=subject_slug, display_name=subject_name,
                              user_id=user_id, kg_id=kg_id))
            else:
                subj.kg_id = kg_id
            s.commit()
        reporter.update(1.0, "完成")
        return {"subject_id": subject_slug, "kg_id": kg_id, "concepts": len(concepts)}

    task_id = manager.submit("import_subject", job)
    return ok({"task_id": task_id, "subject_id": subject_slug})


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
