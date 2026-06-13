"""quiz generator 契约测试。

从 KG 概念出题:
- 填空题: 把 definition 里挖掉 concept.name_primary（让学生填名词）
- 多选题: 取 4 个相邻 concept，1 个正确 + 3 个干扰

输出: 一份 quiz.html（套模板）+ 一份 quiz-data.json（题目结构）
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.llm_client import MockLLMProvider
from shared.models import User
from shared.storage import RelationalStore

FIXTURE = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "mini_subject.md"


def _enriched(name: str) -> str:
    return json.dumps({
        "definition": f"{name} 是一个用于描述某种结构的核心概念。",
        "confidence": 0.85,
    }, ensure_ascii=False)


@pytest.fixture
def kg_ready(tmp_db: RelationalStore, tmp_filestore):
    from servers.knowledge_mcp.acquisition_adapter import AcquireSource, acquire
    from servers.knowledge_mcp.kg_builder import ConceptKGBuilder

    with tmp_db.session() as s:
        s.add(User(id="yhn"))
        s.commit()
    manifest, corpus_id = acquire(
        subject="ce-shi",
        version="v1",
        sources=[AcquireSource(type="file", uri=str(FIXTURE))],
        user_id="yhn",
        file_store=tmp_filestore,
        db=tmp_db,
    )
    canned = [_enriched(f"c{i}") for i in range(50)]
    r = ConceptKGBuilder(llm=MockLLMProvider(canned_responses=canned)).build(
        corpus_id=corpus_id,
        subject_slug="ce-shi",
        markdown_path=Path(manifest.file_paths["markdown"]),
        db=tmp_db,
    )
    return tmp_db, r.kg_id


def test_quiz_writes_html_and_json(kg_ready, tmp_path: Path) -> None:
    from servers.digest_mcp.quiz import generate_quiz

    db, kg_id = kg_ready
    artifacts = generate_quiz(db=db, kg_id=kg_id, out_dir=tmp_path, count=5)
    # 期望返回两个 artifact: html + json
    assert len(artifacts) == 2
    mimes = {a.mime_type for a in artifacts}
    assert "text/html" in mimes
    assert "application/json" in mimes


def test_quiz_json_has_correct_structure(kg_ready, tmp_path: Path) -> None:
    from servers.digest_mcp.quiz import generate_quiz

    db, kg_id = kg_ready
    artifacts = generate_quiz(db=db, kg_id=kg_id, out_dir=tmp_path, count=5)
    json_artifact = next(a for a in artifacts if a.mime_type == "application/json")
    data = json.loads(Path(json_artifact.uri.replace("file:///", "")).read_text(encoding="utf-8"))
    assert "questions" in data
    assert len(data["questions"]) <= 5
    for q in data["questions"]:
        assert "id" in q
        assert "type" in q  # "fill_blank" | "multiple_choice"
        assert "prompt" in q
        assert "answer" in q


def test_quiz_includes_multiple_choice_with_4_options(kg_ready, tmp_path: Path) -> None:
    from servers.digest_mcp.quiz import generate_quiz

    db, kg_id = kg_ready
    artifacts = generate_quiz(db=db, kg_id=kg_id, out_dir=tmp_path, count=10)
    json_artifact = next(a for a in artifacts if a.mime_type == "application/json")
    data = json.loads(Path(json_artifact.uri.replace("file:///", "")).read_text(encoding="utf-8"))
    mc_qs = [q for q in data["questions"] if q["type"] == "multiple_choice"]
    assert mc_qs, "应该至少有 1 道多选题"
    for q in mc_qs:
        assert len(q["options"]) == 4
        assert q["answer"] in q["options"]


def test_quiz_html_contains_questions(kg_ready, tmp_path: Path) -> None:
    """HTML 应该包含题目文本，可在浏览器看到。"""
    from servers.digest_mcp.quiz import generate_quiz

    db, kg_id = kg_ready
    artifacts = generate_quiz(db=db, kg_id=kg_id, out_dir=tmp_path, count=3)
    html_artifact = next(a for a in artifacts if a.mime_type == "text/html")
    html = Path(html_artifact.uri.replace("file:///", "")).read_text(encoding="utf-8")
    assert "<html" in html.lower()
    assert "<form" in html or "<button" in html or "<input" in html
    # 至少包含 KG 中某个概念名
    json_artifact = next(a for a in artifacts if a.mime_type == "application/json")
    data = json.loads(Path(json_artifact.uri.replace("file:///", "")).read_text(encoding="utf-8"))
    first_prompt = data["questions"][0]["prompt"]
    # 题目里某些片段应出现在 html 中
    assert any(snippet in html for snippet in [first_prompt[:10], first_prompt[10:30] if len(first_prompt) > 30 else first_prompt])


def test_quiz_count_caps_at_concept_count(kg_ready, tmp_path: Path) -> None:
    """count 超出 concept 数 → 输出 = min(count, concept_count)。"""
    from servers.digest_mcp.quiz import generate_quiz

    db, kg_id = kg_ready
    artifacts = generate_quiz(db=db, kg_id=kg_id, out_dir=tmp_path, count=10000)
    json_artifact = next(a for a in artifacts if a.mime_type == "application/json")
    data = json.loads(Path(json_artifact.uri.replace("file:///", "")).read_text(encoding="utf-8"))
    # fixture 有 17 概念，所以 questions <= 17
    assert len(data["questions"]) <= 17


def test_quiz_seed_makes_reproducible(kg_ready, tmp_path: Path) -> None:
    """同 seed 两次跑应得相同题目。"""
    from servers.digest_mcp.quiz import generate_quiz

    db, kg_id = kg_ready
    a1 = generate_quiz(db=db, kg_id=kg_id, out_dir=tmp_path / "r1", count=5, seed=42)
    a2 = generate_quiz(db=db, kg_id=kg_id, out_dir=tmp_path / "r2", count=5, seed=42)
    j1 = json.loads(Path(next(a for a in a1 if a.mime_type == "application/json").uri.replace("file:///", "")).read_text(encoding="utf-8"))
    j2 = json.loads(Path(next(a for a in a2 if a.mime_type == "application/json").uri.replace("file:///", "")).read_text(encoding="utf-8"))
    # 题目顺序和内容应相同
    p1 = [(q["type"], q["prompt"]) for q in j1["questions"]]
    p2 = [(q["type"], q["prompt"]) for q in j2["questions"]]
    assert p1 == p2


def test_quiz_unknown_kg_raises(tmp_db: RelationalStore, tmp_path: Path) -> None:
    from servers.digest_mcp.quiz import generate_quiz
    from shared.errors import TutorError

    with pytest.raises(TutorError) as exc:
        generate_quiz(db=tmp_db, kg_id="no-such", out_dir=tmp_path, count=5)
    assert exc.value.code == "KG_NOT_FOUND"
