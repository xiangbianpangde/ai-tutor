# 共享 Pydantic 模型

> 定义所有跨层数据类型 —— 开发工程师的"接口合同"  
> 文件位置：`ai-tutor/shared/schemas.py`

---

## 一、基础类型

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum, IntEnum


class SourceRef(BaseModel):
    """来源引用"""
    type: Literal["textbook", "video", "web", "lecture_note"]
    ref: str                          # "同济高数v8" / "BV1..."
    page: Optional[str] = None        # "P23-P24"
    timestamp: Optional[str] = None   # "02:15:30"
    text: Optional[str] = None        # 原文片段
    url: Optional[str] = None


class ArtifactURI(BaseModel):
    """产物文件引用"""
    uri: str                          # "artifact://session-abc/output/quiz.html"
    mime_type: str                    # "text/html", "application/pdf"
    size_bytes: int
    expires_at: Optional[datetime] = None


class Example(BaseModel):
    text: str
    type: Literal["proof", "computation", "application", "counterexample", "pathological"]
    difficulty: Optional[float] = None  # 0~1
```

---

## 二、L4 知识工程模型

```python
# === 概念节点 ===
class ConceptClassification(BaseModel):
    bloom_level: Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
    abstract_level: float = Field(ge=0.0, le=1.0)
    domain: str                       # "高等数学/极限论"
    cross_domain_tags: List[str] = []


class ConceptDifficulty(BaseModel):
    prereq_count: int
    prereq_max_depth: int
    formula_density: float = Field(ge=0.0, le=1.0)
    coupling: float = Field(ge=0.0, le=1.0)
    cognitive_load_estimate: float = Field(ge=0.0, le=1.0)
    typical_learning_time_min: int = Field(ge=1, le=120)


CONCEPT_ID_PATTERN = r"^[a-z0-9][a-z0-9\-]*:\d+(?:\.\d+)*:[a-z0-9][a-z0-9_]*$"


class Concept(BaseModel):
    id: str = Field(pattern=CONCEPT_ID_PATTERN)  # "gaoshu-v8:2.1.1:limit_epsilon_delta"
    names: List[str]
    category: Literal["definition", "theorem", "formula", "method",
                       "property", "axiom", "lemma", "corollary"]
    definition: str
    informal_description: str
    attributes: Dict[str, Any] = {}
    classification: ConceptClassification
    difficulty: ConceptDifficulty
    examples: List[Example] = []
    counter_examples: List[Example] = []
    common_misconceptions: List[str] = []
    keywords: List[str] = []
    embedding: Optional[List[float]] = None    # 768-dim
    sources: List[SourceRef]
    confidence: float = Field(ge=0.0, le=1.0)


# === 12 种语义关系 ===
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
    sources: List[SourceRef]
    confidence: float = Field(ge=0.0, le=1.0)
    deprecated: bool = False


# === 知识图谱 ===
class QualityReport(BaseModel):
    overall: Literal["pass", "fail", "pass_with_warnings"]
    chapter_coverage: float
    isolated_nodes: int
    cycles: int
    avg_confidence: float
    warnings: List[str] = []
    suggestions: List[str] = []


class KnowledgeGraph(BaseModel):
    kg_id: str
    subject_id: str
    version: str
    created_at: datetime
    source_corpora: List[str]
    node_count: int
    edge_count: int
    quality_report: QualityReport
    nodes: Dict[str, Concept]
    edges: List[Relation]
    file_paths: Dict[str, str] = {}


# === 语料库 ===
class CorpusSource(BaseModel):
    type: Literal["textbook", "video_transcript", "web"]
    format: str                       # "pdf", "md", "mp3"
    original_file: Optional[str] = None
    converted_file: Optional[str] = None
    pages: Optional[int] = None
    duration_min: Optional[int] = None
    language: str = "zh"
    parser: Optional[str] = None
    parser_version: Optional[str] = None


class CorpusManifest(BaseModel):
    corpus_id: str
    subject: str
    version: str
    created_at: datetime
    sources: List[CorpusSource]
    total_chapters: int
    total_sections: int
    estimated_concepts: int
    file_paths: Dict[str, str]
```

---

## 三、L5 学习者建模模型

```python
# === 知识追踪 ===
class BKTParams(BaseModel):
    concept_id: str
    p_learn: float = Field(ge=0.0, le=1.0, default=0.15)
    p_guess: float = Field(ge=0.0, le=1.0, default=0.12)
    p_slip: float = Field(ge=0.0, le=1.0, default=0.08)
    p_init: float = Field(ge=0.0, le=1.0, default=0.05)
    p_mastery: float = Field(ge=0.0, le=1.0, default=0.05)
    last_updated: Optional[datetime] = None
    n_observations: int = 0


class DKTOutput(BaseModel):
    concept_id: str
    mastery_prob: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    predicted_correctness: float = Field(ge=0.0, le=1.0)
    next_review_at: Optional[datetime] = None
    predicted_error_type: Optional[str] = None


# === 错误诊断 ===
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
    evidence: List[str] = []
    remediation_suggestion: str


# === 知识状态快照 ===
class ConceptMastery(BaseModel):
    bkt_mastery: float = Field(ge=0.0, le=1.0)
    dkt_mastery: Optional[float] = Field(ge=0.0, le=1.0, default=None)
    n_correct: int = 0
    n_incorrect: int = 0
    last_error_type: Optional[str] = None
    last_interaction_at: Optional[datetime] = None
    forgetting_rate_lambda: Optional[float] = None
    review_streak: int = 0


class KnowledgeSnapshot(BaseModel):
    user_id: str
    subject_id: str
    timestamp: datetime
    concepts: Dict[str, ConceptMastery]
    total_concepts: int
    mastered_count: int                 # mastery > 0.85
    learning_count: int                 # 0.4 < mastery < 0.85
    unknown_count: int                  # mastery < 0.4
    avg_mastery: float


# === 学习者画像 ===
class CognitiveProfile(BaseModel):
    working_memory_span: int = Field(ge=2, le=9, default=5)
    abstract_tolerance: float = Field(ge=0.0, le=1.0, default=0.5)
    transfer_ability: float = Field(ge=0.0, le=1.0, default=0.4)
    analogical_reasoning: float = Field(ge=0.0, le=1.0, default=0.5)
    mathematical_maturity: float = Field(ge=0.0, le=1.0, default=0.4)
    preferred_modality: Dict[str, float] = Field(
        default_factory=lambda: {"text": 0.4, "visual": 0.3, "interactive": 0.2, "audio": 0.1}
    )
    information_processing_speed: float = 1.0


class MetacognitiveProfile(BaseModel):
    self_assessment_accuracy: float = Field(ge=0.0, le=1.0, default=0.6)
    help_seeking_tendency: float = Field(ge=0.0, le=1.0, default=0.5)
    frustration_threshold: int = Field(ge=1, le=10, default=3)
    confidence_calibration: float = Field(ge=-1.0, le=1.0, default=0.0)
    growth_mindset_score: float = Field(ge=0.0, le=1.0, default=0.6)


class BehavioralProfile(BaseModel):
    peak_learning_hours: List[int] = []
    optimal_session_length_min: int = 45
    attention_decay_rate: float = 0.02
    streak_momentum: float = Field(ge=0.0, le=1.0, default=0.5)
    review_compliance_rate: float = Field(ge=0.0, le=1.0, default=0.5)
    preferred_pace: Literal["fast", "moderate", "thorough"] = "moderate"


class LearnerProfile(BaseModel):
    user_id: str
    version: int = 1
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    total_study_hours: float = 0.0
    cognitive: CognitiveProfile = Field(default_factory=CognitiveProfile)
    metacognitive: MetacognitiveProfile = Field(default_factory=MetacognitiveProfile)
    behavioral: BehavioralProfile = Field(default_factory=BehavioralProfile)
    weakest_domains: List[str] = []
    strongest_domains: List[str] = []
    total_concepts_mastered: int = 0


# === PGFGA 心流追踪（详见 specs/pgfga-integration.md §二）===
class FlowLevel(IntEnum):
    SILENT = 0      # 静默：答得慢、犹豫、频繁求助
    SHALLOW = 1     # 浅层：开始尝试但表面
    FLUENT = 2      # 流畅：答题连贯，主动推进
    DEEP = 3        # 深入：主动串联概念，举一反三
    IMMERSED = 4    # 沉浸：完全专注，自驱表达


class FlowSignals(BaseModel):
    # 增长信号
    answer_length_growth: bool = False
    depth_increasing: bool = False
    initiative_taking: bool = False
    hesitation_decreasing: bool = False
    inter_turn_speed_up: bool = False
    self_correction_quality: bool = False
    # 衰减信号
    withdrawal_pattern: bool = False
    help_seeking_spike: bool = False
    answer_regression: bool = False
    emotional_flatness: bool = False


# === 教学上下文（L5→L6 接口）===
class TeachingContext(BaseModel):
    current_focus_concept_id: str
    position_in_plan: int
    estimated_time_remaining_min: int
    mastery_map: Dict[str, float]
    cognitive_load: float = Field(ge=0.0, le=1.0)
    error_history: List[ErrorDiagnosis] = []
    learner_profile: LearnerProfile
    weak_points: List[str] = []
```

---

## 四、L3 长期记忆模型

```python
class ForgettingCurve(BaseModel):
    user_id: str
    concept_id: str
    lambda_param: float                  # 衰减速率
    r_squared: Optional[float] = None
    n_data_points: int = 0
    last_review_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    review_streak: int = 0


class ReviewRecord(BaseModel):
    user_id: str
    concept_id: str
    subject_id: str
    review_date: datetime
    days_since_last: int
    accuracy: float
    review_mode: str
    error_types: Optional[List[str]] = None
    session_id: Optional[str] = None


class DailyReviewSection(BaseModel):
    concept_id: str
    priority: float
    predicted_recall: float
    estimated_minutes: int
    review_mode: Literal["quick_quiz", "concept_map", "teach_back", "error_revisit"]
    urgency_context: str                # "3天前复习，预测正确率76%"


class DailyReviewPlan(BaseModel):
    user_id: str
    subject_id: str
    date: str                           # "2026-05-20"
    sections: List[DailyReviewSection]
    total_estimated_min: int
    tips: List[str]
```

---

## 五、L2 短期记忆模型

```python
class FocusState(BaseModel):
    primary_concept: str
    supporting_concepts: List[str] = []
    last_action_type: Optional[str] = None
    expected_next_action: Optional[str] = None


class InterruptCheckpoint(BaseModel):
    saved_at: datetime
    current_concept_id: str
    position_in_plan: int
    strategy: str
    strategy_state: str
    focus: FocusState
    pending_action: Optional[Dict[str, Any]] = None
    pending_question: Optional[str] = None
    context_tail: List[Dict[str, Any]] = []    # 最近3轮
    cognitive_load_at_save: float


class SessionMeta(BaseModel):
    started_at: datetime
    total_elapsed_min: float = 0.0
    active_time_min: float = 0.0
    interrupt_count: int = 0
    checkpoint_count: int = 0
    current_cognitive_load: float = 0.0


class SessionStats(BaseModel):
    concepts_covered: List[str] = []
    concepts_mastered: List[str] = []
    total_questions_asked: int = 0
    correct_rate: float = 0.0
    errors_by_type: Dict[str, int] = {}


class SessionContext(BaseModel):
    session_id: str
    user_id: str
    subject_id: str
    status: Literal["idle", "active", "interrupted", "completed", "expired"] = "idle"
    teaching_plan_id: Optional[str] = None
    current_concept_id: Optional[str] = None
    position_in_plan: int = 0
    current_strategy: Optional[str] = None
    current_strategy_state: Optional[str] = None
    interrupt_checkpoint: Optional[InterruptCheckpoint] = None
    recent_history: List[Dict[str, Any]] = []
    focus: FocusState = Field(default_factory=FocusState)
    meta: SessionMeta
    session_stats: SessionStats = Field(default_factory=SessionStats)
```

---

## 六、L6 教学引擎模型

```python
# === 教学策略参数 ===
class ReductionOfOrderParams(BaseModel):
    topology: Literal["bottom_up", "top_down"] = "bottom_up"
    skip_threshold: float = 0.85
    max_concepts_per_session: int = 8
    review_interleave_ratio: float = 0.25


class FeynmanParams(BaseModel):
    fidelity_threshold: float = 0.80
    max_attempts: int = Field(ge=1, le=5, default=3)
    guidance_level: int = Field(ge=0, le=3, default=2)


class SocraticParams(BaseModel):
    question_chain_depth: int = Field(ge=2, le=6, default=4)
    hint_level: int = Field(ge=0, le=3, default=2)


class TeachingSnippet(BaseModel):
    concept: Concept
    depth: int
    estimated_minutes: int
    teaching_method: str
    review_slot: bool = False


class TeachingPath(BaseModel):
    total_concepts: int
    estimated_hours: float
    snippets: List[TeachingSnippet]


# === 教学动作 ===
class TeachingAction(BaseModel):
    type: Literal[
        "explain", "ask_question", "show_example", "give_exercise",
        "request_explanation", "provide_hint", "reveal_answer",
        "review", "checkpoint", "break_suggestion", "reflection",
    ]
    content: str
    estimated_duration_min: int = 5
    metadata: Dict[str, Any] = {}


# === 学生响应分析 ===
class ErrorAnalysis(BaseModel):
    type: Optional[ErrorType] = None
    root_concept: Optional[str] = None
    surface_concept: Optional[str] = None
    explanation: Optional[str] = None
    remediation: Optional[str] = None


class MasteryUpdate(BaseModel):
    concept_id: str
    new_mastery: float = Field(ge=0.0, le=1.0)
    change: float


class ResponseResult(BaseModel):
    correctness: Literal["correct", "partial", "incorrect"]
    feedback: str
    error_analysis: Optional[ErrorAnalysis] = None
    mastery_update: Optional[MasteryUpdate] = None
    next_action: Optional[TeachingAction] = None


# === PGFGA 非评判防火墙 + 增益回路（详见 pgfga-integration.md §三、§五）===
class FirewallViolation(BaseModel):
    category: Literal[
        "negation", "judgment", "preachy", "topic_killer",
        "empty_praise", "topic_shift",
    ]
    matched_pattern: str
    suggested_fallback: str


class GainLoopBreakType(BaseModel):
    type: Literal[
        "student_withdrawal", "emotional_flattening",
        "surface_responses", "avoidance_pattern",
    ]
    evidence: List[str] = []
    repair_action_hint: Optional[str] = None


# === 中断 ===
class InterruptResult(BaseModel):
    type: Literal["context_aware_answer", "prereq_tutorial",
                   "pace_adjustment", "redirect"]
    content: str
    checkpoint_saved: bool = True
    resume_prompt: Optional[str] = None
    suggested_action: Literal["resume", "explore_further", "change_topic"] = "resume"
```

---

## 七、L7 MCP Tool 输入/输出模型

```python
# === knowledge-mcp ===
class AcquireSubjectInput(BaseModel):
    subject: str
    version: Optional[str] = None
    sources: List[str] = ["textbook", "video", "web"]
    target_language: str = "zh"
    preserve_formulas: bool = True


class AcquireResult(BaseModel):
    corpus_id: str
    toc: List[Dict[str, Any]]
    stats: Dict[str, Any]
    artifacts: List[ArtifactURI]
    next_step_suggestion: str = "build_knowledge_graph"


class BuildKGResult(BaseModel):
    kg_id: str
    triples_count: int
    quality_report: QualityReport
    mermaid: Optional[str] = None
    gml_path: Optional[str] = None


# === KG 人工确认（adopted-fixes 修正 1）===
class KgEditAction(BaseModel):
    op: Literal[
        "edit_definition", "add_edge", "remove_edge",
        "delete_concept", "merge_concepts", "approve_all",
    ]
    concept_id: Optional[str] = None
    new_definition: Optional[str] = None
    edge: Optional[Relation] = None        # for add_edge / remove_edge
    merge_target_id: Optional[str] = None  # for merge_concepts
    note: Optional[str] = None


class LowConfidenceConcept(BaseModel):
    concept_id: str
    name: str
    confidence: float
    definition_preview: str


class ReviewKGResult(BaseModel):
    kg_id: str
    mode: Literal["quick", "full"]
    low_confidence_concepts: List[LowConfidenceConcept]
    warnings: List[str] = []
    suggestions: List[str] = []
    mermaid_thumb: Optional[str] = None
    full_mermaid: Optional[str] = None
    suggested_actions: List[KgEditAction] = []


class KgUpdateFailure(BaseModel):
    action_index: int
    reason: str


class KgUpdateResult(BaseModel):
    kg_id: str
    new_version: str
    applied: int
    failed: List[KgUpdateFailure] = []
    new_quality_report: QualityReport


# === tutoring-mcp ===
class SessionStartResult(BaseModel):
    session_id: str
    teaching_plan: Dict[str, Any]       # phases + total
    current_action: TeachingAction
    pre_session_insight: Optional[str] = None


class InsightReport(BaseModel):
    overall_mastery: float
    concepts_mastered: int
    concepts_learning: int
    strengths: List[str]
    weaknesses: List[Dict[str, Any]]
    recommended_focus: List[str]
    next_review_plan: Dict[str, List[str]]


# === digest-mcp ===
class DigestInput(BaseModel):
    corpus_id: Optional[str] = None
    kg_id: Optional[str] = None
    formats: List[str] = ["mindmap", "quiz"]
    grade: str = "college"
    learning_style: Optional[str] = None


class DigestResult(BaseModel):
    artifacts: List[ArtifactURI]
```

---

## 八、统一错误模型

```python
class TutorErrorDetail(BaseModel):
    code: str
    message: str
    hint: Optional[str] = None
    retryable: bool = False
    details: Optional[Dict[str, Any]] = None


# 预定义错误码常量
ERROR_CODES: Dict[str, str] = {
    "PLUGIN_NOT_AVAILABLE": "插件不可用，请检查配置",
    "DEPENDENCY_MISSING": "缺少依赖",
    "CORPUS_NOT_FOUND": "语料库不存在",
    "KG_NOT_BUILT": "请先构建知识图谱",
    "SESSION_EXPIRED": "会话已过期",
    "COGNITIVE_OVERLOAD": "检测到认知过载，建议休息",
    "RATE_LIMITED": "请求频率过高",
    "AUTH_REQUIRED": "需要认证",
    "GPU_NOT_AVAILABLE": "未检测到GPU，将以CPU模式运行",
}
```

---

## 九、schemas.py 文件结构（给开发工程师）

```python
# ai-tutor/shared/schemas.py
#
# 导入顺序（避免循环引用）:
# 1. 基础类型 (SourceRef, ArtifactURI, Example)
# 2. L4 知识工程 (Concept, Relation, KnowledgeGraph, ...)
# 3. L5 学习者建模 (BKTParams, ErrorDiagnosis, LearnerProfile, ...)
# 4. L3 长期记忆 (ForgettingCurve, DailyReviewPlan, ...)
# 5. L2 短期记忆 (SessionContext, ...)
# 6. L6 教学引擎 (TeachingAction, ResponseResult, ...)
# 7. L7 MCP Tool I/O (AcquireResult, SessionStartResult, ...)
# 8. 错误模型 (TutorErrorDetail, ERROR_CODES)

# Pydantic 配置:
# class Config:
#     extra = "forbid"        # 拒绝未定义字段
#     validate_assignment = True
#     use_enum_values = True
```

---

## 十、模型校验规则汇总

| 模型 | 关键约束 |
|------|---------|
| Concept.id | 格式 `{subject}:{chapter}.{section}.{index}:{slug}` |
| Concept.confidence | ≥ 0.0, ≤ 1.0 |
| Relation | from_id ≠ to_id（不可自环） |
| BKTParams | 所有概率 ≥ 0.0, ≤ 1.0 |
| SessionContext.status | 必须遵循状态机转换规则 |
| TeachingAction.type | 仅限枚举值 |
| ResponseResult.correctness | 仅限 "correct"/"partial"/"incorrect" |
