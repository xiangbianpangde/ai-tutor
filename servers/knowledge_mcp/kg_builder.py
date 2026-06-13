"""KGBuilder Protocol + 三个实现。

合同来源:
  ai-tutor-system-design/specs/server-api-spec.md §1.2 build_knowledge_graph
  - depth=toc     : 纯规则
  - depth=concept : LLM 抽 concept + 关系
  - depth=full    : concept + 难度评分 + embedding

抽出 Protocol 的好处:
- server.py 不再 if/else 三种 depth，直接 get_builder(depth).build(...)
- ConceptKGBuilder / FullKGBuilder 当前 stub，未来切片实现时只改这两个类
- 调用方对 stub 的失败模式有保证（PLUGIN_NOT_AVAILABLE）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from shared.errors import TutorError
from shared.llm_client import LLMProvider
from shared.logging_config import get_logger
from shared.schemas import BuildKGResult
from shared.storage import RelationalStore

from .concept_enricher import ConceptEnricher
from .kg_enrich_adapter import (
    _build_toc,
    _compute_quality,
    _persist_kg,
    _split_sections,
    _to_mermaid,
)
from .kg_enrich_adapter import (
    build_kg_toc as _build_kg_toc_impl,
)

logger = get_logger("knowledge_mcp.kg_builder")


DepthMode = Literal["toc", "concept", "full"]


@runtime_checkable
class KGBuilder(Protocol):
    """所有 KG 构建器共同接口。

    实现类必须接受 (corpus_id, subject_slug, markdown_path, db) 并返回 BuildKGResult。
    """

    depth: DepthMode

    def build(
        self,
        *,
        corpus_id: str,
        subject_slug: str,
        markdown_path: Path,
        db: RelationalStore,
    ) -> BuildKGResult: ...


# --------------------------------------------------------------------------- #
# 实现 1: toc — 已就绪，纯规则
# --------------------------------------------------------------------------- #


@dataclass
class TocKGBuilder:
    depth: DepthMode = "toc"

    def build(
        self,
        *,
        corpus_id: str,
        subject_slug: str,
        markdown_path: Path,
        db: RelationalStore,
    ) -> BuildKGResult:
        kg_id, _concepts, edges, quality, mermaid = _build_kg_toc_impl(
            corpus_id=corpus_id,
            subject_slug=subject_slug,
            markdown_path=markdown_path,
            db=db,
        )
        return BuildKGResult(
            kg_id=kg_id,
            triples_count=len(edges),
            quality_report=quality,
            mermaid=mermaid,
        )


# --------------------------------------------------------------------------- #
# 实现 2: concept
# --------------------------------------------------------------------------- #


def _enrich_concepts(
    *, llm: LLMProvider | None, subject_slug: str, markdown_path: Path,
    max_workers: int = 4, checkpoint_path: Path | None = None,
):
    """toc 骨架 → 切节 → 批量并行 enrich。concept 和 full 共用的前半段。

    返回 (enriched_concepts, edges, per_concept_warnings)。
    llm 不可用 → PLUGIN_NOT_AVAILABLE；markdown 缺失 → CORPUS_NOT_FOUND；
    无标题 → KG_QUALITY_GATE_FAILED。单 concept enrich 失败容错（保留 toc 默认）。
    P1 #5：有界并行（max_workers）+ 可选断点续跑（checkpoint_path），支撑数百概念规模。
    """
    from .batch_enrich import EnrichCheckpoint, batch_enrich

    if llm is None:
        raise TutorError(
            "PLUGIN_NOT_AVAILABLE",
            hint="需要 LLMProvider；通过构造器或 get_builder(depth, llm=...) 注入",
        )
    if not markdown_path.exists():
        raise TutorError("CORPUS_NOT_FOUND", hint=str(markdown_path))

    concepts, edges = _build_toc(subject_slug=subject_slug, markdown_path=markdown_path)
    if not concepts:
        raise TutorError(
            "KG_QUALITY_GATE_FAILED",
            hint="markdown 中没有任何 # 标题，无法生成 concept/full 模式 KG",
        )

    sections = _split_sections(markdown_path, concepts)
    checkpoint = None
    if checkpoint_path is not None:
        checkpoint = EnrichCheckpoint(checkpoint_path)
        checkpoint.load()
    enriched, warnings = batch_enrich(
        enricher=ConceptEnricher(llm=llm),
        concepts=concepts,
        sections=sections,
        max_workers=max_workers,
        checkpoint=checkpoint,
    )

    # 关系抽取（12 种语义关系）：在结构边 part_of/prerequisite_strong 之上，
    # 用一次 LLM 调用补全其余 10 种「概念对」关系。失败即降级（结构边保留）。
    from .relation_extractor import RelationExtractor

    rel_edges, rel_warnings = RelationExtractor(llm=llm).extract(
        concepts=enriched, existing_edges=edges,
    )
    edges = edges + rel_edges
    warnings = warnings + rel_warnings
    return enriched, edges, warnings


@dataclass
class ConceptKGBuilder:
    """depth=concept：toc 骨架 + 对每个 concept 调 ConceptEnricher 富化。

    流程:
    1. _build_toc 拿骨架 concepts + edges（part_of / prerequisite_strong）
    2. _split_sections 把 markdown 切成 {concept_id: 该节正文}
    3. 对每个 concept 调 ConceptEnricher.enrich：
       - definition / informal_description / examples / common_misconceptions
       - bloom_level 校正 / confidence 自评
       - 单个失败保留 toc 默认值（容错）
       - LLMProvider 整体不可用 → 抛 PLUGIN_NOT_AVAILABLE 让调用方决定
    4. _compute_quality + _to_mermaid + _persist_kg（version="concept-v1"）

    后续切片: 12 种 SemanticRelation 推断（当前只保留 part_of + prerequisite_strong）。
    """

    llm: LLMProvider | None = None
    depth: DepthMode = "concept"
    max_workers: int = 4
    checkpoint_path: Path | None = None

    def build(
        self,
        *,
        corpus_id: str,
        subject_slug: str,
        markdown_path: Path,
        db: RelationalStore,
    ) -> BuildKGResult:
        # 1-3) toc + 切节 + 批量并行 enrich（共用 pipeline）
        enriched, edges, per_concept_warnings = _enrich_concepts(
            llm=self.llm, subject_slug=subject_slug, markdown_path=markdown_path,
            max_workers=self.max_workers, checkpoint_path=self.checkpoint_path,
        )

        # 4) quality + mermaid
        quality = _compute_quality(enriched, edges)
        if per_concept_warnings:
            # 只挂前 5 条避免 quality_report 膨胀
            quality.warnings.extend(per_concept_warnings[:5])
            if len(per_concept_warnings) > 5:
                quality.warnings.append(
                    f"...另有 {len(per_concept_warnings) - 5} 条 enrich 警告"
                )
        mermaid = _to_mermaid(enriched, edges)

        # 5) persist
        kg_id = f"{corpus_id}-kg-concept-v1"
        _persist_kg(
            db=db,
            kg_id=kg_id,
            subject_slug=subject_slug,
            corpus_id=corpus_id,
            version="concept-v1",
            concepts=enriched,
            edges=edges,
            quality=quality,
            manifest={
                "depth": "concept",
                "source": str(markdown_path),
                "enrich_warnings": len(per_concept_warnings),
            },
        )

        logger.info(
            "build_kg_concept.done",
            kg_id=kg_id,
            concepts=len(enriched),
            edges=len(edges),
            warnings=len(per_concept_warnings),
            avg_conf=round(quality.avg_confidence, 3),
        )

        return BuildKGResult(
            kg_id=kg_id,
            triples_count=len(edges),
            quality_report=quality,
            mermaid=mermaid,
        )


# --------------------------------------------------------------------------- #
# 实现 3: full
# --------------------------------------------------------------------------- #


@dataclass
class FullKGBuilder:
    """depth=full：concept enrich + 确定性难度校准 + 本地 embedding 向量。

    难度校准用可解释加权公式（kg_full.compute_calibrated_difficulty），
    embedding 用 numpy feature-hashing 词频向量（零额外依赖）。装了 chromadb
    时额外把向量写入一个 collection（可选增强）。
    """

    llm: LLMProvider | None = None
    depth: DepthMode = "full"
    max_workers: int = 4
    checkpoint_path: Path | None = None

    def build(
        self,
        *,
        corpus_id: str,
        subject_slug: str,
        markdown_path: Path,
        db: RelationalStore,
    ) -> BuildKGResult:
        from .kg_full import build_embeddings, compute_calibrated_difficulty
        from .time_estimator import estimate_time_min

        # 1-3) 复用 concept enrich pipeline（批量并行 + 可选断点续跑）
        enriched, edges, per_concept_warnings = _enrich_concepts(
            llm=self.llm, subject_slug=subject_slug, markdown_path=markdown_path,
            max_workers=self.max_workers, checkpoint_path=self.checkpoint_path,
        )

        # 4) 时长校准（先）+ 难度校准 + embedding，写回每个 concept
        #    先估时长（用非时间特征），再算难度（其 time_norm 用上校准后的时长，告别恒 30）
        embeddings = build_embeddings(enriched)
        full_concepts = []
        for c in enriched:
            est_time = estimate_time_min(c)
            timed_difficulty = c.difficulty.model_copy(
                update={"typical_learning_time_min": est_time}
            )
            c = c.model_copy(update={"difficulty": timed_difficulty})
            diff = compute_calibrated_difficulty(c)
            new_difficulty = c.difficulty.model_copy(update={"calibrated_difficulty": diff})
            full_concepts.append(
                c.model_copy(update={
                    "difficulty": new_difficulty,
                    "embedding": embeddings.get(c.id),
                })
            )

        # 5) quality + mermaid
        quality = _compute_quality(full_concepts, edges)
        if per_concept_warnings:
            quality.warnings.extend(per_concept_warnings[:5])
            if len(per_concept_warnings) > 5:
                quality.warnings.append(
                    f"...另有 {len(per_concept_warnings) - 5} 条 enrich 警告"
                )
        mermaid = _to_mermaid(full_concepts, edges)

        # 6) 可选 chromadb 向量索引（装了才做，失败不影响主流程）
        chroma_indexed = _try_index_chromadb(corpus_id, full_concepts, embeddings)

        # 7) persist（version=full-v1）
        kg_id = f"{corpus_id}-kg-full-v1"
        avg_diff = (
            sum(c.difficulty.calibrated_difficulty or 0 for c in full_concepts)
            / max(len(full_concepts), 1)
        )
        _persist_kg(
            db=db,
            kg_id=kg_id,
            subject_slug=subject_slug,
            corpus_id=corpus_id,
            version="full-v1",
            concepts=full_concepts,
            edges=edges,
            quality=quality,
            manifest={
                "depth": "full",
                "source": str(markdown_path),
                "enrich_warnings": len(per_concept_warnings),
                "avg_calibrated_difficulty": round(avg_diff, 4),
                "embedding_dim": len(next(iter(embeddings.values()), [])),
                "chromadb_indexed": chroma_indexed,
            },
        )

        logger.info(
            "build_kg_full.done",
            kg_id=kg_id,
            concepts=len(full_concepts),
            edges=len(edges),
            avg_difficulty=round(avg_diff, 3),
            chromadb=chroma_indexed,
        )
        return BuildKGResult(
            kg_id=kg_id,
            triples_count=len(edges),
            quality_report=quality,
            mermaid=mermaid,
        )


def _try_index_chromadb(corpus_id: str, concepts, embeddings: dict) -> bool:
    """装了 chromadb 则把向量写入 collection；否则静默跳过返回 False。"""
    import importlib.util

    if importlib.util.find_spec("chromadb") is None:
        return False
    try:
        import chromadb  # noqa: PLC0415

        client = chromadb.Client()
        coll = client.get_or_create_collection(name=f"kg-{corpus_id}")
        ids = [c.id for c in concepts if embeddings.get(c.id)]
        if not ids:
            return False
        id_set = set(ids)
        coll.upsert(
            ids=ids,
            embeddings=[embeddings[i] for i in ids],
            documents=[next(iter(c.names), c.id) for c in concepts if c.id in id_set],
        )
        return True
    except Exception as exc:  # noqa: BLE001 — 向量库失败不影响主 KG
        logger.warning("build_kg_full.chromadb_failed", error=str(exc))
        return False


# --------------------------------------------------------------------------- #
# 工厂
# --------------------------------------------------------------------------- #


_BUILDERS: dict[str, type] = {
    "toc": TocKGBuilder,
    "concept": ConceptKGBuilder,
    "full": FullKGBuilder,
}


def get_builder(
    depth: DepthMode,
    *,
    llm: LLMProvider | None = None,
    max_workers: int = 4,
    checkpoint_path: Path | None = None,
) -> KGBuilder:
    cls = _BUILDERS.get(depth)
    if cls is None:
        raise TutorError(
            "DEPENDENCY_MISSING",
            hint=f"未知 depth={depth!r}（支持: {', '.join(_BUILDERS)}）",
        )
    if depth in ("concept", "full"):
        # 透传并行度 + 断点续跑路径，使 checkpoint 在工厂路径（server 用）也可达
        return cls(llm=llm, max_workers=max_workers, checkpoint_path=checkpoint_path)
    return cls()
