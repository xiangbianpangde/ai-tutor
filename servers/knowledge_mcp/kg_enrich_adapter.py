"""build_knowledge_graph 的适配层。

depth=toc:     纯规则。从 markdown 的 #/## 抽 Concept 骨架 + prerequisite_strong 边。
depth=concept: TODO 下一切片：接 research_tool.ExtractResult.triples + LLM 二次增强
depth=full:    TODO 同上 + 难度评分 + embedding
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterator

from shared.errors import TutorError
from shared.logging_config import get_logger
from shared.models import ConceptRow, KnowledgeGraphRow, RelationRow
from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    QualityReport,
    Relation,
    SourceRef,
)
from shared.storage import RelationalStore

logger = get_logger("knowledge_mcp.kg_enrich")


_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*$")


from shared.slug import slugify as _slug  # noqa: E402  function alias


def _iter_headings(markdown: str) -> Iterator[tuple[int, str, int]]:
    """逐行扫 markdown，yield (level, title, line_no)。"""
    for line_no, line in enumerate(markdown.splitlines(), start=1):
        m = _HEADING_RE.match(line)
        if m:
            yield len(m.group("hashes")), m.group("title").strip(), line_no


def _bloom(level: int) -> str:
    """章节深度粗映射 Bloom 层级。"""
    return {1: "remember", 2: "understand", 3: "apply", 4: "analyze"}.get(level, "understand")


def _build_concept(
    *,
    subject_slug: str,
    chapter_counters: list[int],
    title: str,
    level: int,
    source_file: str,
    line_no: int,
) -> Concept:
    chapter_id = ".".join(str(n) for n in chapter_counters)
    cid = f"{subject_slug}:{chapter_id}:{_slug(title)}"

    # toc 模式：所有难度字段用启发式默认值（标注 confidence=0.4 留给后续增强）
    return Concept(
        id=cid,
        names=[title],
        category="definition" if level <= 2 else "method",
        definition=title,
        informal_description=f"来自 {Path(source_file).name} 行 {line_no} 的章节标题",
        classification=ConceptClassification(
            bloom_level=_bloom(level),
            abstract_level=min(0.3 + 0.15 * (level - 1), 0.85),
            domain=subject_slug,
        ),
        difficulty=ConceptDifficulty(
            prereq_count=max(level - 1, 0),
            prereq_max_depth=max(level - 1, 0),
            formula_density=0.3,
            coupling=0.3,
            cognitive_load_estimate=0.4,
            typical_learning_time_min=30,
        ),
        confidence=0.4,  # toc 模式：低置信，预期后续 review_kg / concept 模式增强
        sources=[SourceRef(type="textbook", ref=Path(source_file).name, page=str(line_no))],
    )


def _build_toc(
    *,
    subject_slug: str,
    markdown_path: Path,
) -> tuple[list[Concept], list[Relation]]:
    """从 markdown 章节生成 Concept + prerequisite_strong 边。"""
    text = markdown_path.read_text(encoding="utf-8")
    concepts: list[Concept] = []
    edges: list[Relation] = []

    counters: list[int] = []
    # parent_at_level[i] = level-(i+1) 的最近祖先 concept id；同时维护 level 之上的祖先
    parent_at_level: list[str | None] = []
    # prev_sibling_at_level[i] = level-(i+1) 的同级前一个 concept id
    prev_sibling_at_level: list[str | None] = []

    for level, title, line_no in _iter_headings(text):
        # ---- 1) 更新 counters 到 level 长度 ----
        if len(counters) >= level:
            counters = counters[: level - 1] + [counters[level - 1] + 1]
        else:
            while len(counters) < level - 1:
                counters.append(1)
            counters.append(1)

        # ---- 2) 清掉比当前 level 更深的栈条目 ----
        # 进入新 level 时，更深层的 sibling/parent 信息全部失效
        del parent_at_level[level:]
        del prev_sibling_at_level[level:]

        # ---- 3) 读父亲 + 同级前驱 ----
        parent_id = parent_at_level[level - 2] if level >= 2 and len(parent_at_level) >= level - 1 else None
        prev_sibling_id = prev_sibling_at_level[level - 1] if len(prev_sibling_at_level) >= level else None

        # ---- 4) 创建 concept ----
        concept = _build_concept(
            subject_slug=subject_slug,
            chapter_counters=counters,
            title=title,
            level=level,
            source_file=str(markdown_path),
            line_no=line_no,
        )
        concepts.append(concept)

        # ---- 5) 加边 ----
        if parent_id and parent_id != concept.id:
            edges.append(
                Relation(
                    from_id=concept.id,
                    to_id=parent_id,
                    type="part_of",
                    weight=0.9,
                    explanation=f"{title} 是上级章节的子项",
                    confidence=0.7,
                )
            )
        if prev_sibling_id and prev_sibling_id != concept.id:
            edges.append(
                Relation(
                    from_id=prev_sibling_id,
                    to_id=concept.id,
                    type="prerequisite_strong",
                    weight=0.6,
                    explanation="教材顺序：前一节是后一节的前置",
                    confidence=0.5,
                )
            )

        # ---- 6) 把当前节点写入栈 ----
        while len(parent_at_level) < level:
            parent_at_level.append(None)
        parent_at_level[level - 1] = concept.id

        while len(prev_sibling_at_level) < level:
            prev_sibling_at_level.append(None)
        prev_sibling_at_level[level - 1] = concept.id

    return concepts, edges


def _compute_quality(concepts: list[Concept], edges: list[Relation]) -> QualityReport:
    if not concepts:
        return QualityReport(
            overall="fail",
            chapter_coverage=0.0,
            isolated_nodes=0,
            cycles=0,
            avg_confidence=0.0,
            warnings=["KG 为空"],
        )
    node_ids = {c.id for c in concepts}
    connected = {e.from_id for e in edges} | {e.to_id for e in edges}
    isolated = node_ids - connected
    avg_conf = sum(c.confidence for c in concepts) / len(concepts)

    warnings: list[str] = []
    if isolated:
        warnings.append(f"{len(isolated)} 个孤立节点（无边连接）")
    if avg_conf < 0.5:
        warnings.append(f"平均置信度 {avg_conf:.2f} 偏低，建议 review_kg 人工确认")

    return QualityReport(
        overall="pass_with_warnings" if warnings else "pass",
        chapter_coverage=1.0,
        isolated_nodes=len(isolated),
        cycles=0,
        avg_confidence=avg_conf,
        warnings=warnings,
        suggestions=["运行 review_kg(mode='quick') 查看低置信度概念"] if warnings else [],
    )


def _to_mermaid(concepts: list[Concept], edges: list[Relation], max_nodes: int = 50) -> str:
    """生成 Mermaid 图。节点过多时截断。"""
    lines = ["graph TD"]
    for c in concepts[:max_nodes]:
        safe_label = c.names[0].replace('"', "'")
        lines.append(f'  {_safe_node_id(c.id)}["{safe_label}"]')
    for e in edges:
        if e.from_id in {c.id for c in concepts[:max_nodes]} and e.to_id in {
            c.id for c in concepts[:max_nodes]
        }:
            lines.append(
                f"  {_safe_node_id(e.from_id)} -->|{e.type}| {_safe_node_id(e.to_id)}"
            )
    return "\n".join(lines)


def _safe_node_id(concept_id: str) -> str:
    """Mermaid 节点 ID 不能含 `:` 和 `.`。"""
    return concept_id.replace(":", "__").replace(".", "_").replace("-", "_")


# --------------------------------------------------------------------------- #
# 切节正文 — 给 concept 模式喂 ConceptEnricher
# --------------------------------------------------------------------------- #


def _split_sections(
    markdown_path: Path, concepts: list[Concept]
) -> dict[str, str]:
    """把 markdown 切成 {concept_id: 该节正文} 字典。

    一个 concept 的正文 = 它对应 heading 行的下一行 → 下一个 concept heading 之前。
    Concept.sources[0].page 存的是 heading 所在的 1-indexed 行号。
    """
    text = markdown_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    by_line: list[tuple[int, str]] = []
    for c in concepts:
        if not c.sources:
            continue
        try:
            ln = int(c.sources[0].page or "0")
        except (TypeError, ValueError):
            continue
        by_line.append((ln, c.id))
    by_line.sort()

    out: dict[str, str] = {}
    for i, (start, cid) in enumerate(by_line):
        end = by_line[i + 1][0] if i + 1 < len(by_line) else len(lines) + 1
        body = "\n".join(lines[start : end - 1]).strip()
        out[cid] = body
    return out


# --------------------------------------------------------------------------- #
# 持久化 — 给所有 builder 共用
# --------------------------------------------------------------------------- #


def _persist_kg(
    *,
    db: RelationalStore,
    kg_id: str,
    subject_slug: str,
    corpus_id: str,
    version: str,
    concepts: list[Concept],
    edges: list[Relation],
    quality: QualityReport,
    manifest: dict,
) -> None:
    """把 concepts + edges 落 knowledge_graphs/concepts/relations 三张表。"""
    with db.session() as s:
        s.add(
            KnowledgeGraphRow(
                kg_id=kg_id,
                subject_id=subject_slug,
                corpus_id=corpus_id,
                version=version,
                node_count=len(concepts),
                edge_count=len(edges),
                quality_json=quality.model_dump(mode="json"),
                manifest_json=manifest,
            )
        )
        s.flush()
        for c in concepts:
            s.add(
                ConceptRow(
                    id=c.id,
                    kg_id=kg_id,
                    name_primary=c.names[0],
                    names_json=c.names,
                    category=c.category,
                    definition=c.definition,
                    informal_description=c.informal_description,
                    abstract_level=c.classification.abstract_level,
                    bloom_level=c.classification.bloom_level,
                    domain=c.classification.domain,
                    cognitive_load_estimate=c.difficulty.cognitive_load_estimate,
                    typical_learning_time_min=c.difficulty.typical_learning_time_min,
                    prereq_count=c.difficulty.prereq_count,
                    prereq_max_depth=c.difficulty.prereq_max_depth,
                    formula_density=c.difficulty.formula_density,
                    coupling=c.difficulty.coupling,
                    confidence=c.confidence,
                    full_json=c.model_dump(mode="json"),
                )
            )
        for e in edges:
            s.add(
                RelationRow(
                    kg_id=kg_id,
                    from_id=e.from_id,
                    to_id=e.to_id,
                    type=e.type,
                    weight=e.weight,
                    explanation=e.explanation,
                    confidence=e.confidence,
                    deprecated=False,
                )
            )
        s.commit()


def build_kg_toc(
    *,
    corpus_id: str,
    subject_slug: str,
    markdown_path: Path,
    db: RelationalStore,
) -> tuple[str, list[Concept], list[Relation], QualityReport, str]:
    """toc 模式：从 markdown 章节生成 KG。

    返回 (kg_id, concepts, edges, quality, mermaid)
    """
    if not markdown_path.exists():
        raise TutorError("CORPUS_NOT_FOUND", hint=str(markdown_path))

    concepts, edges = _build_toc(subject_slug=subject_slug, markdown_path=markdown_path)
    if not concepts:
        raise TutorError(
            "KG_QUALITY_GATE_FAILED",
            hint="markdown 中没有任何 # 标题，无法生成 toc",
        )

    quality = _compute_quality(concepts, edges)
    mermaid = _to_mermaid(concepts, edges)
    kg_id = f"{corpus_id}-kg-toc-v1"

    _persist_kg(
        db=db,
        kg_id=kg_id,
        subject_slug=subject_slug,
        corpus_id=corpus_id,
        version="toc-v1",
        concepts=concepts,
        edges=edges,
        quality=quality,
        manifest={"depth": "toc", "source": str(markdown_path)},
    )

    logger.info(
        "build_kg_toc.done",
        kg_id=kg_id,
        concepts=len(concepts),
        edges=len(edges),
        overall=quality.overall,
    )
    return kg_id, concepts, edges, quality, mermaid
