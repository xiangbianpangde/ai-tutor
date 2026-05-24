"""统一配置加载（L1）。

职责:
- load_env(): 从 cwd 或父目录的 .env 加载到 os.environ（不覆盖已有变量）
- get_deepseek_config(): 大小写不敏感地拿到 DeepSeek 配置 dict（或 None）

为什么大小写不敏感:
用户 .env 里写 `Deepseek_API_KEY=...`，DeepSeek 官方文档示例又是
`DEEPSEEK_API_KEY=...`。我们都接，避免改用户的 .env。
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv_file(path: Path) -> None:
    """简易 .env 解析（避免再加一个依赖）。
    格式: KEY=value；'#' 起始的行跳过；不覆盖已有 env。
    """
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if not k:
            continue
        if k in os.environ:
            continue  # 不覆盖运行时已有的
        os.environ[k] = v


def load_env() -> Path | None:
    """按优先级查找 .env 并加载：
       1. ./.env  (cwd)
       2. ../.env (cwd 的父目录)

    返回首个被加载的文件路径，或 None。
    """
    candidates = [
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            _load_dotenv_file(p)
            return p
    return None


def _getenv_ci(*names: str) -> str | None:
    """大小写不敏感地取环境变量（按 names 顺序作为优先级）。

    例: _getenv_ci("DEEPSEEK_API_KEY") 会尝试
        DEEPSEEK_API_KEY / Deepseek_API_KEY / deepseek_api_key / ...
    """
    if not names:
        return None
    # 把 os.environ 做一份小写键映射
    lower_map = {k.lower(): v for k, v in os.environ.items()}
    for name in names:
        v = os.environ.get(name)
        if v:
            return v
        v = lower_map.get(name.lower())
        if v:
            return v
    return None


def get_deepseek_config() -> dict[str, str] | None:
    """返回 {'api_key', 'base_url', 'model'} 或 None（没配 key 时）。"""
    api_key = _getenv_ci("DEEPSEEK_API_KEY", "Deepseek_API_KEY")
    if not api_key:
        return None
    base_url = _getenv_ci(
        "DEEPSEEK_BASE_URL", "Deepseek_base_url"
    ) or "https://api.deepseek.com"
    model = _getenv_ci("DEEPSEEK_CHAT_MODEL", "DEEPSEEK_MODEL") or "deepseek-chat"
    return {"api_key": api_key, "base_url": base_url, "model": model}
