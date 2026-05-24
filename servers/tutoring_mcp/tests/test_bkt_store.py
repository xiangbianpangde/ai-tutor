"""BKT 持久化契约测试。

BKTStore 职责:
- load(user_id, concept_id) → 没记录返回默认 BKTParams
- save(user_id, BKTParams) → upsert 到 bkt_params 表
- 不同 user_id 间互不干扰
"""
from __future__ import annotations

import pytest

from shared.models import User
from shared.schemas import BKTParams
from shared.storage import RelationalStore


@pytest.fixture
def db_with_users(tmp_db: RelationalStore) -> RelationalStore:
    with tmp_db.session() as s:
        s.add(User(id="u1"))
        s.add(User(id="u2"))
        s.commit()
    return tmp_db


def test_load_missing_returns_default(db_with_users: RelationalStore) -> None:
    from servers.tutoring_mcp.bkt_store import BKTStore

    store = BKTStore(db_with_users)
    p = store.load(user_id="u1", concept_id="x:1.1:a")
    assert p.concept_id == "x:1.1:a"
    assert p.p_mastery == BKTParams(concept_id="x:1.1:a").p_mastery
    assert p.n_observations == 0


def test_save_then_load_round_trip(db_with_users: RelationalStore) -> None:
    from servers.tutoring_mcp.bkt import update
    from servers.tutoring_mcp.bkt_store import BKTStore

    store = BKTStore(db_with_users)
    p0 = store.load(user_id="u1", concept_id="x:1.1:a")
    p1 = update(p0, correct=True)
    store.save(user_id="u1", params=p1)

    reloaded = store.load(user_id="u1", concept_id="x:1.1:a")
    assert reloaded.p_mastery == pytest.approx(p1.p_mastery)
    assert reloaded.n_observations == 1


def test_save_is_upsert_not_duplicate(db_with_users: RelationalStore) -> None:
    """同 (user, concept) 多次 save 不能产生多行。"""
    from servers.tutoring_mcp.bkt import update
    from servers.tutoring_mcp.bkt_store import BKTStore

    store = BKTStore(db_with_users)
    p = store.load(user_id="u1", concept_id="x:1.1:a")
    for _ in range(5):
        p = update(p, correct=True)
        store.save(user_id="u1", params=p)

    from shared.models import BKTParamRow
    with db_with_users.session() as s:
        count = s.query(BKTParamRow).filter_by(user_id="u1", concept_id="x:1.1:a").count()
    assert count == 1


def test_users_isolated(db_with_users: RelationalStore) -> None:
    """u1 的 BKT 改动不影响 u2。"""
    from servers.tutoring_mcp.bkt import update
    from servers.tutoring_mcp.bkt_store import BKTStore

    store = BKTStore(db_with_users)

    p1 = update(store.load("u1", "x:1.1:a"), correct=True)
    store.save("u1", p1)

    p2 = store.load("u2", "x:1.1:a")
    assert p2.n_observations == 0
    assert p2.p_mastery == BKTParams(concept_id="x:1.1:a").p_mastery


def test_record_observation_one_call(db_with_users: RelationalStore) -> None:
    """便捷方法 record_observation 一行做完 load + update + save。"""
    from servers.tutoring_mcp.bkt_store import BKTStore

    store = BKTStore(db_with_users)
    result = store.record_observation(
        user_id="u1", concept_id="x:1.1:a", correct=True
    )
    assert result.n_observations == 1
    # 真的落库
    assert store.load("u1", "x:1.1:a").n_observations == 1


def test_seed_prior_sets_mastery_without_observation(db_with_users: RelationalStore) -> None:
    """冷启动种先验：设 p_init/p_mastery，不计为一次答题观测。"""
    from servers.tutoring_mcp.bkt_store import BKTStore

    store = BKTStore(db_with_users)
    p = store.seed_prior(user_id="u1", concept_id="x:1.1:a", mastery=0.9)
    assert p.p_mastery == pytest.approx(0.9)
    assert p.p_init == pytest.approx(0.9)
    assert p.n_observations == 0
    # 落库可重载
    reloaded = store.load("u1", "x:1.1:a")
    assert reloaded.p_mastery == pytest.approx(0.9)


def test_seed_prior_clamps_range(db_with_users: RelationalStore) -> None:
    from servers.tutoring_mcp.bkt_store import BKTStore

    store = BKTStore(db_with_users)
    assert store.seed_prior(user_id="u1", concept_id="x:1.1:a", mastery=1.5).p_mastery == 1.0
    assert store.seed_prior(user_id="u1", concept_id="x:1.1:b", mastery=-0.2).p_mastery == 0.0


def test_seed_prior_does_not_clobber_observed(db_with_users: RelationalStore) -> None:
    """已有真实答题记录的概念不被先验覆盖（避免摸底冲掉真实学习数据）。"""
    from servers.tutoring_mcp.bkt_store import BKTStore

    store = BKTStore(db_with_users)
    observed = store.record_observation(user_id="u1", concept_id="x:1.1:a", correct=True)
    p = store.seed_prior(user_id="u1", concept_id="x:1.1:a", mastery=0.9)
    # 保持观测后的值，不被先验覆盖
    assert p.n_observations == 1
    assert p.p_mastery == pytest.approx(observed.p_mastery)
