"""M-015 打包调度测试 + M-001 收尾聚合健康。

不真编译/不真 shell out：runner 注入；verifier 用 tmp 假产物目录。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.build import (
    ArtifactVerifier,
    BuildConfig,
    BuildOrchestrator,
    NuitkaBuilder,
    UPXCompressor,
)
from backend.config import AppConfig

# ----------------------------- NuitkaBuilder -----------------------------

def test_nuitka_args_are_onedir_not_onefile():
    """硬红线：必须 --standalone（onedir），绝不 --onefile（R-01）。"""
    args = NuitkaBuilder().build_args()
    assert "--standalone" in args
    assert "--onefile" not in args
    assert any(a.startswith("--output-filename=") for a in args)


def test_nuitka_includes_data_and_excludes_tests():
    args = NuitkaBuilder().build_args()
    assert any("--include-data-dir=data=data" in a for a in args)
    assert any("--nofollow-import-to=pytest" in a for a in args)


def test_nuitka_build_runs_runner():
    builder = NuitkaBuilder()
    res = builder.build(lambda cmd: (0, "Nuitka build done"))
    assert res["ok"] is True
    assert res["command"][:3] == ["python", "-m", "nuitka"]


# ----------------------------- UPX 软降级 -----------------------------

def test_upx_missing_tool_is_soft(tmp_path):
    """UPX 不存在 → 不抛，返回 warning（软约束）。"""
    (tmp_path / "lib.so").write_bytes(b"x" * 2_000_000)
    # 注入失败 runner 模拟"工具在但压缩失败"
    comp = UPXCompressor(runner=lambda cmd: (1, "upx failed"))
    res = comp.compress_dir(tmp_path)
    assert res["compressed"] == 0
    assert res["warnings"]  # 软降级警告，不抛


def test_upx_compresses_large_files(tmp_path):
    (tmp_path / "big.pyd").write_bytes(b"x" * 2_000_000)
    (tmp_path / "small.so").write_bytes(b"x" * 100)  # 太小跳过
    comp = UPXCompressor(runner=lambda cmd: (0, "ok"))
    res = comp.compress_dir(tmp_path)
    assert res["compressed"] == 1
    assert res["skipped"] == 1


# ----------------------------- ArtifactVerifier -----------------------------

def test_verifier_missing_exe_hard_fail(tmp_path):
    (tmp_path / "junk.txt").write_text("x")
    res = ArtifactVerifier().verify(tmp_path, exe_name="ai-tutor-backend")
    assert res["ok"] is False
    assert res["errors"]


def test_verifier_passes_with_exe(tmp_path):
    (tmp_path / "ai-tutor-backend.exe").write_bytes(b"x" * 1000)
    res = ArtifactVerifier().verify(tmp_path, exe_name="ai-tutor-backend")
    assert res["ok"] is True
    assert res["exe_found"] is True


def test_verifier_size_over_limit_is_soft_warn(tmp_path):
    (tmp_path / "ai-tutor-backend.bin").write_bytes(b"x" * 2_000_000)
    res = ArtifactVerifier(max_size_mb=1).verify(tmp_path, exe_name="ai-tutor-backend")
    assert res["ok"] is True  # 体积软约束，不硬失败
    assert res["warnings"]


# ----------------------------- BuildOrchestrator FSM -----------------------------

def test_orchestrator_full_success(tmp_path):
    # 准备假产物目录
    dist = tmp_path / "main.dist"
    dist.mkdir()
    (dist / "ai-tutor-backend.exe").write_bytes(b"x" * 1000)

    cfg = BuildConfig(nuitka=NuitkaBuilder(), enable_upx=True, max_size_mb=500)
    orch = BuildOrchestrator(cfg, runner=lambda cmd: (0, "ok"))
    res = orch.run(dist_dir=str(dist))
    assert res["ok"] is True
    assert res["state"] == "DONE"
    states = [s["state"] for s in res["steps"]]
    assert states == ["NUITKA", "UPX", "VERIFY"]


def test_orchestrator_nuitka_failure_hard_stops(tmp_path):
    orch = BuildOrchestrator(runner=lambda cmd: (1, "compile error"))
    res = orch.run(dist_dir=str(tmp_path))
    assert res["ok"] is False
    assert res["state"] == "FAILED"
    assert len(res["steps"]) == 1  # 编译失败即停，不进 UPX/VERIFY


def test_orchestrator_verify_failure_hard(tmp_path):
    dist = tmp_path / "main.dist"
    dist.mkdir()  # 空目录，无 exe → 校验硬失败
    orch = BuildOrchestrator(BuildConfig(enable_upx=False), runner=lambda cmd: (0, "ok"))
    res = orch.run(dist_dir=str(dist))
    assert res["ok"] is False
    assert res["state"] == "FAILED"


# ----------------------------- REST（M-001 收尾 + M-015）-----------------------------

@pytest.fixture()
def client(tmp_path):
    cfg = AppConfig(_env_file=None, db_path=tmp_path / "t.db")
    app = create_app(cfg)
    with TestClient(app) as c:
        yield c, app


def test_rest_system_health(client):
    c, app = client
    r = c.get("/api/meta/health")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["ok"] is True  # 测试环境 DB 就绪 → 全子系统 up
    assert data["subsystems"]["db"] is True
    assert set(data["subsystems"]) == {"db", "cache", "sessions", "tasks", "events"}


def test_rest_build_with_injected_runner(client):
    c, app = client
    app.state.build_runner = lambda cmd: (1, "no nuitka here")  # 不真编译
    r = c.post("/api/meta/build", json={})
    assert r.status_code == 200
    # 编译失败（无 nuitka）→ 优雅返回 FAILED，不 500
    assert r.json()["data"]["state"] == "FAILED"
