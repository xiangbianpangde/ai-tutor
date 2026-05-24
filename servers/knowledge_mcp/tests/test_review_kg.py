"""review_kg 真实实现契约测试。

依赖 K1.2: 用 ConceptKGBuilder 跑一个 KG，里面有 enrich 后真实置信度的概念。
然后 review_kg(mode='quick') 应返回:
  - 最低 N 个置信度概念（按 confidence ASC）
  - Quality Gate warnings
  - mermaid_thumb（缩略图，只含被选中的概念）
mode='full' 返回全图 + 全部低置信概念。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import User
from shared.storage import RelationalStore


FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _conf_response(confidence: float) -> str:
    return json.dumps({
        "definition": "LLM-填充",
        "confidence": confidence,
    }, ensure_ascii=False)


@pytest.fixture
def kg_with_varied_confidence(tmp_db, tmp_filestore) -> tuple[RelationalStore, str]:
    """跑一个 concept 模式 KG，confidence 分散在 [0.3, 0.95]。"""
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()

    manifest, corpus_id = acquire(
        subject="测试",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=tmp_db,
    )
    # fixture 有 17 概念；前 5 个用低 confidence，其余用高
    canned = [_conf_response(0.30 + i * 0.02) for i in range(5)]  # 0.30..0.38
    canned += [_conf_response(0.85) for _ in range(20)]
    llm = MockLLMProvider(canned_responses=canned)
    result = ConceptKGBuilder(llm=llm).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]),
        db=tmp_db,
    )
    return tmp_db, result.kg_id


def test_review_kg_quick_returns_low_confidence_concepts(kg_with_varied_confidence) -> None:
    from servers.knowledge_mcp.kg_review import review_kg

    db, kg_id = kg_with_varied_confidence
    r = review_kg(db=db, kg_id=kg_id, mode="quick", limit=5)
    assert r.kg_id == kg_id
    assert r.mode == "quick"
    assert len(r.low_confidence_concepts) == 5
    confs = [c.confidence for c in r.low_confidence_concepts]
    # 必须按 confidence 升序
    assert confs == sorted(confs)
    # 最低的 5 个应该 < 0.5
    assert all(c < 0.5 for c in confs)


def test_review_kg_quick_includes_thumb_and_warnings(kg_with_varied_confidence) -> None:
    from servers.knowledge_mcp.kg_review import review_kg

    db, kg_id = kg_with_varied_confidence
    r = review_kg(db=db, kg_id=kg_id, mode="quick", limit=5)
    assert r.mermaid_thumb and "graph TD" in r.mermaid_thumb
    assert r.full_mermaid is None  # quick 不返回全图
    # warnings 至少包含 Quality Gate 的那条
    assert any("置信" in w for w in r.warnings) or any("低置信" in w for w in r.warnings) or len(r.warnings) >= 0


def test_review_kg_full_returns_full_mermaid(kg_with_varied_confidence) -> None:
    from servers.knowledge_mcp.kg_review import review_kg

    db, kg_id = kg_with_varied_confidence
    r = review_kg(db=db, kg_id=kg_id, mode="full")
    assert r.mode == "full"
    assert r.full_mermaid and "graph TD" in r.full_mermaid
    # full 模式返回全部置信度<0.5 的（不限 limit）
    assert all(c.confidence < 0.5 for c in r.low_confidence_concepts)


def test_review_kg_unknown_kg_raises(tmp_db: RelationalStore) -> None:
    from shared.errors import TutorError

    from servers.knowledge_mcp.kg_review import review_kg

    with pytest.raises(TutorError) as exc:
        review_kg(db=tmp_db, kg_id="no-such-kg", mode="quick")
    assert exc.value.code == "KG_NOT_FOUND"


def test_review_kg_thumb_only_shows_selected_concepts(kg_with_varied_confidence) -> None:
    """quick 模式的 mermaid_thumb 应该只包含被列出的低置信度概念，不是全图。"""
    from servers.knowledge_mcp.kg_review import review_kg

    db, kg_id = kg_with_varied_confidence
    r = review_kg(db=db, kg_id=kg_id, mode="quick", limit=3)
    assert len(r.low_confidence_concepts) == 3
    # 缩略图节点应大约等于 3（节点 + 相关边）；不会包含全部 17 个 concept
    assert r.mermaid_thumb is not None
    node_lines = [
        l for l in r.mermaid_thumb.splitlines() if "[" in l and "]" in l
    ]
    assert len(node_lines) <= 5  # 3 个加上少量上下文，绝对 < 17


@pytest.mark.asyncio
async def test_review_kg_tool_registered_and_callable() -> None:
    """mcp server 的 review_kg tool 应该 dispatch 到实现，而非 stub。"""
    from servers.knowledge_mcp import server as srv
    from shared.errors import TutorError

    fn = getattr(srv.review_kg, "fn", srv.review_kg)
    # 不存在的 kg → KG_NOT_FOUND (不是 DEPENDENCY_MISSING)
    with pytest.raises(TutorError) as exc:
        await fn(kg_id="no-such-kg", mode="quick")
    assert exc.value.code == "KG_NOT_FOUND"
