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
    """测试隔离：禁止 server._llm() 偶然连真实 DeepSeek。

    pytest 在 ai-tutor/ 下运行时，shared.config.load_env() 会从父目录
    加载 .env（用户开发用），导致测试意外走付费 API。
    """
    for var in ("DEEPSEEK_API_KEY", "Deepseek_API_KEY", "deepseek_api_key"):
        monkeypatch.delenv(var, raising=False)
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
