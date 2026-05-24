"""knowledge-mcp FastMCP server 入口。

暴露的 Tool（spine 切片只实现 acquire + build + query 的最小路径；
review_kg / update_kg / resolve_conflicts 留下下切片）：

- acquire_subject  : 单文件版（pdf/md）；多源/视频/web 见 acquisition_adapter
- build_knowledge_graph: depth ∈ toc(纯规则) / concept(LLM富化) / full(+难度校准+embedding)
- query_knowledge  : query_type ∈ concept / neighbors / path / subgraph
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP

from shared.config import load_env
from shared.errors import TutorError
from shared.llm_cache import CachedLLMProvider
from shared.llm_client import LLMProvider, StubLLMProvider
from shared.logging_config import configure_logging, get_logger
from shared.providers.deepseek import DeepSeekProvider
from shared.models import KnowledgeGraphRow, RelationRow
from shared.models import ConceptRow as ConceptRowORM
from shared.schemas import (
    AcquireResult,
    ArtifactURI,
    BuildKGResult,
    KgEditAction,
    KgUpdateResult,
    ReviewKGResult,
)
from shared.storage import FileStore, RelationalStore

from .acquisition_adapter import AcquireSource, acquire as acquire_impl
from .kg_builder import DepthMode, get_builder
from .kg_diff import diff_kg as diff_kg_impl
from .kg_query import (
    extract_subgraph as extract_subgraph_impl,
    shortest_learning_path as shortest_learning_path_impl,
)
from .kg_review import review_kg as review_kg_impl
from .kg_rollback import rollback_kg as rollback_kg_impl
from .kg_update import update_kg as update_kg_impl
from .resolve_conflicts import find_conflicts as find_conflicts_impl


configure_logging()
logger = get_logger("knowledge_mcp.server")


mcp: FastMCP = FastMCP("knowledge-mcp")


# --------------------------------------------------------------------------- #
# 依赖装配
# --------------------------------------------------------------------------- #


def _file_store() -> FileStore:
    root = os.environ.get("AI_TUTOR_DATA_ROOT", str(Path("data").resolve()))
    return FileStore(root)


_DB_INITED: dict[str, bool] = {}


def _db() -> RelationalStore:
    store = RelationalStore.from_env()
    # 每个 url 第一次取时建表；之后 no-op（避免 review/update 等 tool 假设表已存在）
    if not _DB_INITED.get(store.url):
        store.init_schema()
        _DB_INITED[store.url] = True
    return store


_LLM_SINGLETON: LLMProvider | None = None


def _llm() -> LLMProvider:
    """装配 LLM provider（带 L1 内存缓存）。

    优先级：
    1. 进程已存在的单例（避免重复构造 OpenAI 客户端 + 共享缓存）
    2. DeepSeekProvider.from_env()（从 .env / 环境变量取 key）
    3. 否则 StubLLMProvider（.chat 抛 PLUGIN_NOT_AVAILABLE，让调用方报错指引）
    """
    global _LLM_SINGLETON
    if _LLM_SINGLETON is not None:
        return _LLM_SINGLETON

    load_env()  # 兼容把 .env 放在父目录的场景
    inner = DeepSeekProvider.from_env() or StubLLMProvider()
    if isinstance(inner, StubLLMProvider):
        _LLM_SINGLETON = inner
        return _LLM_SINGLETON
    # 真实 provider 加一层 L1 缓存
    _LLM_SINGLETON = CachedLLMProvider(inner=inner, max_size=256)
    logger.info(
        "llm.configured",
        provider=getattr(inner, "name", "?"),
        model=getattr(inner, "model", "?"),
    )
    return _LLM_SINGLETON


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #


@mcp.tool()
async def acquire_subject(
    subject: str,
    sources: list[dict[str, str]],
    user_id: str = "default",
    version: str | None = None,
) -> AcquireResult:
    """从一个或多个来源采集语料并落库。

    Args:
        subject: 科目显示名，如 "高等数学"
        sources: 来源列表。每项 `{"type": "file"|"web"|"video", "uri": "..."}`。
                 当前切片仅 type="file" 完整实现；web/video 抛 DEPENDENCY_MISSING。
        user_id: 用户标识；默认 "default"
        version: 教材版本字符串

    Returns:
        AcquireResult，含 corpus_id 与每个 markdown 产物的 artifact URI
    """
    db = _db()
    db.init_schema()  # spine 期一键建表
    fs = _file_store()

    typed_sources = [AcquireSource(type=s["type"], uri=s["uri"]) for s in sources]  # type: ignore[arg-type]

    manifest, corpus_id = acquire_impl(
        subject=subject,
        version=version,
        sources=typed_sources,
        user_id=user_id,
        file_store=fs,
        db=db,
        mineru_cmd=os.environ.get("MINERU_CMD"),
    )

    artifacts = []
    for key, path_str in manifest.file_paths.items():
        if key == "markdown":  # 别名，跳过避免重复
            continue
        p = Path(path_str)
        artifacts.append(
            ArtifactURI(
                uri=f"file:///{p.as_posix()}",
                mime_type="text/markdown",
                size_bytes=p.stat().st_size,
            )
        )

    return AcquireResult(
        corpus_id=corpus_id,
        toc=[],  # toc 由 build_knowledge_graph(depth=toc) 产出
        stats={
            "total_chapters": manifest.total_chapters,
            "total_sections": manifest.total_sections,
            "estimated_concepts": manifest.estimated_concepts,
            "sources_used": [s.format for s in manifest.sources],
        },
        artifacts=artifacts,
        next_step_suggestion="build_knowledge_graph",
    )


@mcp.tool()
async def build_knowledge_graph(
    corpus_id: str,
    depth: DepthMode = "toc",
) -> BuildKGResult:
    """从语料库构建知识图谱。

    depth=toc:     纯规则抽章节骨架
    depth=concept: LLM 富化每个 concept（定义/例子/误解/置信度）
    depth=full:    concept + 确定性难度校准 + 本地 embedding 向量（可选 chromadb）
    """
    db = _db()
    with db.session() as s:
        from shared.models import Corpus as CorpusRow
        corpus = s.get(CorpusRow, corpus_id)
        if corpus is None:
            raise TutorError("CORPUS_NOT_FOUND", hint=corpus_id)
        manifest = corpus.manifest_json
        subject_slug = corpus.subject_id
        corpus_user = corpus.user_id

    md_path = Path(manifest["file_paths"]["markdown"])
    result = get_builder(depth, llm=_llm()).build(
        corpus_id=corpus_id,
        subject_slug=subject_slug,
        markdown_path=md_path,
        db=db,
    )

    # 关闭采集→教学的闭环：建/更新 Subject 行并把 kg_id 指向刚建的 KG，
    # 这样 tutoring 工具（start_learning_session 等）可直接用 subject_id=subject_slug，
    # 无需手工写回 subject.kg_id。subject_id 即科目名的 slug。
    from shared.models import Subject
    with db.session() as s:
        subj = s.get(Subject, subject_slug)
        if subj is None:
            subj = Subject(id=subject_slug, user_id=corpus_user, display_name=subject_slug)
            s.add(subj)
        subj.kg_id = result.kg_id
        s.commit()

    return result


# --------------------------------------------------------------------------- #
# KG 人工确认（adopted-fixes 修正 1）— stub
# --------------------------------------------------------------------------- #


@mcp.tool()
async def review_kg(
    kg_id: str,
    mode: Literal["quick", "full"] = "quick",
    limit: int = 20,
) -> ReviewKGResult:
    """KG 人工确认（adopted-fixes 修正 1）。

    放在 build_knowledge_graph 与 start_learning_session 之间。

    quick (默认): 取 confidence 最低的 `limit` 个概念 + Quality Gate warnings + 缩略 Mermaid
    full:        取 confidence < 0.5 全部 + 完整 Mermaid 图，配合 update_kg 交互编辑
    """
    db = _db()
    return review_kg_impl(db=db, kg_id=kg_id, mode=mode, limit=limit)


@mcp.tool()
async def update_kg(
    kg_id: str,
    actions: list[dict],
    mode: Literal["in_place", "versioned"] = "in_place",
) -> KgUpdateResult:
    """根据 review_kg 的反馈批量编辑 KG。

    6 种 op: edit_definition / add_edge / remove_edge / delete_concept /
            merge_concepts / approve_all

    mode:
    - "in_place"  (默认): 直接在 kg_id 上修改 + audit trail（K2 行为）
    - "versioned" (K3):   复制 KG 到新 kg_id（parent_kg_id 指向原），原 KG 不变；
                          搭配 diff_kg / rollback_kg 实现版本树管理
    """
    db = _db()
    typed_actions = [KgEditAction.model_validate(a) for a in actions]
    return update_kg_impl(db=db, kg_id=kg_id, actions=typed_actions, mode=mode)


@mcp.tool()
async def diff_kg(
    kg_id_a: str,
    kg_id_b: str,
) -> dict[str, Any]:
    """对比两个 KG 版本（按 base_id 对齐）。

    返回: {kg_id_a, kg_id_b, added, removed, definition_changed,
           confidence_changed, edges_added, edges_removed, summary}
    """
    db = _db()
    d = diff_kg_impl(db=db, kg_id_a=kg_id_a, kg_id_b=kg_id_b)
    return {
        "kg_id_a": d.kg_id_a,
        "kg_id_b": d.kg_id_b,
        "added": d.added,
        "removed": d.removed,
        "definition_changed": d.definition_changed,
        "confidence_changed": d.confidence_changed,
        "edges_added": d.edges_added,
        "edges_removed": d.edges_removed,
        "summary": d.summary,
    }


@mcp.tool()
async def rollback_kg(
    subject_id: str,
    target_kg_id: str,
) -> dict[str, Any]:
    """回退 subject 的当前 KG 到祖先版本。

    target_kg_id 必须是当前 subject.kg_id 的祖先（沿 parent_kg_id 链可达）。
    不删除任何 KG 行（保留审计）；BKT 因 base_id 设计自动跨版本继承。
    """
    db = _db()
    return rollback_kg_impl(db=db, subject_id=subject_id, target_kg_id=target_kg_id)


@mcp.tool()
async def resolve_conflicts(kg_id: str) -> list[dict]:
    """检测 KG 中的结构 / 语义冲突。

    5 种结构冲突（纯算法）:
    - circular_prerequisite    前置成环
    - reversed_prerequisite    A→B 且 B→A
    - duplicate_concept        同名不同 id
    - broken_reference         悬空边
    - isolated_subgraph        孤岛子图

    contradictory_definition（语义对立）需 LLM，后续切片接入。

    返回: list[{type, concept_a, concept_b, description, suggested_resolution, detail}]
    """
    db = _db()
    conflicts = find_conflicts_impl(db=db, kg_id=kg_id)
    return [c.to_dict() for c in conflicts]


@mcp.tool()
async def query_knowledge(
    kg_id: str,
    query: str,
    query_type: Literal["concept", "neighbors", "path", "subgraph"] = "concept",
    max_results: int = 10,
    target: str | None = None,
    depth: int = 1,
) -> dict[str, Any]:
    """KG 查询。

    concept:   按名称/id 精确或模糊匹配
    neighbors: 给定 concept_id，返回 upstream(prerequisite_strong 指向自己) + downstream + part_of 父
    path:      sql query=起点 concept_id，target=终点 concept_id；返回沿 prerequisite_strong
               的最短学习路径（A→B 表示 A 是 B 前置）。无路径 → found=False。
    subgraph:  query=中心 concept_id，depth=半径（无向 BFS 跳数）；返回 N 跳邻域子图。
    """
    if query_type == "path":
        return shortest_learning_path_impl(
            db=_db(), kg_id=kg_id, from_id=query, to_id=target or query,
        )
    if query_type == "subgraph":
        return extract_subgraph_impl(
            db=_db(), kg_id=kg_id, center_id=query, depth=depth,
        )

    db = _db()
    with db.session() as s:
        kg = s.get(KnowledgeGraphRow, kg_id)
        if kg is None:
            raise TutorError("KG_NOT_FOUND", hint=kg_id)

        if query_type == "concept":
            q = s.query(ConceptRowORM).filter_by(kg_id=kg_id)
            rows = q.filter(
                (ConceptRowORM.id == query) | (ConceptRowORM.name_primary.contains(query))
            ).limit(max_results).all()
            return {
                "results": [
                    {
                        "concept_id": r.id,
                        "name": r.name_primary,
                        "definition_preview": r.definition[:160],
                        "abstract_level": r.abstract_level,
                        "confidence": r.confidence,
                    }
                    for r in rows
                ]
            }

        if query_type == "neighbors":
            up = s.query(RelationRow).filter_by(kg_id=kg_id, to_id=query, type="prerequisite_strong").all()
            down = s.query(RelationRow).filter_by(kg_id=kg_id, from_id=query, type="prerequisite_strong").all()
            parents = s.query(RelationRow).filter_by(kg_id=kg_id, from_id=query, type="part_of").all()
            return {
                "concept_id": query,
                "upstream": [r.from_id for r in up],
                "downstream": [r.to_id for r in down],
                "parents": [r.to_id for r in parents],
            }

        raise TutorError("DEPENDENCY_MISSING", hint=f"未知 query_type={query_type}")


@mcp.tool()
async def health() -> dict[str, Any]:
    """轻量自检：DB 可达 + KG 数。"""
    db = _db()
    try:
        with db.session() as s:
            kg_count = s.query(KnowledgeGraphRow).count()
        return {
            "ok": True,
            "server": "knowledge-mcp",
            "version": "0.1.0",
            "kg_count": kg_count,
            "db_url": db.url,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #


def main() -> None:
    import sys

    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    logger.info("knowledge_mcp.start", transport=transport)
    if transport == "http":
        mcp.run(transport="sse", host="0.0.0.0", port=8001)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
