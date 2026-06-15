"""M-016 红线编排测试：聚合 / fail_fast / pass_on_zero + REST（注入假 runner）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import AppConfig
from backend.redline import RedlineOrchestrator, RedlineTool


def _runner(table):
    """假执行器：按命令首词查表返回 (code, output)。"""
    def run(command):
        return table.get(command[0], (0, "ok"))
    return run


def test_all_pass():
    tools = [RedlineTool("ruff", ("ruff", "check")), RedlineTool("imports", ("lint-imports",))]
    orch = RedlineOrchestrator(tools=tools, runner=_runner({}))
    out = orch.run()
    assert out["passed"] is True
    assert out["failed"] == []
    assert out["ran"] == 2


def test_one_fails():
    tools = [RedlineTool("ruff", ("ruff",)), RedlineTool("imports", ("lint-imports",))]
    orch = RedlineOrchestrator(tools=tools, runner=_runner({"ruff": (1, "E501 found")}))
    out = orch.run()
    assert out["passed"] is False
    assert "ruff" in out["failed"]


def test_fail_fast_stops():
    tools = [RedlineTool("a", ("a",)), RedlineTool("b", ("b",)), RedlineTool("c", ("c",))]
    orch = RedlineOrchestrator(tools=tools, runner=_runner({"a": (1, "boom")}))
    out = orch.run(fail_fast=True)
    assert out["ran"] == 1  # 首个失败即停
    assert out["total"] == 3


def test_summary_is_last_line():
    tools = [RedlineTool("ruff", ("ruff",))]
    orch = RedlineOrchestrator(tools=tools, runner=_runner({"ruff": (0, "line1\nAll checks passed!")}))
    out = orch.run()
    assert out["results"][0]["summary"] == "All checks passed!"


def test_pass_on_nonzero_tool():
    """个别工具非零表达'有发现'——pass_on_zero=False 反转判定。"""
    tools = [RedlineTool("grep_clean", ("grep",), pass_on_zero=False)]
    orch = RedlineOrchestrator(tools=tools, runner=_runner({"grep": (1, "no match")}))
    out = orch.run()
    assert out["passed"] is True  # exit 1 (无匹配) = 干净


def test_default_tools_shape():
    orch = RedlineOrchestrator()
    names = [t.name for t in orch.tools]
    assert "ruff" in names and "import-linter" in names


# ----------------------------- REST -----------------------------

@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(_env_file=None, db_path=tmp_path / "t.db")
    app = create_app(cfg)
    with TestClient(app) as c:
        # 注入假 runner——REST 不真 shell out
        app.state.redline_runner = lambda command: (0, "All checks passed!")
        yield c


def test_rest_redline(client):
    r = client.post("/api/meta/redline", json={"fail_fast": False})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["passed"] is True
    assert data["ran"] >= 1
