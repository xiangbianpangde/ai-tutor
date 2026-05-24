"""simulation generator 契约测试 — 自包含 HTML 交互闪卡。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.errors import TutorError
from shared.llm_client import MockLLMProvider
from shared.models import Corpus, KnowledgeGraphRow, User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enriched(name: str) -> str:
    return json.dumps({
        "definition": f"{name}：精确定义",
        "informal_description": f"通俗解释{name}",
        "examples": [{"text": f"例子{name}", "type": "computation"}],
        "confidence": 0.85,
    }, ensure_ascii=False)


@pytest.fixture
def kg_with_content(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ce-shi", version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn", file_store=tmp_filestore, db=tmp_db,
    )
    canned = [_enriched(f"c{i}") for i in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id, subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]), db=tmp_db,
    )
    return tmp_db, r.kg_id


def test_simulation_writes_html(kg_with_content, tmp_path: Path) -> None:
    from servers.digest_mcp.simulation import generate_simulation

    db, kg_id = kg_with_content
    art = generate_simulation(db=db, kg_id=kg_id, out_dir=tmp_path)
    assert art.mime_type == "text/html"
    text = Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "交互闪卡" in text


def test_simulation_embeds_concept_cards(kg_with_content, tmp_path: Path) -> None:
    """HTML 中应内嵌 CARDS JSON，包含概念名与定义。"""
    from servers.digest_mcp.simulation import generate_simulation

    db, kg_id = kg_with_content
    art = generate_simulation(db=db, kg_id=kg_id, out_dir=tmp_path)
    text = Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "const CARDS =" in text
    assert "精确定义" in text


def test_simulation_self_contained_no_cdn(kg_with_content, tmp_path: Path) -> None:
    """离线可用：不引用任何外部 http(s) 资源。"""
    from servers.digest_mcp.simulation import generate_simulation

    db, kg_id = kg_with_content
    art = generate_simulation(db=db, kg_id=kg_id, out_dir=tmp_path)
    text = Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "http://" not in text
    assert "https://" not in text
    assert "src=" not in text  # 无外部脚本/图片引用


def test_simulation_unknown_kg_raises(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from servers.digest_mcp.simulation import generate_simulation

    with pytest.raises(TutorError) as exc:
        generate_simulation(db=tmp_db, kg_id="no-such", out_dir=tmp_path)
    assert exc.value.code == "KG_NOT_FOUND"


def test_simulation_empty_kg_still_writes(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from servers.digest_mcp.simulation import generate_simulation

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Corpus(id="c1", subject_id="x", user_id="yhn", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id="empty-kg", subject_id="x", corpus_id="c1",
            version="v1", node_count=0, edge_count=0, manifest_json={},
        ))
        s.commit()
    art = generate_simulation(db=tmp_db, kg_id="empty-kg", out_dir=tmp_path)
    text = Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "暂无概念" in text


def test_simulation_escapes_html_in_names(tmp_db: RelationalStore, tmp_path: Path) -> None:
    """概念名/定义里的特殊字符通过 JSON 转义嵌入，不破坏 HTML 结构。"""
    from servers.digest_mcp.simulation import generate_simulation
    from shared.models import ConceptRow

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Corpus(id="c2", subject_id="x", user_id="yhn", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id="kg2", subject_id="x", corpus_id="c2",
            version="v1", node_count=1, edge_count=0, manifest_json={},
        ))
        s.add(ConceptRow(
            id="x:1:a", kg_id="kg2", base_id="x:1:a",
            name_primary="<script>alert(1)</script>", names_json=["a"],
            category="definition", definition="含 </script> 的定义",
            informal_description="", abstract_level=0.5, bloom_level="understand",
            domain="x", cognitive_load_estimate=0.3, typical_learning_time_min=10,
            prereq_count=0, prereq_max_depth=0, formula_density=0,
            coupling=0, confidence=0.9, full_json={},
        ))
        s.commit()
    art = generate_simulation(db=tmp_db, kg_id="kg2", out_dir=tmp_path)
    text = Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8")
    # JSON 转义后 </script> 不应原样出现在 CARDS 里破坏脚本块
    assert "</script>\",\"" not in text.replace(" ", "")
