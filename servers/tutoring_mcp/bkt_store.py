"""BKT 状态持久化到 bkt_params 表。

接口:
  load(user_id, concept_id)        → BKTParams（没记录返回默认值）
  save(user_id, params)            → upsert
  record_observation(user_id, concept_id, correct) → 一步完成 load+update+save
"""
from __future__ import annotations

from datetime import datetime

from shared.models import BKTParamRow
from shared.schemas import BKTParams
from shared.storage import RelationalStore

from .bkt import update as _bkt_update


class BKTStore:
    def __init__(self, db: RelationalStore) -> None:
        self.db = db

    def load(self, user_id: str, concept_id: str) -> BKTParams:
        with self.db.session() as s:
            row = s.get(BKTParamRow, (user_id, concept_id))
            if row is None:
                return BKTParams(concept_id=concept_id)
            return BKTParams(
                concept_id=row.concept_id,
                p_learn=row.p_learn,
                p_guess=row.p_guess,
                p_slip=row.p_slip,
                p_init=row.p_init,
                p_mastery=row.p_mastery,
                n_observations=row.n_observations,
                last_updated=row.last_updated,
            )

    def save(self, user_id: str, params: BKTParams) -> None:
        with self.db.session() as s:
            row = s.get(BKTParamRow, (user_id, params.concept_id))
            if row is None:
                row = BKTParamRow(
                    user_id=user_id,
                    concept_id=params.concept_id,
                )
                s.add(row)
            row.p_learn = params.p_learn
            row.p_guess = params.p_guess
            row.p_slip = params.p_slip
            row.p_init = params.p_init
            row.p_mastery = params.p_mastery
            row.n_observations = params.n_observations
            row.last_updated = params.last_updated or datetime.utcnow()
            s.commit()

    def record_observation(
        self, *, user_id: str, concept_id: str, correct: bool
    ) -> BKTParams:
        current = self.load(user_id, concept_id)
        updated = _bkt_update(current, correct=correct)
        self.save(user_id, updated)
        return updated

    def seed_prior(
        self, *, user_id: str, concept_id: str, mastery: float
    ) -> BKTParams:
        """冷启动用：把先验掌握度种进 p_init/p_mastery，不计为答题观测。

        若该 (user, concept) 已有真实答题记录（n_observations>0）则不覆盖——
        真实学习数据优先于摸底先验。
        """
        current = self.load(user_id, concept_id)
        if current.n_observations > 0:
            return current
        m = max(0.0, min(1.0, float(mastery)))
        current.p_init = m
        current.p_mastery = m
        self.save(user_id, current)
        return current
