"""backend.main —— 后端统一入口。

    uv run python -m backend.main

启动 Uvicorn 监听 ``config.host:config.port``（默认 127.0.0.1:18501）。
"""
from __future__ import annotations

import uvicorn

from .app import create_app
from .config import get_config

# 模块级 app 供 `uvicorn backend.main:app` 或 Electron spawn 复用。
app = create_app()


def main() -> None:
    config = get_config()
    uvicorn.run(app, host=config.host, port=config.port, log_level=config.log_level.lower())


if __name__ == "__main__":
    main()
