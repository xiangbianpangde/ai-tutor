"""shared/config.py 契约测试。

职责:
- 自动从 ai-tutor/.env 或父目录 .env 加载到 os.environ
- 兼容大小写差异（Deepseek_API_KEY → DEEPSEEK_API_KEY）
- 已有环境变量不被 .env 覆盖（运行时优先）
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _use_real_dotenv_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """本模块专测 load_env 的真实加载行为，恢复被根 conftest 屏蔽的 _load_dotenv_file。"""
    import shared.config as cfg

    real = getattr(cfg, "_REAL_LOAD_DOTENV_FILE", cfg._load_dotenv_file)
    monkeypatch.setattr(cfg, "_load_dotenv_file", real)


def test_load_env_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from shared.config import load_env

    env_file = tmp_path / ".env"
    env_file.write_text("MY_TEST_VAR=hello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MY_TEST_VAR", raising=False)

    loaded = load_env()
    assert loaded == env_file
    assert os.environ.get("MY_TEST_VAR") == "hello"


def test_load_env_from_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from shared.config import load_env

    env_file = tmp_path / ".env"
    env_file.write_text("MY_PARENT_VAR=parent", encoding="utf-8")
    sub = tmp_path / "child"
    sub.mkdir()
    monkeypatch.chdir(sub)
    monkeypatch.delenv("MY_PARENT_VAR", raising=False)

    loaded = load_env()
    assert loaded == env_file
    assert os.environ.get("MY_PARENT_VAR") == "parent"


def test_existing_env_not_overridden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from shared.config import load_env

    env_file = tmp_path / ".env"
    env_file.write_text("ALREADY_SET=from_dotenv", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALREADY_SET", "from_shell")

    load_env()
    # shell 已设置的值应保留
    assert os.environ["ALREADY_SET"] == "from_shell"


def test_no_env_file_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from shared.config import load_env

    monkeypatch.chdir(tmp_path)
    assert load_env() is None


def test_get_deepseek_config_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deepseek_API_KEY / DEEPSEEK_API_KEY 都应该被 get_deepseek_config 识别。"""
    from shared.config import get_deepseek_config

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("Deepseek_API_KEY", raising=False)
    monkeypatch.setenv("Deepseek_API_KEY", "sk-test")
    monkeypatch.setenv("Deepseek_base_url", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_CHAT_MODEL", "deepseek-chat")

    cfg = get_deepseek_config()
    assert cfg is not None
    assert cfg["api_key"] == "sk-test"
    assert cfg["base_url"] == "https://api.deepseek.com"
    assert cfg["model"] == "deepseek-chat"


def test_get_deepseek_config_returns_none_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from shared.config import get_deepseek_config

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("Deepseek_API_KEY", raising=False)
    monkeypatch.delenv("deepseek_api_key", raising=False)
    assert get_deepseek_config() is None


def test_get_deepseek_config_uses_default_base_url_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """没显式设 base_url/model 时给合理默认。"""
    from shared.config import get_deepseek_config

    for var in ("DEEPSEEK_BASE_URL", "Deepseek_base_url", "DEEPSEEK_CHAT_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-x")
    cfg = get_deepseek_config()
    assert cfg is not None
    assert cfg["base_url"] == "https://api.deepseek.com"
    assert cfg["model"] == "deepseek-chat"
