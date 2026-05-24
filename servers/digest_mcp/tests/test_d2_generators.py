"""D2 新 generator 契约测试：multi_agent / slides / audio。

simulation 单独在 test_simulation.py。这里共用一个 kg fixture。
"""
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
        "informal_description": f"通俗{name}",
        "examples": [{"text": f"例子{name}", "type": "computation"}],
        "common_misconceptions": [f"误解{name}"],
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


def _empty_kg(tmp_db: RelationalStore, kg_id="empty-kg") -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.add(Corpus(id=f"c-{kg_id}", subject_id="x", user_id="yhn", manifest_json={}))
        s.add(KnowledgeGraphRow(
            kg_id=kg_id, subject_id="x", corpus_id=f"c-{kg_id}",
            version="v1", node_count=0, edge_count=0, manifest_json={},
        ))
        s.commit()
    return tmp_db


# ---------------- multi_agent ---------------- #


def test_multi_agent_template_mode_no_llm(kg_with_content, tmp_path: Path) -> None:
    from servers.digest_mcp.multi_agent import generate_multi_agent

    db, kg_id = kg_with_content
    art = generate_multi_agent(db=db, kg_id=kg_id, out_dir=tmp_path, llm=None)
    assert art.mime_type == "application/json"
    doc = json.loads(Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8"))
    assert doc["generator"] == "template"
    assert doc["scenes"]
    roles = {t["role"] for sc in doc["scenes"] for t in sc["dialogue"]}
    assert "teacher" in roles
    # 模板里有 misconception → 应出现 skeptic
    assert "skeptic" in roles or "student" in roles


def test_multi_agent_llm_mode(kg_with_content, tmp_path: Path) -> None:
    from servers.digest_mcp.multi_agent import generate_multi_agent

    db, kg_id = kg_with_content
    dialogue = json.dumps([
        {"role": "teacher", "content": "讲解内容"},
        {"role": "student", "content": "学生提问"},
        {"role": "skeptic", "content": "抬杠"},
    ], ensure_ascii=False)
    llm = MockLLMProvider(canned_responses=[dialogue] * 60)
    art = generate_multi_agent(db=db, kg_id=kg_id, out_dir=tmp_path, llm=llm)
    doc = json.loads(Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8"))
    assert doc["generator"] == "llm"
    assert doc["scenes"][0]["dialogue"][0]["content"] == "讲解内容"


def test_multi_agent_llm_garbage_falls_back_to_template(kg_with_content, tmp_path: Path) -> None:
    """LLM 返回非法 JSON → 该 scene 回退模板，不崩。"""
    from servers.digest_mcp.multi_agent import generate_multi_agent

    db, kg_id = kg_with_content
    llm = MockLLMProvider(canned_responses=["这不是JSON"] * 60)
    art = generate_multi_agent(db=db, kg_id=kg_id, out_dir=tmp_path, llm=llm)
    doc = json.loads(Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8"))
    # 每个 scene 仍有对话（模板兜底）
    assert all(sc["dialogue"] for sc in doc["scenes"])


def test_multi_agent_unknown_kg_raises(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from servers.digest_mcp.multi_agent import generate_multi_agent

    with pytest.raises(TutorError) as exc:
        generate_multi_agent(db=tmp_db, kg_id="no-such", out_dir=tmp_path)
    assert exc.value.code == "KG_NOT_FOUND"


# ---------------- slides ---------------- #


def test_slides_writes_artifact(kg_with_content, tmp_path: Path) -> None:
    from servers.digest_mcp.slides import generate_slides

    db, kg_id = kg_with_content
    art = generate_slides(db=db, kg_id=kg_id, out_dir=tmp_path)
    # 没装 pptx → HTML；装了 → pptx。两者都可接受
    assert art.mime_type in (
        "text/html",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    assert Path(art.uri.replace("file:///", "")).exists()


def test_slides_html_self_contained(kg_with_content, tmp_path: Path) -> None:
    """无 pptx 时 HTML 幻灯应自包含（无 CDN）。"""
    from servers.digest_mcp import slides as slides_mod

    db, kg_id = kg_with_content
    # 强制走 HTML 分支
    orig = slides_mod._HAS_PPTX
    slides_mod._HAS_PPTX = False
    try:
        art = slides_mod.generate_slides(db=db, kg_id=kg_id, out_dir=tmp_path)
    finally:
        slides_mod._HAS_PPTX = orig
    assert art.mime_type == "text/html"
    text = Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "const SLIDES =" in text
    assert "https://" not in text and "http://" not in text


def test_slides_unknown_kg_raises(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from servers.digest_mcp.slides import generate_slides

    with pytest.raises(TutorError) as exc:
        generate_slides(db=tmp_db, kg_id="no-such", out_dir=tmp_path)
    assert exc.value.code == "KG_NOT_FOUND"


# ---------------- audio ---------------- #


def test_audio_writes_script_md(kg_with_content, tmp_path: Path) -> None:
    """无 edge-tts（或 synthesize=False）→ 输出讲稿 markdown。"""
    from servers.digest_mcp.audio import generate_audio

    db, kg_id = kg_with_content
    art = generate_audio(db=db, kg_id=kg_id, out_dir=tmp_path, synthesize=False)
    assert art.mime_type == "text/markdown"
    text = Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "音频讲稿" in text
    assert "[停顿]" in text


def test_audio_script_contains_concepts(kg_with_content, tmp_path: Path) -> None:
    from servers.digest_mcp.audio import generate_audio

    db, kg_id = kg_with_content
    art = generate_audio(db=db, kg_id=kg_id, out_dir=tmp_path, synthesize=False)
    text = Path(art.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "精确定义" in text
    assert "举个例子" in text


def test_audio_unknown_kg_raises(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from servers.digest_mcp.audio import generate_audio

    with pytest.raises(TutorError) as exc:
        generate_audio(db=tmp_db, kg_id="no-such", out_dir=tmp_path)
    assert exc.value.code == "KG_NOT_FOUND"


def test_audio_empty_kg_still_writes_script(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from servers.digest_mcp.audio import generate_audio

    db = _empty_kg(tmp_db)
    art = generate_audio(db=db, kg_id="empty-kg", out_dir=tmp_path, synthesize=False)
    assert art.mime_type == "text/markdown"
    assert Path(art.uri.replace("file:///", "")).exists()
