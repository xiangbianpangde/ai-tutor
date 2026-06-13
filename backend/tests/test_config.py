"""backend.config 测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.config import AppConfig


def test_defaults_zero_config():
    c = AppConfig(_env_file=None)
    assert c.host == "127.0.0.1"
    assert c.port == 18501
    assert c.app_version == "2.0.0"
    assert c.db_url == f"sqlite:///{c.db_path.as_posix()}"
    assert c.db_url.startswith("sqlite:///")


def test_env_override(monkeypatch):
    monkeypatch.setenv("AITUTOR_PORT", "9123")
    assert AppConfig(_env_file=None).port == 9123


def test_port_out_of_range_rejected():
    with pytest.raises(ValidationError):
        AppConfig(_env_file=None, port=70000)
