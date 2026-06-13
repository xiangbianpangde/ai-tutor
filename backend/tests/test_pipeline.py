"""backend.pipeline 测试（M-014）：NoiseGate 红线 + DataPipeline 编排。"""
from __future__ import annotations

import pytest

from backend.pipeline import DataPipeline, NoiseGate
from shared.errors import TutorError
from shared.storage import RelationalStore

# 真实禁类样本（is_noise_title=True）vs 干净概念
NOISE = ["参考文献", "致谢", "目录", "config.py", "创建线程池，比如最多4个"]
CLEAN = ["偏导数", "梯度下降", "知识蒸馏", "反向传播", "注意力机制"]


def test_audit_clean_passes():
    gate = NoiseGate()
    r = gate.audit(CLEAN)
    assert r["noise_count"] == 0 and r["noise_rate"] == 0.0 and r["passed"] is True


def test_audit_counts_noise():
    gate = NoiseGate()
    r = gate.audit(CLEAN + NOISE)  # 5 clean + 5 noise → 50%
    assert r["total"] == 10
    assert r["noise_count"] == 5
    assert r["noise_rate"] == 0.5
    assert r["passed"] is False  # 超 5%
    assert "参考文献" in r["offenders"]


def test_threshold_boundary():
    gate = NoiseGate(threshold=0.1)
    names = CLEAN * 4 + ["参考文献"]  # 1/21 ≈ 4.76% < 10%
    assert gate.audit(names)["passed"] is True


def _seed_kg(store, kg_id, names):
    from shared.models import ConceptRow, KnowledgeGraphRow
    with store.session() as s:
        s.add(KnowledgeGraphRow(kg_id=kg_id, subject_id="sub", corpus_id="c1",
                                version="v1", node_count=len(names), edge_count=0, manifest_json={}))
        for i, n in enumerate(names):
            s.add(ConceptRow(
                id=f"{kg_id}:{i}", kg_id=kg_id, base_id=f"{kg_id}:{i}",
                name_primary=n, names_json=[n], category="definition",
                definition=f"{n} 的定义", informal_description="",
                abstract_level=0.5, bloom_level="understand", domain="math",
                cognitive_load_estimate=0.4, typical_learning_time_min=20,
                prereq_count=0, prereq_max_depth=0, formula_density=0.3, coupling=0.2,
                confidence=0.8, full_json={},
            ))
        s.commit()


def test_audit_kg_reads_concepts(tmp_path):
    store = RelationalStore(f"sqlite:///{(tmp_path / 'kg.db').as_posix()}")
    store.init_schema()
    _seed_kg(store, "kg-x", CLEAN + ["参考文献"])
    r = NoiseGate().audit_kg(store, "kg-x")
    assert r["kg_id"] == "kg-x" and r["total"] == 6 and r["noise_count"] == 1


def test_audit_kg_missing(tmp_path):
    store = RelationalStore(f"sqlite:///{(tmp_path / 'kg.db').as_posix()}")
    store.init_schema()
    with pytest.raises(TutorError) as ei:
        NoiseGate().audit_kg(store, "nope")
    assert ei.value.code == "KG_NOT_FOUND"


def test_noise_audit_endpoint(client):
    _seed_kg(client.app.state.store, "kg-ep", CLEAN + ["致谢", "目录"])
    r = client.get("/api/knowledge/graphs/kg-ep/noise")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["kg_id"] == "kg-ep" and data["noise_count"] == 2 and data["passed"] is False
    # 不存在的 KG → 404 KG_NOT_FOUND
    miss = client.get("/api/knowledge/graphs/nope/noise")
    assert miss.status_code == 404
    assert miss.json()["error"]["code"] == "KG_NOT_FOUND"


class _Rec:
    def __init__(self):
        self.calls = []

    def update(self, p, m=None):
        self.calls.append((p, m))


def test_pipeline_runs_stages_in_order_with_noise_audit():
    order = []

    def acquire(rep, ctx):
        order.append("acquire")
        return {**ctx, "corpus_id": "c1"}

    def clean(rep, ctx):
        order.append("clean")
        return ctx

    def structure(rep, ctx):
        order.append("structure")
        return {**ctx, "kg_id": "kg1", "concept_names": CLEAN + ["参考文献"]}

    pipe = DataPipeline(acquire=acquire, clean=clean, structure=structure)
    rec = _Rec()
    result = pipe.run(rec, subject_id="ml", sources=[])
    assert order == ["acquire", "clean", "structure"]
    assert result["corpus_id"] == "c1" and result["kg_id"] == "kg1"
    assert result["noise_audit"]["noise_count"] == 1
    assert rec.calls[-1] == (1.0, "完成")  # 进度走到 100%
