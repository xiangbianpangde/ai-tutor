"""M-009 教学编排测试：start/respond/next_action/transition + 事件 + REST。

不建真 KG / 不碰真 LLM / 不碰演示资产：注入 FakeEngine（stub 决策），真 SessionStore
负责会话存储（验证新建会话真落库、进 list_sessions）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig
from backend.teaching import TeachingOrchestrator
from shared.schemas import ResponseResult, TeachingAction


class FakeEngine:
    """替身教学引擎：拓扑序固定 + 固定动作/判分，记录调用。"""

    def __init__(self, order=("c1", "c2")):
        self._order = list(order)
        self.calls: list[tuple] = []

    def _topo_order(self, kg_id):
        self.calls.append(("topo", kg_id))
        return list(self._order)

    def next_action(self, session_id):
        self.calls.append(("next_action", session_id))
        return TeachingAction(type="explain", content="讲解 c1", estimated_duration_min=5)

    def respond(self, session_id, answer):
        self.calls.append(("respond", session_id, answer))
        return ResponseResult(correctness="correct", feedback="答得好")

    def advance(self, session_id):
        self.calls.append(("advance", session_id))
        return TeachingAction(type="explain", content="下一步")

    def transition_event(self, session_id, *, event, payload=None):
        self.calls.append(("transition", session_id, event))


@pytest.fixture()
def store(tmp_path):
    from shared.storage import RelationalStore

    s = RelationalStore(f"sqlite:///{tmp_path / 'teach.db'}")
    s.init_schema()
    return s


# ----------------------------- 编排单元 -----------------------------

def test_start_creates_session_and_returns_first_action(store):
    fake = FakeEngine()
    orch = TeachingOrchestrator(store, engine_factory=lambda: fake)
    import asyncio

    res = asyncio.run(orch.start(user_id="u1", subject_id="s1", kg_id="kg-x"))
    assert res["session_id"]
    assert res["kg_id"] == "kg-x"
    assert res["total_concepts"] == 2
    assert res["current_action"]["type"] == "explain"
    # 真落库：session 可被 SessionStore 读回，且首概念 = 拓扑序首位
    from servers.tutoring_mcp.session import SessionStore

    ctx = SessionStore(store).load(res["session_id"])
    assert ctx.current_concept_id == "c1"
    assert ctx.teaching_plan_id == "kg-x"
    assert ctx.status == "active"


def test_start_empty_kg_raises(store):
    from shared.errors import TutorError

    orch = TeachingOrchestrator(store, engine_factory=lambda: FakeEngine(order=()))
    import asyncio

    with pytest.raises(TutorError):
        asyncio.run(orch.start(user_id="u1", subject_id="s1", kg_id="kg-x"))


def test_respond_returns_result(store):
    import asyncio

    fake = FakeEngine()
    orch = TeachingOrchestrator(store, engine_factory=lambda: fake)
    start = asyncio.run(orch.start(user_id="u1", subject_id="s1", kg_id="kg-x"))
    out = asyncio.run(orch.respond(start["session_id"], "我的答案"))
    assert out["result"]["correctness"] == "correct"
    assert ("respond", start["session_id"], "我的答案") in fake.calls


def test_next_action_delegates(store):
    import asyncio

    orch = TeachingOrchestrator(store, engine_factory=lambda: FakeEngine())
    out = asyncio.run(orch.next_action("sess-x"))
    assert out["action"]["type"] == "explain"


def test_transition_delegates(store):
    import asyncio

    fake = FakeEngine()
    orch = TeachingOrchestrator(store, engine_factory=lambda: fake)
    out = asyncio.run(orch.transition("sess-x", event="intro_done"))
    assert out["ok"] is True
    assert ("transition", "sess-x", "intro_done") in fake.calls


def test_start_emits_event(store):
    import asyncio

    seen = []

    class _Bus:
        async def publish(self, event):
            seen.append(event.type)
            return 1

    orch = TeachingOrchestrator(store, engine_factory=lambda: FakeEngine(), events=_Bus())
    asyncio.run(orch.start(user_id="u1", subject_id="s1", kg_id="kg-x"))
    assert "teaching.session_started" in seen


def test_resolve_kg_id_from_subject(store):
    """不传 kg_id 时从 Subject.kg_id 解析。"""
    import asyncio

    from shared.models import Subject

    with store.session() as s:
        s.add(Subject(id="s1", display_name="数学", user_id="u1", kg_id="kg-y"))
        s.commit()
    orch = TeachingOrchestrator(store, engine_factory=lambda: FakeEngine())
    res = asyncio.run(orch.start(user_id="u1", subject_id="s1"))
    assert res["kg_id"] == "kg-y"


def test_missing_subject_raises(store):
    import asyncio

    from shared.errors import TutorError

    orch = TeachingOrchestrator(store, engine_factory=lambda: FakeEngine())
    with pytest.raises(TutorError):
        asyncio.run(orch.start(user_id="u1", subject_id="nope"))


# ----------------------------- REST -----------------------------

@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(_env_file=None, db_path=tmp_path / "t.db")
    app = create_app(cfg)
    app_holder = {}
    with TestClient(app) as c:
        # lifespan 已建库；注入 stub engine 工厂（REST 不碰真 KG/LLM）
        app.state.teaching_engine_factory = lambda: FakeEngine()
        app_holder["app"] = app
        yield c, app


def test_rest_start_and_respond_and_list(client):
    c, app = client
    r = c.post("/api/tutoring/sessions/start",
               json={"user_id": "u1", "subject_id": "s1", "kg_id": "kg-x"})
    assert r.status_code == 200
    data = r.json()["data"]
    sid = data["session_id"]
    assert data["current_action"]["type"] == "explain"

    # 新建会话进 list_sessions（M-004 共享存储）
    lst = c.get("/api/tutoring/sessions", params={"user_id": "u1"}).json()["data"]
    assert any(s["session_id"] == sid for s in lst)

    # respond
    rr = c.post(f"/api/tutoring/sessions/{sid}/respond", json={"answer": "答案"})
    assert rr.status_code == 200
    assert rr.json()["data"]["result"]["correctness"] == "correct"

    # next-action
    na = c.get(f"/api/tutoring/sessions/{sid}/next-action")
    assert na.status_code == 200
    assert na.json()["data"]["action"]["type"] == "explain"

    # transition
    tr = c.post(f"/api/tutoring/sessions/{sid}/transition", json={"event": "intro_done"})
    assert tr.status_code == 200
    assert tr.json()["data"]["ok"] is True
