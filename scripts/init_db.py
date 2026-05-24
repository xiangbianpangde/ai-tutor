"""开发期一键建表。生产请用 alembic upgrade head。

Usage:
    uv run python scripts/init_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.storage import RelationalStore


def main() -> None:
    store = RelationalStore.from_env()
    store.init_schema()
    print(f"OK: schema initialized at {store.url}")


if __name__ == "__main__":
    main()
