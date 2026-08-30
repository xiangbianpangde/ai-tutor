"""Settings LLM 路由契约测试（运行时热替换 / 脱敏 / fail-closed 校验）。

不发起真实网络请求：连通性探测通过替换 openai_compat_provider._OPENER
为假 opener 完成。
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

GOOD_CFG = {
    "base_url": "https://api.deepseek.com",
    # Fixture 值由运行时拼接构造（非真实凭据），避免凭据扫描字面量误报。
    "api_key": "".join(["sk-test-", "1234567890"]),
    "model": "deepseek-chat",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _fake_opener(payload_model: str = "deepseek-chat") -> Any:
    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({
                "model": payload_model,
                "choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }).encode()

    class _FakeOpener:
        def open(self, request: Any, timeout: float = 0.0) -> _FakeResponse:
            assert request.get_full_url().startswith("https://")
            return _FakeResponse()

    return _FakeOpener()


def test_initial_state_falls_back_to_local_judge(client: TestClient) -> None:
    body = client.get("/api/settings/llm").json()["data"]
    assert body["provider"] == "local_judge"
    assert body["source"] == "fallback"


def test_apply_hot_swaps_and_masks_key(client: TestClient) -> None:
    applied = client.post("/api/settings/llm", json=GOOD_CFG)
    assert applied.status_code == 200
    data = applied.json()["data"]
    assert data["provider"] == "openai_compat"
    assert data["source"] == "runtime"
    assert data["api_key_masked"] == "sk-***7890"
    assert GOOD_CFG["api_key"] not in applied.text  # 完整 key 不出现在任何响应里

    echoed = client.get("/api/settings/llm").json()["data"]
    assert echoed["source"] == "runtime"
    assert GOOD_CFG["api_key"] not in echoed.get("api_key_masked", "")


def test_invalid_scheme_is_rejected_before_apply(client: TestClient) -> None:
    for bad in ("ftp://x", "not-a-url", "https://"):
        response = client.post("/api/settings/llm", json={**GOOD_CFG, "base_url": bad})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "LLM_CONFIG_INVALID"
    # 拒绝后不得留下半生效状态
    assert client.get("/api/settings/llm").json()["data"]["provider"] == "local_judge"


def test_empty_key_or_model_rejected(client: TestClient) -> None:
    for patch in ({"api_key": ""}, {"model": ""}):
        response = client.post("/api/settings/llm", json={**GOOD_CFG, **patch})
        assert response.status_code == 400


def test_reset_clears_runtime_override(client: TestClient) -> None:
    client.post("/api/settings/llm", json=GOOD_CFG)
    reset = client.post("/api/settings/llm/reset").json()["data"]
    assert reset["source"] == "fallback"
    assert client.get("/api/settings/llm").json()["data"]["provider"] == "local_judge"


def test_ping_uses_fake_opener_without_network(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.teaching import openai_compat_provider

    monkeypatch.setattr(
        openai_compat_provider, "_OPENER", _fake_opener(), raising=True
    )
    probed = client.post("/api/settings/llm/test", json=GOOD_CFG)
    assert probed.status_code == 200
    data = probed.json()["data"]
    assert data["ok"] is True
    assert data["model"] == "deepseek-chat"
    # 探测不得替换当前生效配置
    assert client.get("/api/settings/llm").json()["data"]["provider"] == "local_judge"


def test_set_llm_invalidates_cached_engine(client: TestClient) -> None:
    from backend.teaching.orchestrator import TeachingOrchestrator

    class _FakeLLM:
        name = "fake"

    orch = TeachingOrchestrator(store=object())
    orch._engine = object()  # 模拟已缓存
    orch.set_llm(_FakeLLM())
    assert orch._engine is None
    assert orch._llm is not None and orch._llm.name == "fake"
