"""共享 Pydantic 模型 — 跨层接口合同。

合同来源:
  ai-tutor-system-design/specs/shared-schemas.md
  ai-tutor-system-design/specs/pgfga-integration.md
  ai-tutor-system-design/specs/adopted-fixes.md (review_kg / update_kg)

导入顺序:
  1) 基础类型
  2) L4 知识工程
  3) L5 学习者建模 + PGFGA 心流
  4) L3 长期记忆
  5) L2 短期记忆
  6) L6 教学引擎 + PGFGA 防火墙
  7) L7 MCP Tool I/O
"""
from __future__ import annotations

from datetime import datetime
from enum import IntEnum
from typing import Any, Literal

from pydantic import BaseModel as _PydanticBase
from pydantic import ConfigDict, Field, model_validator


class BaseModel(_PydanticBase):
    """项目内统一基类：拒绝未知字段 + assign 时校验。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# =========================================================================== #
# 1) 基础类型
# =========================================================================== #


class SourceRef(BaseModel):
    type: Literal["textbook", "video", "web", "lecture_note"]
    ref: str
    page: str | None = None
    timestamp: str | None = None
    text: str | None = None
    url: str | None = None


class ArtifactURI(BaseModel):
    uri: str
    mime_type: str
    size_bytes: int
    expires_at: datetime | None = None


class Example(BaseModel):
    text: str
    type: Literal["proof", "computation", "application", "counterexample", "pathological"]
    difficulty: float | None = Field(default=None, ge=0.0, le=1.0)


# =========================================================================== #
# 2) L4 知识工程
# =========================================================================== #


CONCEPT_ID_PATTERN = r"^[a-z0-9][a-z0-9\-]*:\d+(?:\.\d+)*:[a-z0-9][a-z0-9_]*$"


class ConceptClassification(BaseModel):
    bloom_level: Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
    abstract_level: float = Field(ge=0.0, le=1.0)
    domain: str
    cross_domain_tags: list[str] = Field(default_factory=list)


class ConceptDifficulty(BaseModel):
    prereq_count: int = Field(ge=0)
    prereq_max_depth: int = Field(ge=0)
    formula_density: float = Field(ge=0.0, le=1.0)
    coupling: float = Field(ge=0.0, le=1.0)
    cognitive_load_estimate: float = Field(ge=0.0, le=1.0)
    typical_learning_time_min: int = Field(ge=1, le=120)
    # depth=full 时由 kg_full.compute_calibrated_difficulty 写入的综合难度分；
    # toc/concept 模式留 None。将来有学习者答题数据可换成学习模型。
    calibrated_difficulty: float | None = Field(default=None, ge=0.0, le=1.0)


class Concept(BaseModel):
    """KG 节点。id 必须匹配 `{subject}:{chapter}.{section}.{index}:{slug}`。"""

    id: str = Field(pattern=CONCEPT_ID_PATTERN)
    names: list[str]
    category: Literal[
        "definition", "theorem", "formula", "method",
        "property", "axiom", "lemma", "corollary",
    ]
    definition: str
    informal_description: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    classification: ConceptClassification
    difficulty: ConceptDifficulty
    examples: list[Example] = Field(default_factory=list)
    counter_examples: list[Example] = Field(default_factory=list)
    common_misconceptions: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


SemanticRelation = Literal[
    "is_a", "part_of",
    "prerequisite_strong", "prerequisite_weak",
    "analogous_to", "contradicts",
    "generalizes", "instantiates",
    "proves", "computed_from",
    "common_pitfall", "historical_origin",
]


class Relation(BaseModel):
    from_id: str
    to_id: str
    type: SemanticRelation
    weight: float = Field(ge=0.0, le=1.0)
    explanation: str
    sources: list[SourceRef] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    deprecated: bool = False

    @model_validator(mode="after")
    def _no_self_loop(self) -> Relation:
        if self.from_id == self.to_id:
            raise ValueError(f"Relation 不能自环: {self.from_id} -> {self.to_id}")
        return self


class QualityReport(BaseModel):
    overall: Literal["pass", "fail", "pass_with_warnings"]
    chapter_coverage: float = Field(ge=0.0, le=1.0)
    isolated_nodes: int = Field(ge=0)
    cycles: int = Field(ge=0)
    avg_confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class KnowledgeGraph(BaseModel):
    kg_id: str
    subject_id: str
    version: str
    created_at: datetime
    source_corpora: list[str]
    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    quality_report: QualityReport
    nodes: dict[str, Concept]
    edges: list[Relation]
    file_paths: dict[str, str] = Field(default_factory=dict)


class CorpusSource(BaseModel):
    type: Literal["textbook", "video_transcript", "web"]
    format: str
    original_file: str | None = None
    converted_file: str | None = None
    pages: int | None = None
    duration_min: int | None = None
    language: str = "zh"
    parser: str | None = None
    parser_version: str | None = None


class CorpusManifest(BaseModel):
    corpus_id: str
    subject: str
    version: str
    created_at: datetime
    sources: list[CorpusSource]
    total_chapters: int = Field(ge=0)
    total_sections: int = Field(ge=0)
    estimated_concepts: int = Field(ge=0)
    file_paths: dict[str, str] = Field(default_factory=dict)


# === KG 人工确认（adopted-fixes 修正 1）===
class KgEditAction(BaseModel):
    op: Literal[
        "edit_definition", "add_edge", "remove_edge",
        "delete_concept", "merge_concepts", "approve_all",
    ]
    concept_id: str | None = None
    new_definition: str | None = None
    edge: Relation | None = None
    merge_target_id: str | None = None
    note: str | None = None


class LowConfidenceConcept(BaseModel):
    concept_id: str
    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    definition_preview: str


class ReviewKGResult(BaseModel):
    kg_id: str
    mode: Literal["quick", "full"]
    low_confidence_concepts: list[LowConfidenceConcept] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    mermaid_thumb: str | None = None
    full_mermaid: str | None = None
    suggested_actions: list[KgEditAction] = Field(default_factory=list)


class KgUpdateFailure(BaseModel):
    action_index: int
    reason: str


class KgUpdateResult(BaseModel):
    kg_id: str
    new_version: str
    applied: int = Field(ge=0)
    failed: list[KgUpdateFailure] = Field(default_factory=list)
    new_quality_report: QualityReport


# =========================================================================== #
# 3) L5 学习者建模 + PGFGA 心流
# =========================================================================== #


class BKTParams(BaseModel):
    concept_id: str
    p_learn: float = Field(default=0.15, ge=0.0, le=1.0)
    p_guess: float = Field(default=0.12, ge=0.0, le=1.0)
    p_slip: float = Field(default=0.08, ge=0.0, le=1.0)
    p_init: float = Field(default=0.05, ge=0.0, le=1.0)
    p_mastery: float = Field(default=0.05, ge=0.0, le=1.0)
    last_updated: datetime | None = None
    n_observations: int = Field(default=0, ge=0)


class DKTOutput(BaseModel):
    concept_id: str
    mastery_prob: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    predicted_correctness: float = Field(ge=0.0, le=1.0)
    next_review_at: datetime | None = None
    predicted_error_type: str | None = None


ErrorType = Literal[
    "concept_confusion", "symbol_mistake", "logic_gap",
    "syntax_error", "prereq_gap", "overgeneralization",
    "arithmetic_mistake", "reading_error", "careless", "blank",
]


class ErrorDiagnosis(BaseModel):
    error_type: ErrorType
    root_concept_id: str
    surface_concept_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    remediation_suggestion: str


class ConceptMastery(BaseModel):
    bkt_mastery: float = Field(ge=0.0, le=1.0)
    dkt_mastery: float | None = Field(default=None, ge=0.0, le=1.0)
    n_correct: int = Field(default=0, ge=0)
    n_incorrect: int = Field(default=0, ge=0)
    last_error_type: str | None = None
    last_interaction_at: datetime | None = None
    forgetting_rate_lambda: float | None = None
    review_streak: int = Field(default=0, ge=0)


class KnowledgeSnapshot(BaseModel):
    user_id: str
    subject_id: str
    timestamp: datetime
    concepts: dict[str, ConceptMastery]
    total_concepts: int = Field(ge=0)
    mastered_count: int = Field(ge=0)
    learning_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    avg_mastery: float = Field(ge=0.0, le=1.0)


class CognitiveProfile(BaseModel):
    working_memory_span: int = Field(default=5, ge=2, le=9)
    abstract_tolerance: float = Field(default=0.5, ge=0.0, le=1.0)
    transfer_ability: float = Field(default=0.4, ge=0.0, le=1.0)
    analogical_reasoning: float = Field(default=0.5, ge=0.0, le=1.0)
    mathematical_maturity: float = Field(default=0.4, ge=0.0, le=1.0)
    preferred_modality: dict[str, float] = Field(
        default_factory=lambda: {"text": 0.4, "visual": 0.3, "interactive": 0.2, "audio": 0.1}
    )
    information_processing_speed: float = 1.0


class MetacognitiveProfile(BaseModel):
    self_assessment_accuracy: float = Field(default=0.6, ge=0.0, le=1.0)
    help_seeking_tendency: float = Field(default=0.5, ge=0.0, le=1.0)
    frustration_threshold: int = Field(default=3, ge=1, le=10)
    confidence_calibration: float = Field(default=0.0, ge=-1.0, le=1.0)
    growth_mindset_score: float = Field(default=0.6, ge=0.0, le=1.0)


class BehavioralProfile(BaseModel):
    peak_learning_hours: list[int] = Field(default_factory=list)
    optimal_session_length_min: int = 45
    attention_decay_rate: float = 0.02
    streak_momentum: float = Field(default=0.5, ge=0.0, le=1.0)
    review_compliance_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    preferred_pace: Literal["fast", "moderate", "thorough"] = "moderate"


class LearnerProfile(BaseModel):
    user_id: str
    version: int = 1
    created_at: datetime | None = None
    last_updated: datetime | None = None
    total_study_hours: float = 0.0
    cognitive: CognitiveProfile = Field(default_factory=CognitiveProfile)
    metacognitive: MetacognitiveProfile = Field(default_factory=MetacognitiveProfile)
    behavioral: BehavioralProfile = Field(default_factory=BehavioralProfile)
    weakest_domains: list[str] = Field(default_factory=list)
    strongest_domains: list[str] = Field(default_factory=list)
    total_concepts_mastered: int = 0


# --- PGFGA 心流（详见 specs/pgfga-integration.md §二）---
class FlowLevel(IntEnum):
    SILENT = 0
    SHALLOW = 1
    FLUENT = 2
    DEEP = 3
    IMMERSED = 4


class FlowSignals(BaseModel):
    answer_length_growth: bool = False
    depth_increasing: bool = False
    initiative_taking: bool = False
    hesitation_decreasing: bool = False
    inter_turn_speed_up: bool = False
    self_correction_quality: bool = False
    withdrawal_pattern: bool = False
    help_seeking_spike: bool = False
    answer_regression: bool = False
    emotional_flatness: bool = False


# === L5 → L6 接口 ===
class TeachingContext(BaseModel):
    current_focus_concept_id: str
    position_in_plan: int
    estimated_time_remaining_min: int
    mastery_map: dict[str, float]
    cognitive_load: float = Field(ge=0.0, le=1.0)
    error_history: list[ErrorDiagnosis] = Field(default_factory=list)
    learner_profile: LearnerProfile
    weak_points: list[str] = Field(default_factory=list)


# =========================================================================== #
# 4) L3 长期记忆
# =========================================================================== #


class ForgettingCurve(BaseModel):
    user_id: str
    concept_id: str
    lambda_param: float
    r_squared: float | None = None
    n_data_points: int = Field(default=0, ge=0)
    last_review_at: datetime | None = None
    next_review_at: datetime | None = None
    review_streak: int = Field(default=0, ge=0)


class ReviewRecord(BaseModel):
    user_id: str
    concept_id: str
    subject_id: str
    review_date: datetime
    days_since_last: int = Field(ge=0)
    accuracy: float = Field(ge=0.0, le=1.0)
    review_mode: str
    error_types: list[str] | None = None
    session_id: str | None = None


class DailyReviewSection(BaseModel):
    concept_id: str
    priority: float
    predicted_recall: float = Field(ge=0.0, le=1.0)
    estimated_minutes: int = Field(ge=1)
    review_mode: Literal["quick_quiz", "concept_map", "teach_back", "error_revisit"]
    urgency_context: str


class DailyReviewPlan(BaseModel):
    user_id: str
    subject_id: str
    date: str
    sections: list[DailyReviewSection]
    total_estimated_min: int = Field(ge=0)
    tips: list[str] = Field(default_factory=list)


# =========================================================================== #
# 5) L2 短期记忆
# =========================================================================== #


class FocusState(BaseModel):
    primary_concept: str = ""
    supporting_concepts: list[str] = Field(default_factory=list)
    last_action_type: str | None = None
    # 最近一次教学动作的内容（截断）。判分必须能看到题目本身——
    # 只比对「概念定义 vs 答案」会把答非所问判对（#18/#20 根因）。
    last_action_content: str | None = None
    expected_next_action: str | None = None


class InterruptCheckpoint(BaseModel):
    saved_at: datetime
    current_concept_id: str
    position_in_plan: int
    strategy: str
    strategy_state: str
    focus: FocusState
    pending_action: dict[str, Any] | None = None
    pending_question: str | None = None
    context_tail: list[dict[str, Any]] = Field(default_factory=list)
    cognitive_load_at_save: float = Field(ge=0.0, le=1.0)


class SessionMeta(BaseModel):
    started_at: datetime
    total_elapsed_min: float = 0.0
    active_time_min: float = 0.0
    interrupt_count: int = 0
    checkpoint_count: int = 0
    current_cognitive_load: float = Field(default=0.0, ge=0.0, le=1.0)
    # 连续学习段（#10 学习时长→休息建议）：作答间隔超过阈值视为休息过、重置起点
    continuous_start_at: datetime | None = None
    last_break_suggested_at: datetime | None = None


class SessionStats(BaseModel):
    concepts_covered: list[str] = Field(default_factory=list)
    concepts_mastered: list[str] = Field(default_factory=list)
    total_questions_asked: int = 0
    correct_rate: float = 0.0
    errors_by_type: dict[str, int] = Field(default_factory=dict)
    # PGFGA 增益回路：学生主动跳过/换主题次数（pace_complaint → change_topic）
    # 用于 detect_break 的 avoidance_pattern 检测
    skipped_count: int = 0


class SessionContext(BaseModel):
    session_id: str
    user_id: str
    subject_id: str
    status: Literal["idle", "active", "interrupted", "completed", "expired"] = "idle"
    teaching_plan_id: str | None = None
    current_concept_id: str | None = None
    position_in_plan: int = 0
    current_strategy: str | None = None
    current_strategy_state: str | None = None
    # 当前策略的内部状态快照（计数器/产出/pace 参数），供引擎无损重建策略实例
    strategy_internal: dict[str, Any] = Field(default_factory=dict)
    interrupt_checkpoint: InterruptCheckpoint | None = None
    recent_history: list[dict[str, Any]] = Field(default_factory=list)
    focus: FocusState = Field(default_factory=FocusState)
    meta: SessionMeta
    session_stats: SessionStats = Field(default_factory=SessionStats)


# =========================================================================== #
# 6) L6 教学引擎 + PGFGA 防火墙
# =========================================================================== #


class ReductionOfOrderParams(BaseModel):
    topology: Literal["bottom_up", "top_down"] = "bottom_up"
    skip_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    max_concepts_per_session: int = Field(default=8, ge=1)
    review_interleave_ratio: float = Field(default=0.25, ge=0.0, le=1.0)


class FeynmanParams(BaseModel):
    fidelity_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    max_attempts: int = Field(default=3, ge=1, le=5)
    guidance_level: int = Field(default=2, ge=0, le=3)


class SocraticParams(BaseModel):
    question_chain_depth: int = Field(default=4, ge=2, le=6)
    hint_level: int = Field(default=2, ge=0, le=3)


class TeachingSnippet(BaseModel):
    concept: Concept
    depth: int = Field(ge=0)
    estimated_minutes: int = Field(ge=1)
    teaching_method: str
    review_slot: bool = False


class TeachingPath(BaseModel):
    total_concepts: int = Field(ge=0)
    estimated_hours: float = Field(ge=0.0)
    snippets: list[TeachingSnippet]


TeachingActionType = Literal[
    "explain", "ask_question", "show_example", "give_exercise",
    "request_explanation", "provide_hint", "reveal_answer",
    "review", "checkpoint", "break_suggestion", "reflection",
    "show_counter_example", "pace_feedback",
]


class TeachingAction(BaseModel):
    type: TeachingActionType
    content: str
    estimated_duration_min: int = 5
    metadata: dict[str, Any] = Field(default_factory=dict)


class ErrorAnalysis(BaseModel):
    type: ErrorType | None = None
    root_concept: str | None = None
    surface_concept: str | None = None
    explanation: str | None = None
    remediation: str | None = None


class MasteryUpdate(BaseModel):
    concept_id: str
    new_mastery: float = Field(ge=0.0, le=1.0)
    change: float


class ResponseResult(BaseModel):
    correctness: Literal["correct", "partial", "incorrect"]
    feedback: str
    error_analysis: ErrorAnalysis | None = None
    mastery_update: MasteryUpdate | None = None
    next_action: TeachingAction | None = None


class InterruptResult(BaseModel):
    type: Literal["context_aware_answer", "prereq_tutorial", "pace_adjustment", "redirect"]
    content: str
    checkpoint_saved: bool = True
    resume_prompt: str | None = None
    suggested_action: Literal["resume", "explore_further", "change_topic"] = "resume"


# --- PGFGA 防火墙 + 增益回路 ---
class FirewallViolation(BaseModel):
    category: Literal[
        "negation", "judgment", "preachy", "topic_killer",
        "empty_praise", "topic_shift",
    ]
    matched_pattern: str
    suggested_fallback: str


class GainLoopBreak(BaseModel):
    type: Literal[
        "student_withdrawal", "emotional_flattening",
        "surface_responses", "avoidance_pattern",
    ]
    evidence: list[str] = Field(default_factory=list)
    repair_action_hint: str | None = None


# =========================================================================== #
# 7) L7 MCP Tool I/O
# =========================================================================== #


# --- knowledge-mcp ---
class AcquireSubjectInput(BaseModel):
    subject: str
    version: str | None = None
    sources: list[str] = Field(default_factory=lambda: ["textbook", "video", "web"])
    target_language: str = "zh"
    preserve_formulas: bool = True


class AcquireResult(BaseModel):
    corpus_id: str
    toc: list[dict[str, Any]] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactURI] = Field(default_factory=list)
    next_step_suggestion: str = "build_knowledge_graph"


class BuildKGResult(BaseModel):
    kg_id: str
    triples_count: int = Field(ge=0)
    quality_report: QualityReport
    mermaid: str | None = None
    gml_path: str | None = None


# --- tutoring-mcp ---
class SessionStartResult(BaseModel):
    session_id: str
    teaching_plan: dict[str, Any]
    current_action: TeachingAction
    pre_session_insight: str | None = None


# --- 冷启动摸底（adopted-fixes 修正 2）--- #

ColdStartBand = Literal["basic", "current", "abstract"]
SelfReport = Literal["sure", "unsure", "dont_know"]
StartingLevel = Literal["beginner", "intermediate", "advanced"]


class ColdStartProbe(BaseModel):
    """单道摸底题：探测学生对某个代表性概念的先验掌握。"""

    concept_id: str
    concept_name: str
    abstract_level: float = Field(ge=0.0, le=1.0)
    band: ColdStartBand
    question: str


class ColdStartProbeSet(BaseModel):
    """一组摸底题（默认 10 道，跨难度分布 3/4/3）。"""

    user_id: str
    subject_id: str
    kg_id: str
    probes: list[ColdStartProbe] = Field(default_factory=list)
    already_assessed: bool = False


class ColdStartAnswer(BaseModel):
    """学生对一道摸底题的作答 + 自评。"""

    concept_id: str
    answer: str = ""
    self_report: SelfReport = "unsure"


class ColdStartResult(BaseModel):
    """摸底结果：画像初值 + 已掌握概念的 BKT 先验种子。"""

    abstract_tolerance_initial: float = Field(ge=0.0, le=1.0)
    transfer_ability_initial: float = Field(ge=0.0, le=1.0)
    self_assessment_accuracy_initial: float = Field(ge=0.0, le=1.0)
    recommended_starting_level: StartingLevel
    probes_graded: int = Field(default=0, ge=0)
    mastery_priors: dict[str, float] = Field(default_factory=dict)
    seeded_mastered: list[str] = Field(default_factory=list)


# --- 多 Session 学习计划（P0 #3：跨天调度）--- #

PhaseStatus = Literal["done", "in_progress", "pending"]


class PhasePlan(BaseModel):
    """一个学习阶段（默认按顶层章节切分）。"""

    phase: int = Field(ge=1)
    title: str
    concept_ids: list[str] = Field(default_factory=list)
    estimated_hours: float = Field(ge=0.0)


class LearningPlan(BaseModel):
    """跨 Session 的持久化学习计划：把 KG 拓扑序切成若干 Phase。"""

    user_id: str
    subject_id: str
    kg_id: str
    phases: list[PhasePlan] = Field(default_factory=list)
    total_concepts: int = Field(ge=0)
    estimated_hours: float = Field(ge=0.0)
    created_at: datetime | None = None


class PhaseProgress(BaseModel):
    phase: int = Field(ge=1)
    title: str
    concepts_total: int = Field(ge=0)
    concepts_mastered: int = Field(ge=0)
    mastered_ratio: float = Field(ge=0.0, le=1.0)
    status: PhaseStatus


class LearningProgress(BaseModel):
    """跨 Session 进度报告：回答"我学到哪了 / 明天从哪继续"。"""

    user_id: str
    subject_id: str
    overall_mastery_ratio: float = Field(ge=0.0, le=1.0)
    concepts_total: int = Field(ge=0)
    concepts_mastered: int = Field(ge=0)
    current_phase: int | None = None
    current_phase_title: str | None = None
    next_concept_id: str | None = None
    next_concept_name: str | None = None
    phases: list[PhaseProgress] = Field(default_factory=list)
    completed: bool = False


class InsightReport(BaseModel):
    overall_mastery: float = Field(ge=0.0, le=1.0)
    concepts_mastered: int = Field(ge=0)
    concepts_learning: int = Field(ge=0)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[dict[str, Any]] = Field(default_factory=list)
    recommended_focus: list[str] = Field(default_factory=list)
    next_review_plan: dict[str, list[str]] = Field(default_factory=dict)


# --- digest-mcp（占位，本切片不实现）---
class DigestInput(BaseModel):
    corpus_id: str | None = None
    kg_id: str | None = None
    formats: list[str] = Field(default_factory=lambda: ["mindmap", "quiz"])
    grade: str = "college"
    learning_style: str | None = None


class DigestResult(BaseModel):
    artifacts: list[ArtifactURI] = Field(default_factory=list)


