"""backend.config —— 类型化应用配置（pydantic-settings + .env）。

对应 M-001 配置加载。环境变量前缀 `AITUTOR_`（如 `AITUTOR_PORT=9000`），
`.env` 自动加载；敏感字段（API key 等）只走环境变量，不写入日志。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """应用配置 schema。默认值即可零配置本地启动。"""

    model_config = SettingsConfigDict(
        env_prefix="AITUTOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ai-tutor"
    app_version: str = "2.0.0"
    host: str = "127.0.0.1"
    port: int = Field(default=18501, ge=1, le=65535)
    db_path: Path = Path("data/tutor.db")
    files_root: Path = Path("data")  # FileManager 根（{user}/{subject}/{kind}/）
    log_level: str = "INFO"
    debug: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    @property
    def db_url(self) -> str:
        """SQLAlchemy 连接串。用 posix 斜杠，避免 Windows 反斜杠路径问题。"""
        return f"sqlite:///{self.db_path.as_posix()}"


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """进程内单例配置。测试需隔离时直接 `AppConfig(...)` 构造，不走此缓存。"""
    return AppConfig()
