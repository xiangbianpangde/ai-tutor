# Server API 规格

> 每个 MCP server 的完整 Tool/Prompt/Resource 签名 —— 开发工程师的接口合同  
> 所有返回类型定义见 shared-schemas.md

---

## 一、knowledge-mcp

### Tools

#### 1. acquire_subject

```
输入:
  subject: str                       # 科目名称
  version: Optional[str] = None      # 教材版本
  sources: List[str] = ["textbook", "video", "web"]
  target_language: str = "zh"
  preserve_formulas: bool = True

返回: AcquireResult
  {
    corpus_id: str,
    toc: List[Dict],                 # [{chapter: 1, title: "...", sections: [...]}]
    stats: {
      total_chapters: int,
      total_concepts_detected: int,
      sources_used: List[str],
      estimated_quality: float,
    },
    artifacts: List[ArtifactURI],
    next_step_suggestion: str,
  }

内部编排:
  ① fetch_textbook → 返回链接列表 → 等待用户选择 → 下载
  ② pdf_to_markdown → Docker容器 (auto选provider)
  ③ transcribe_video → yt-dlp + whisper (并行)
  ④ web_collect → DuckDuckGo/Tavily
  ⑤ normalize_corpus → 去重 + 章节对齐

需等待用户输入的环节:
  - 教材链接选择 → 通过 MCP Tool 返回链接列表, 用户选后再次调用
    (或: 在 Tool 内部通过 stdin 交互; 取决于 MCP host 能力)

超时策略:
  - pdf_to_markdown: 单页 30s, 总超时 60min
  - transcribe_video: 音频时长 × 1.5
  - web_collect: 单页 15s

需实现为长运行 Tool (返回 streaming progress):
  pdf_to_markdown, transcribe_video
```

#### 2. build_knowledge_graph

```
输入:
  corpus_id: str
  depth: Literal["toc", "concept", "full"] = "full"

返回: BuildKGResult
  {
    kg_id: str,
    triples_count: int,
    quality_report: QualityReport,
    mermaid: Optional[str],           # Mermaid文本
    gml_path: Optional[str],          # GML文件 artifact:// URI
  }

depth模式:
  toc:     纯规则（章节→概念骨架），~5min，零LLM调用
  concept: toc + LLM抽取概念 + 关系，需要 LLM API key
  full:    concept + 难度评分 + embedding索引，完整流程

LLM调用:
  depth=toc: 0次
  depth=concept: ~N次 (N=章节数，每章1次概念抽取调用)
  depth=full: ~N + M次 (M=关系数/批次大小，每批20个关系1次调用)

进度上报:
  返回 streaming progress: {"stage": "passage_split", "progress": 0.3}
```

#### 3. query_knowledge

```
输入:
  kg_id: str
  query: str
  query_type: Literal["concept", "path", "neighbors", "subgraph"] = "concept"
  depth: int = 2
  max_results: int = 10

返回:
  根据 query_type:

  concept:
    [{concept_id, name, definition_preview, abstract_level, mastery_prereqs}]
  
  path:
    {from, to, path: [{concept_id, relation_type}], length, alternatives}
  
  neighbors:
    {concept_id, upstream: [...], downstream: [...], analogous: [...]}
  
  subgraph:
    {nodes: [...], edges: [...], mermaid: str}
```

#### 4. review_kg

```
输入:
  kg_id: str
  mode: Literal["quick", "full"] = "quick"

返回: ReviewKGResult
  {
    kg_id: str,
    mode: str,
    low_confidence_concepts: List[{concept_id, name, confidence, definition_preview}],
    warnings: List[str],                # 来自 QualityReport
    suggestions: List[str],
    mermaid_thumb: Optional[str],       # 缩略图（quick）
    full_mermaid: Optional[str],        # 完整图（full）
    suggested_actions: List[KgEditAction],
  }

内部:
  quick: 取置信度最低的 20 个概念 + Quality Gate warnings + Mermaid 缩略图
  full:  全量返回，配合 update_kg 交互编辑

放在 build_knowledge_graph 与 start_learning_session 之间的人工确认节点。
```

#### 5. update_kg

```
输入:
  kg_id: str
  actions: List[KgEditAction]

返回: KgUpdateResult
  {
    kg_id: str,
    new_version: str,
    applied: int,
    failed: List[{action_index, reason}],
    new_quality_report: QualityReport,
  }

KgEditAction.op ∈ {
  "edit_definition", "add_edge", "remove_edge",
  "delete_concept", "merge_concepts", "approve_all",
}

写入时新建 KG 版本（不修改原 kg_id），便于回滚。
```

#### 6. resolve_conflicts

```
输入:
  kg_id: str

返回: List[{
  type: "contradictory_definition" | "reversed_prerequisite" | ...
  concept_a: str,
  concept_b: str,
  source_a: SourceRef,
  source_b: SourceRef,
  description: str,
  suggested_resolution: str,
}]
```

### Prompts

```
acquisition_strategy:
  模板: "请分析科目'{subject}'，推荐最佳的知识获取策略..."
  用途: 在 acquire_subject 前规划数据源

kg_quality_review:
  模板: "请审查以下知识图谱的质量报告：{quality_report}..."
  用途: Quality Gate 不通过时，辅助分析
```

### Resources

```
kb://corpora/{corpus_id}
  → CorpusManifest JSON

kb://corpora/{corpus_id}/toc
  → 目录结构 JSON

kb://kgs/{kg_id}/concepts?page=1&page_size=50
  → 分页概念列表

kb://kgs/{kg_id}/mermaid
  → Mermaid 可视化文本
```

---

## 二、tutoring-mcp

### Tools

#### 1. start_learning_session

```
输入:
  user_id: str
  subject_id: str
  goal: Literal["48h_sprint", "semester_study", "exam_review", "quick_overview"]
  available_hours: Optional[int] = None

返回: SessionStartResult
  {
    session_id: str,
    teaching_plan: {
      phases: [{phase, concepts, estimated_hours}],
      total_concepts: int,
      estimated_hours: float,
    },
    current_action: TeachingAction,
    pre_session_insight: Optional[str],
  }

内部:
  ① 校验 subject_id 有对应的 KG
  ② 加载 L5 知识状态 (如果是新科目 → cold-start)
  ③ L6 构建教学路径
  ④ L3 插入复习节点
  ⑤ 创建 L2 会话上下文
  ⑥ 返回首步 TeachingAction
```

#### 2. next_action

```
输入:
  session_id: str

返回: TeachingAction
  {type, content, estimated_duration_min, metadata}

内部:
  ① 加载 L2 会话上下文
  ② 获取 L5 最新教学上下文
  ③ 获取 L3 复习建议
  ④ L6 决策循环 → 选择策略 → 生成下一步动作
  ⑤ 更新 L2 状态

注意: 此 Tool 可能返回 checkpoint 或 break_suggestion 类型
```

#### 3. respond

```
输入:
  session_id: str
  answer: str                         # 学生的回答文本

返回: ResponseResult
  {
    correctness: "correct" | "partial" | "incorrect",
    feedback: str,
    error_analysis: Optional[ErrorAnalysis],
    mastery_update: Optional[MasteryUpdate],
    next_action: Optional[TeachingAction],
  }

内部 (即使正确也要执行):
  ① L5 分析回答 → correctness + error_analysis
  ② L5 tracer.update() → 更新 BKT p_mastery
  ③ L3 record_interaction() → 记录答题
  ④ L6 决定下一步
```

#### 4. interrupt

```
输入:
  session_id: str
  question: str

返回: InterruptResult
  {
    type: "context_aware_answer" | "prereq_tutorial" | "pace_adjustment" | "redirect",
    content: str,
    checkpoint_saved: bool,
    resume_prompt: Optional[str],
    suggested_action: "resume" | "explore_further" | "change_topic",
  }

内部:
  ① L2 save_checkpoint()
  ② L6 分类意图
  ③ 对应处理:
     concept_question → 查 KG → 上下文感知回答
     prereq_gap → 检测是否真缺失 → mini复习
     pace_complaint → 降速/建议休息
     distraction → 温和重导向
     cognitive_overload → 建议休息
  ④ 返回结果 + resume_prompt
```

#### 5. checkpoint

```
输入:
  session_id: str
  kind: Literal["self_summary", "test_result"] = "self_summary"
  content: Optional[str] = None        # 学生的总结文本

返回:
  {
    self_assessment_accuracy: float,   # 自评 vs 系统评
    current_mastery_map: Dict[str, float],
    cognitive_load: float,
    suggestions: List[str],
  }
```

#### 6. learning_insight

```
输入:
  user_id: str
  subject_id: str

返回: InsightReport
  {
    overall_mastery: float,
    concepts_mastered: int,
    strengths: List[str],
    weaknesses: List[{concept, mastery, root_cause}],
    recommended_focus: List[str],
    next_review_plan: Dict[str, List[str]],
  }
```

#### 7. generate_review_plan

```
输入:
  user_id: str
  subject_id: str
  available_time_today_min: int = 60

返回: DailyReviewPlan
  {
    user_id, subject_id, date,
    sections: [DailyReviewSection, ...],
    total_estimated_min: int,
    tips: List[str],
  }
```

### Prompts

```
tutoring_session_start:
  模板: "你正在开始{goal}学习{subject}。你的教学计划是..."
  用途: 给 host LLM 的上下文注入

design_exercise:
  模板: "为概念'{concept}'设计{count}道练习题..."
  用途: 生成不在 KG 中的定制题目

diagnose_error:
  模板: "学生作答'{answer}'，正确答案是'{correct}'。分析错误原因..."
  用途: 辅助 L5 错误诊断 (fallback)
```

### Resources

```
tutor://sessions/{session_id}/status
  → {status, current_concept, progress_pct, elapsed_min}

tutor://sessions/{session_id}/history?page=1
  → 分页对话历史

tutor://users/{user_id}/profile
  → LearnerProfile 摘要
```

---

## 三、digest-mcp

### Tools

#### 1. digest

```
输入: DigestInput
  {
    corpus_id: Optional[str],
    kg_id: Optional[str],
    formats: List[str] = ["mindmap", "quiz"],
    grade: str = "college",
    learning_style: Optional[str],
  }

返回: DigestResult
  {artifacts: List[ArtifactURI]}

内部编排顺序:
  ① mindmap → mermaid-cli → PNG
  ② notes → reportlab → 手写风格PDF
  ③ slides → python-pptx + img2pdf
  ④ quiz → quiz-template.html 模板渲染
  ⑤ audio → edge-tts → MP3
  ⑥ simulation → HTML(零依赖)
  ⑦ multi-agent → Markdown 脚本文件集合

formats为空 → 默认 ["mindmap", "quiz"]
```

#### 2. build_quiz_html

```
输入:
  quiz_data: Union[str, dict]         # JSON题目 或 kg_id
  count: int = 10
  difficulty_mix: Tuple[float, float, float] = (0.3, 0.5, 0.2)

返回: ArtifactURI  (指向 quiz.html)

内部:
  - 如果是 kg_id: 从 KG 提取概念 → 生成题目 → 套模板
  - 如果是 JSON: 直接套模板
  - 模板: assets/quiz-template.html
```

#### 3. compile_slides

```
输入:
  images: List[str]                    # 图片路径或URL
  notes: Optional[List[str]] = None
  output_format: Literal["pdf", "pptx", "both"] = "both"

返回: List[ArtifactURI]
```

### Resources

```
digest://templates/quiz
  → quiz-template.html 源文件

digest://references/{format}
  → references/format-{format}.md
  (format ∈ notes|quiz|slides|mindmap|audio|simulation|multi-agent)
```

---

## 四、sync-mcp

### Tools

#### 1. init_subject_repo

```
输入:
  user_id: str
  subject_id: str
  github_org: str = "my-ai-learning"

返回: {repo_url, clone_path}

仓库命名: {github_org}/{user_id}-{subject_slug}
```

#### 2. push_artifacts

```
输入:
  subject_id: str
  artifacts: List[str]                # artifact:// URI 列表
  commit_message: str

返回: {commit_sha, repo_url, files_pushed}
```

#### 3. pull_homework_from_obsidian

```
输入:
  vault_path: str                     # Obsidian vault 的本地绝对路径
  subject_id: str

返回: [{filename, content, modified_at}]

实现: 递归扫描 vault_path 中匹配 subject_id 的 .md 文件
```

#### 4. watch_obsidian (长运行 Tool)

```
输入:
  vault_path: str
  subject_id: str
  poll_interval_sec: int = 30

返回: streaming (通过 MCP notifications/progress)
  每次文件变更推送: {event: "created"|"modified"|"deleted", filename, timestamp}

实现: watchdog 库监听文件变更
超时: 无（持续运行直到 MCP host 断开）
```

---

## 五、所有 Server 的通用 Health Check

```
每个 server 暴露:
  GET /health  (HTTP模式)
  
返回:
  {
    "ok": true,
    "server": "knowledge-mcp",
    "version": "0.1.0",
    "plugins_loaded": {
      "pdf_parse": {"provider": "pdf2zh", "status": "healthy"},
      "transcription": {"provider": "faster_whisper", "status": "healthy"},
      "llm": {"provider": "deepseek", "status": "healthy"},
    },
    "deps_present": ["redis", "sqlalchemy", "fastmcp"],
  }
```

---

## 六、Tool 实现模板（给开发工程师）

```python
# servers/knowledge_mcp/server.py

from fastmcp import FastMCP

mcp = FastMCP("knowledge-mcp")

@mcp.tool()
async def acquire_subject(
    subject: str,
    version: str | None = None,
    sources: list[str] = ["textbook", "video", "web"],
    target_language: str = "zh",
    preserve_formulas: bool = True,
) -> AcquireResult:
    """
    [文档字符串: 功能说明 + 内部步骤]
    """
    # 实现
    ...

@mcp.tool()
async def build_knowledge_graph(
    corpus_id: str,
    depth: Literal["toc", "concept", "full"] = "full",
) -> BuildKGResult:
    ...

@mcp.tool()
async def query_knowledge(
    kg_id: str,
    query: str,
    query_type: Literal["concept", "path", "neighbors", "subgraph"] = "concept",
    depth: int = 2,
    max_results: int = 10,
) -> dict:
    ...

@mcp.tool()
async def resolve_conflicts(kg_id: str) -> list[dict]:
    ...

# === Prompts ===
@mcp.prompt()
def acquisition_strategy(subject: str) -> str:
    return f"请分析科目'{subject}'，推荐最佳的知识获取策略..."

@mcp.prompt()
def kg_quality_review(quality_report: dict) -> str:
    return f"请审查以下知识图谱的质量报告：{quality_report}..."

# === Resources ===
@mcp.resource("kb://corpora/{corpus_id}")
async def get_corpus(corpus_id: str) -> str:
    ...

@mcp.resource("kb://kgs/{kg_id}/mermaid")
async def get_kg_mermaid(kg_id: str) -> str:
    ...

# === Transport ===
def main():
    import sys
    transport = "stdio" if "--transport" not in sys.argv else sys.argv[sys.argv.index("--transport") + 1]
    if transport == "http":
        mcp.run(transport="sse", host="0.0.0.0", port=8001)
    else:
        mcp.run(transport="stdio")
```
