"""共享 pytest fixtures。

- tmp_filestore: 临时文件存储
- tmp_db: 临时 SQLite，每个测试独立
- sample_concept / sample_relation: 最小合法 KG 节点和边
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

# 让 tests 能 import shared 包（pyproject root）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.schemas import (
    Concept,
    ConceptClassification,
    ConceptDifficulty,
    Relation,
    SourceRef,
)
from shared.storage import FileStore, RelationalStore


@pytest.fixture(autouse=True)
def _isolate_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试隔离：禁止任何 server/_llm() 偶然连真实 DeepSeek，并保证离线确定性。

    两道防线：
    1. 删除环境里已有的 DeepSeek/Tavily key（覆盖大小写变体）。
    2. **把 shared.config._load_dotenv_file 打成 no-op**——否则处理器里调用的
       load_env()（如 knowledge server 的 acquire_subject）会在测试**进行中**把
       真实 .env 的 key 原样写回 os.environ，绕过上面的 delenv，导致 respond 等
       测试走真实付费 API、非确定性失败（见 343s 实跑事故）。
    """
    for var in (
        "DEEPSEEK_API_KEY", "Deepseek_API_KEY", "deepseek_api_key",
        "TAVILY_API_KEY", "Tavily_API_KEY", "tavily_api_key",
    ):
        monkeypatch.delenv(var, raising=False)
    # 屏蔽 .env 加载：handler 里的 load_env() 调用变成无操作（不污染 os.environ）。
    # 先把真实实现存一份（仅首次），供 test_config 等需要真实加载的测试显式恢复。
    import shared.config as _cfg

    if not hasattr(_cfg, "_REAL_LOAD_DOTENV_FILE"):
        _cfg._REAL_LOAD_DOTENV_FILE = _cfg._load_dotenv_file
    monkeypatch.setattr(_cfg, "_load_dotenv_file", lambda _p: None, raising=False)
    try:
        from servers.knowledge_mcp import server as kserver

        monkeypatch.setattr(kserver, "_LLM_SINGLETON", None, raising=False)
    except ImportError:
        pass


@pytest.fixture
def tmp_filestore(tmp_path: Path) -> FileStore:
    return FileStore(tmp_path / "store")


@pytest.fixture
def tmp_db(tmp_path: Path) -> RelationalStore:
    """每个测试一个独立的 SQLite 文件。"""
    db_path = tmp_path / "test.db"
    store = RelationalStore(f"sqlite:///{db_path}")
    store.init_schema()
    return store


@pytest.fixture
def sample_concept() -> Concept:
    return Concept(
        id="gaoshu-v8:2.1.1:limit_epsilon_delta",
        names=["极限的 ε-δ 定义", "limit_epsilon_delta"],
        category="definition",
        definition="lim 形式化定义",
        informal_description="任给 ε > 0...",
        classification=ConceptClassification(
            bloom_level="understand",
            abstract_level=0.7,
            domain="高等数学/极限论",
        ),
        difficulty=ConceptDifficulty(
            prereq_count=2,
            prereq_max_depth=1,
            formula_density=0.6,
            coupling=0.4,
            cognitive_load_estimate=0.7,
            typical_learning_time_min=45,
        ),
        confidence=0.85,
        sources=[SourceRef(type="textbook", ref="同济高数v8", page="P23")],
    )


@pytest.fixture
def sample_relation() -> Relation:
    return Relation(
        from_id="gaoshu-v8:1.1.1:sequence_limit",
        to_id="gaoshu-v8:2.1.1:limit_epsilon_delta",
        type="prerequisite_strong",
        weight=0.9,
        explanation="数列极限是函数极限的前置",
        confidence=0.95,
    )
