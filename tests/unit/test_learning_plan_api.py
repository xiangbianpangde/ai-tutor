"""学习计划端点契约测试（GET learning-plan：惰性建计划 + 实时进度）。

临时库隔离。验证：惰性构建与持久化、进度实时叠加（BKT）、
所属权校验、未知科目 404。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig

USER = "plan-user"
SUBJECT = "ml-basics"
KG = "ml-basics-kg-toc-v1"


@pytest.fixture
def client(tmp_path):
    config = AppConfig(db_path=tmp_path / "tutor.db")
    app = create_app(config=config)
    with TestClient(app) as c:
        yield c, app


def _seed_subject_and_kg(client: TestClient) -> None:
    from shared.models import ConceptRow, KnowledgeGraphRow, Subject, User

    store = client.app.state.store
    with store.session() as s:
        s.add(User(id=USER, display_name=USER))
        import datetime
        s.add(KnowledgeGraphRow(
            kg_id=KG, subject_id=SUBJECT, corpus_id="corpus-ml", version="toc-v1",
            node_count=3, edge_count=0, manifest_json={"completed": True},
            created_at=datetime.datetime.utcnow(),
        ))
        s.add(Subject(id=SUBJECT, user_id=USER, display_name="机器学习基础", kg_id=KG))
        slug = {"机器学习基础": "ml-basics", "线性回归": "linear_regression",
                "逻辑回归": "logistic_regression"}
        for cid, name, kind in (
            (f"{SUBJECT}:1:ml_basics", "机器学习基础", "definition"),
            (f"{SUBJECT}:1.1:linear_regression", "线性回归", "method"),
            (f"{SUBJECT}:1.2:logistic_regression", "逻辑回归", "method"),
        ):
            s.add(ConceptRow(
                id=cid, kg_id=KG, base_id=cid, name_primary=name,
                names_json=[name], category=kind,
                definition=f"{name} 的定义", informal_description="",
                abstract_level=0.3, bloom_level="remember", domain="ml",
                cognitive_load_estimate=0.3, typical_learning_time_min=15,
                prereq_count=0, prereq_max_depth=0,
                formula_density=0.0, coupling=0.0,
                confidence=0.9, created_at=__import__('datetime').datetime.utcnow(),
                full_json={
                    "id": cid, "names": [name], "category": kind,
                    "definition": f"{name} 的定义", "informal_description": "",
                    "attributes": {},
                    "classification": {
                        "bloom_level": "remember", "abstract_level": 0.3,
                        "domain": "ml", "cross_domain_tags": [],
                    },
                    "difficulty": {
                        "prereq_count": 0, "prereq_max_depth": 0,
                        "formula_density": 0.3, "coupling": 0.3,
                        "cognitive_load_estimate": 0.4,
                        "typical_learning_time_min": 15,
                    },
                    "examples": [], "counter_examples": [],
                    "common_misconceptions": [], "keywords": [],
                    "embedding": None, "sources": [], "confidence": 0.9,
                },
            ))
        s.commit()


def test_learning_plan_builds_and_persists(client) -> None:
    http, app = client
    _seed_subject_and_kg(http)
    resp = http.get(f"/api/tutoring/users/{USER}/subjects/{SUBJECT}/learning-plan")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan"]["total_concepts"] == 3
    assert data["plan"]["phases"][0]["title"] == "机器学习基础"
    assert data["progress"]["concepts_total"] == 3
    assert data["progress"]["overall_mastery_ratio"] == 0.0
    assert data["progress"]["phases"][0]["status"] == "in_progress"
    # 已持久化：再查不重建（kg_id 不变）
    from shared.models import LearningPlanRow
    with app.state.store.session() as s:
        assert s.get(LearningPlanRow, (USER, SUBJECT)) is not None


def test_learning_plan_reflects_bkt_mastery(client) -> None:
    from shared.models import BKTParamRow

    http, app = client
    _seed_subject_and_kg(http)
    with app.state.store.session() as s:
        s.add(BKTParamRow(
            user_id=USER, concept_id=f"{SUBJECT}:1:ml_basics",
            p_learn=0.15, p_guess=0.12, p_slip=0.08, p_init=0.05,
            p_mastery=0.85, n_observations=3,
        ))
        s.commit()
    resp = http.get(f"/api/tutoring/users/{USER}/subjects/{SUBJECT}/learning-plan")
    progress = resp.json()["data"]["progress"]
    assert progress["concepts_mastered"] == 1
    assert progress["overall_mastery_ratio"] == pytest.approx(0.333, abs=0.01)
    assert progress["next_concept_name"] == "线性回归"


def test_learning_plan_rejects_unknown_or_foreign_subject(client) -> None:
    http, _app = client
    _seed_subject_and_kg(http)
    unknown = http.get(f"/api/tutoring/users/{USER}/subjects/no-such/learning-plan")
    assert unknown.status_code == 404
    foreign = http.get(f"/api/tutoring/users/other-user/subjects/{SUBJECT}/learning-plan")
    assert foreign.status_code == 404
