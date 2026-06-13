"""SQLAlchemy ORM 模型 — 持久化层。

合同来源: ai-tutor-system-design/specs/database-schema.md
Pydantic 业务模型见 shared/schemas.py；二者不互转，调用方用 .model_validate() 串联。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。Alembic 自动迁移用 Base.metadata。"""

    pass


# --------------------------------------------------------------------------- #
# 用户与科目
# --------------------------------------------------------------------------- #


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="active")
    kg_id: Mapped[str | None] = mapped_column(String(128))


# --------------------------------------------------------------------------- #
# L4 知识工程
# --------------------------------------------------------------------------- #


class Corpus(Base):
    __tablename__ = "corpora"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KnowledgeGraphRow(Base):
    """注意类名加 Row 后缀，避免与 schemas.KnowledgeGraph 冲突。"""

    __tablename__ = "knowledge_graphs"

    kg_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    corpus_id: Mapped[str] = mapped_column(ForeignKey("corpora.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    node_count: Mapped[int] = mapped_column(Integer, nullable=False)
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_json: Mapped[dict | None] = mapped_column(JSON)
    manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # K3：版本树指针。None = 根版本；非空指向上一版 kg_id。
    parent_kg_id: Mapped[str | None] = mapped_column(String(128), index=True)


class ConceptRow(Base):
    __tablename__ = "concepts"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    kg_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_graphs.kg_id"), nullable=False
    )
    # K3：跨 KG 版本的稳定身份。同一个概念在不同 KG 版本中 id 可能加 @v 后缀，
    # 但 base_id 始终是原始无后缀 id。BKT / 复习历史等用 base_id 跨版本继承。
    # 默认在 __init__ 里同步等于 id（见下方 __init__）。
    base_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name_primary: Mapped[str] = mapped_column(String(255), nullable=False)
    names_json: Mapped[list] = mapped_column(JSON, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    informal_description: Mapped[str | None] = mapped_column(Text)
    abstract_level: Mapped[float] = mapped_column(nullable=False)
    bloom_level: Mapped[str] = mapped_column(String(32), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    cognitive_load_estimate: Mapped[float] = mapped_column(nullable=False)
    typical_learning_time_min: Mapped[int] = mapped_column(Integer, nullable=False)
    prereq_count: Mapped[int] = mapped_column(Integer, nullable=False)
    prereq_max_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    formula_density: Mapped[float] = mapped_column(nullable=False)
    coupling: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    full_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_concepts_kg", "kg_id"),
        Index("idx_concepts_domain", "domain"),
        Index("idx_concepts_base", "base_id"),
    )

    def __init__(self, **kw):
        """如果 base_id 未提供 → 默认等于 id（K3 之前的 concept 自动迁移）。"""
        if "base_id" not in kw or kw.get("base_id") is None:
            kw["base_id"] = kw.get("id")
        super().__init__(**kw)


class RelationRow(Base):
    __tablename__ = "relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kg_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_graphs.kg_id"), nullable=False
    )
    from_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), nullable=False)
    to_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    deprecated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("from_id != to_id", name="ck_relations_no_self_loop"),
        Index("idx_relations_kg", "kg_id"),
        Index("idx_relations_from", "from_id"),
        Index("idx_relations_to", "to_id"),
        Index("idx_relations_type", "type"),
    )


# --------------------------------------------------------------------------- #
# L5 学习者建模
# --------------------------------------------------------------------------- #


class BKTParamRow(Base):
    __tablename__ = "bkt_params"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    concept_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    p_learn: Mapped[float] = mapped_column(default=0.15, nullable=False)
    p_guess: Mapped[float] = mapped_column(default=0.12, nullable=False)
    p_slip: Mapped[float] = mapped_column(default=0.08, nullable=False)
    p_init: Mapped[float] = mapped_column(default=0.05, nullable=False)
    p_mastery: Mapped[float] = mapped_column(default=0.05, nullable=False)
    n_observations: Mapped[int] = mapped_column(Integer, default=0)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime)


class KnowledgeSnapshotRow(Base):
    __tablename__ = "knowledge_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_snapshots_user_subject", "user_id", "subject_id"),
    )


class LearnerProfileRow(Base):
    __tablename__ = "learner_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    profile_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# --------------------------------------------------------------------------- #
# L3 长期记忆
# --------------------------------------------------------------------------- #


class ReviewHistoryRow(Base):
    __tablename__ = "review_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    concept_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    review_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    days_since_last: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy: Mapped[float] = mapped_column(nullable=False)
    review_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    error_types: Mapped[list | None] = mapped_column(JSON)
    session_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_review_user", "user_id"),
        Index("idx_review_concept", "concept_id"),
        Index("idx_review_date", "review_date"),
    )


class ForgettingCurveRow(Base):
    __tablename__ = "forgetting_curves"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    concept_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    lambda_param: Mapped[float] = mapped_column("lambda", nullable=False)
    r_squared: Mapped[float | None] = mapped_column()
    n_data_points: Mapped[int] = mapped_column(Integer, default=0)
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_streak: Mapped[int] = mapped_column(Integer, default=0)


# --------------------------------------------------------------------------- #
# L2 会话
# --------------------------------------------------------------------------- #


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_status", "status"),
    )


# --------------------------------------------------------------------------- #
# 多 Session 学习计划（P0 #3：跨天调度）
# --------------------------------------------------------------------------- #


class LearningPlanRow(Base):
    """跨 Session 的持久化学习计划，按 (user, subject) 唯一。"""

    __tablename__ = "learning_plans"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), primary_key=True)
    kg_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
