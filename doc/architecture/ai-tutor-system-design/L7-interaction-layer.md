# L7 交互层

> 职责：将 L6 的决策转化为面向学生的自然交互；将学生输入转化为结构化数据反馈 L5/L6  
> 实现：MCP Tool 签名 + 多模态对话 + 随时打断机制 + 进度可视化

---

## 1. MCP Server 重新分组

原设计 6 个 server。重设计后合并为 4 个 MCP server：

| Server | 对应层 | 职责 |
|--------|--------|------|
| `knowledge-mcp` | L4 + L1 插件 | 知识采集、抽取、KG 构建、查询 |
| `tutoring-mcp` | L2 + L5 + L6 + L3 | 教学会话全生命周期（启动/推进/响应/中断/复习） |
| `digest-mcp` | (原 knowledge-digest) | 可视化课件生成（7 种格式） |
| `sync-mcp` | (原 sync-mcp) | GitHub + Obsidian 同步 |

---

## 2. Tool 签名

### 2.1 knowledge-mcp

```python
# === Tools ===

def acquire_subject(
    subject: str,
    version: Optional[str] = None,
    sources: List[str] = ["textbook", "video", "web"],
    target_language: str = "zh",
    preserve_formulas: bool = True,
) -> AcquireResult:
    """
    一条命令完成: 检索教材 → 用户选源 → PDF→MD → 视频转录 → 
                  网页采集 → 多源去重 → 统一格式化 → 语料库

    内部编排:
    1. fetch_textbook → 返回链接列表，用户选择后下载
    2. pdf_to_markdown → Docker pdf2zh 容器
    3. transcribe_video → yt-dlp + whisper + LLM摘要
    4. web_collect → Tavily/Serper/DuckDuckGo
    5. normalize_corpus → 去重 + 章节对齐 + 统一格式

    返回:
    {
        "corpus_id": "gaoshu-v8-yhn-20260519",
        "toc": [...],                  # 目录结构
        "stats": {
            "total_chapters": 12,
            "total_concepts_detected": 847,
            "sources_used": ["textbook", "video_x2"],
            "estimated_quality": 0.87,
        },
        "artifacts": [
            {"uri": "artifact://.../raw/gaoshu_v8.pdf", "type": "pdf"},
            {"uri": "artifact://.../md/chapter_01.md", "type": "markdown"},
            ...
        ],
        "next_step_suggestion": "build_knowledge_graph",
    }
    """

def build_knowledge_graph(
    corpus_id: str,
    depth: Literal["toc", "concept", "full"] = "full",
) -> BuildKGResult:
    """
    从语料库构建知识图谱。
    
    depth=toc: 仅按目录结构生成骨架 KG
    depth=concept: 语义抽取 + 关系抽取（需要 LLM）
    depth=full: 概念抽取 + 关系 + 难度评分 + embedding（完整流程）
    
    返回:
    {
        "kg_id": "gaoshu-v8-kg-v1",
        "triples_count": 3247,
        "quality_report": {
            "isolated_nodes": 3,
            "cycles": 1,
            "chapter_coverage": 0.92,
            "overall": "pass",
            "warnings": ["2个概念缺少示例", "1个依赖循环(已标记)"],
        },
        "visual_export": {
            "mermaid": "graph TD\n...",
            "gml_path": "artifact://.../graph.gml",
        },
    }
    """

def query_knowledge(
    kg_id: str,
    query: str,
    query_type: Literal["concept", "path", "neighbors", "subgraph"] = "concept",
    depth: int = 2,
    max_results: int = 10,
) -> QueryKGResult:
    """
    统一的知识图谱查询接口。
    
    query_type=concept: 按关键词搜索概念
    query_type=path: 查找两个概念之间的学习路径
    query_type=neighbors: 查找某概念的邻居（前后置）
    query_type=subgraph: 提取某概念的子图
    """

def resolve_conflicts(
    kg_id: str,
) -> ConflictReport:
    """
    检测多源知识融合中的冲突，生成仲裁建议。
    返回冲突列表，每个包含:
    - 冲突概念对
    - 冲突类型（定义矛盾/前置关系反转/示例不同）
    - 各来源的权重
    - 建议的仲裁方案
    """

# === Prompts ===
# acquisition_strategy: "我该从哪些源获取[科目]的知识？"
# kg_quality_review: "审查这个 KG 的质量，指出需要改进的地方"

# === Resources ===
# kb://corpora/{corpus_id}         → 语料库元数据
# kb://corpora/{corpus_id}/toc     → 目录结构 JSON
# kb://kgs/{kg_id}/concepts        → 概念列表（支持分页）
# kb://kgs/{kg_id}/mermaid         → Mermaid 可视化文本
```

### 2.2 tutoring-mcp

```python
# === Tools ===

def start_learning_session(
    user_id: str,
    subject_id: str,
    goal: Literal["48h_sprint", "semester_study", "exam_review", "quick_overview"],
    available_hours: Optional[int] = None,
) -> SessionStartResult:
    """
    启动一个学习会话。
    
    内部:
    1. 加载 KG → L6 构建教学路径
    2. 加载 L5 知识状态 → 跳过已掌握概念
    3. 加载 L3 复习建议 → 插入复习节点
    4. 加载 L5 学习者画像 → 个性化策略选择
    5. 创建 L2 会话上下文
    
    返回:
    {
        "session_id": "sess-abc123",
        "teaching_plan": {
            "total_concepts": 47,
            "estimated_hours": 37.5,
            "phases": [
                {"phase": 1, "concepts": [...], "estimated_hours": 8},
                ...
            ],
        },
        "current_action": {
            "type": "explain",
            "content": "我们从多元函数的极限开始...",
            "estimated_duration_min": 15,
        },
        "pre_session_insight": "你已掌握线性代数基础，跳过向量代数...",
    }
    """

def next_action(
    session_id: str,
) -> TeachingAction:
    """
    获取下一步教学动作。
    
    内部: L6 实时决策循环 → 根据 L5 最新状态决定下一步。
    
    返回 TeachingAction 类型之一:
    - explain: 讲解内容
    - ask_question: 提问
    - show_example: 展示例子
    - give_exercise: 布置练习
    - request_explanation: 费曼式要求解释
    - provide_hint: 给提示
    - reveal_answer: 揭示答案
    - review: 复习
    - checkpoint: 阶段性总结
    - break_suggestion: 建议休息
    """

def respond(
    session_id: str,
    answer: str,
) -> ResponseResult:
    """
    学生提交回答后，系统分析并返回反馈。
    
    返回:
    {
        "correctness": "correct" | "partial" | "incorrect",
        "feedback": "你说得对！..." | "基本正确，但有一个小问题..." | "不对...",
        
        # 新增：错误深度分析
        "error_analysis": {
            "type": "concept_confusion" | "symbol_mistake" | ... | null,
            "root_concept": "偏导数定义",
            "surface_concept": "多元函数极值",
            "explanation": "你把 f'(x,y) 和 ∂f/∂x 混淆了...",
            "remediation": "建议先回顾偏导数的定义和记号...",
        },
        
        # 知识状态更新
        "mastery_update": {
            "concept_id": "multi_extreme",
            "new_mastery": 0.45,
            "change": -0.03,
        },
        
        # 下一步
        "next_action": {...},
    }
    """

def interrupt(
    session_id: str,
    question: str,
) -> InterruptResult:
    """
    学生随时打断当前教学。
    
    处理:
    1. 保存 L2 断点
    2. 分类打断意图（概念问题/步骤疑问/前置缺失/节奏抱怨等）
    3. 根据不同意图给出不同回应
    
    返回:
    {
        "type": "context_aware_answer" | "prereq_tutorial" | "pace_adjustment" | "redirect",
        "content": "...",
        "position_saved": true,
        "resume_prompt": "我们刚才在讲多元函数极值，继续？",
    }
    """

def checkpoint(
    session_id: str,
    kind: Literal["self_summary", "test_result"] = "self_summary",
    content: Optional[str] = None,
) -> CheckpointResult:
    """
    阶段性总结/检测。
    
    kind=self_summary: 学生主动总结 → 系统评估总结质量
    kind=test_result: 系统出题 → 学生作答 → 系统分析
    """

def learning_insight(
    user_id: str,
    subject_id: str,
) -> InsightReport:
    """
    生成学习洞察报告。
    
    返回:
    {
        "overall_mastery": 0.73,
        "strengths": ["极限理论", "导数计算"],
        "weaknesses": [{"concept": "多元积分坐标变换", "mastery": 0.34}],
        "recommended_focus": ["重点突破坐标变换（预计需要4小时）"],
        "learning_style_evolution": "你对抽象概念的接受度比2周前提高了12%...",
        "next_milestone": "完成剩余概念后，预计整体掌握度可达85%",
    }
    """

def generate_review_plan(
    user_id: str,
    subject_id: str,
    available_time_today_min: int = 60,
) -> DailyReviewPlan:
    """
    生成今日复习计划（由 L3 多因子调度器生成）。
    
    返回每日复习微课程：
    [
        {"concept": "极限ε-δ", "mode": "quick_quiz", "est_min": 5, 
         "urgency": "3天前复习，预测正确率76%"},
        ...
    ]
    """

# === Prompts ===
# tutoring_session_start: "开始一个新科目的对话式辅导"
# design_exercise: "为我设计关于[概念]的练习题"
# diagnose_error: "帮我分析这个错误的原因"

# === Resources ===
# tutor://sessions/{session_id}/status   → 当前进度
# tutor://sessions/{session_id}/history  → 对话历史（分页）
# tutor://users/{user_id}/profile        → 学习者画像摘要
```

### 2.3 digest-mcp

```python
# === Tools ===

def digest(
    corpus_id: Optional[str] = None,
    kg_id: Optional[str] = None,
    formats: List[str] = ["mindmap", "quiz"],
    grade: str = "college",
    learning_style: Optional[str] = None,
) -> DigestResult:
    """
    统一的可视化课件生成入口。
    
    内部按最优顺序编排:
    ① 思维导图（全局认知）
    ② 笔记（知识输入）
    ③ 幻灯片（结构呈现）
    ④ 测验（检测）
    ⑤ 音频（听觉辅助）
    ⑥ 交互模拟（运用）
    ⑦ 多智能体（深度讨论）
    
    自动调用 L4 KG 数据 + L5 画像进行个性化。
    
    返回:
    {
        "artifacts": [
            {"uri": "artifact://.../mindmap.png", "format": "mindmap"},
            {"uri": "artifact://.../quiz.html", "format": "quiz"},
            ...
        ],
    }
    """

def build_quiz_html(
    quiz_data: Union[str, dict],   # JSON 题目或 kg_id
    count: int = 10,
    difficulty_mix: tuple = (0.3, 0.5, 0.2),  # 简单/中等/困难比例
) -> ArtifactURI:
    """
    生成极简交互测验 HTML（复用 quiz-template.html）。
    """

def compile_slides(
    images: List[str],
    notes: Optional[List[str]] = None,
    output_format: Literal["pdf", "pptx", "both"] = "both",
) -> List[ArtifactURI]:
    """汇编幻灯片为 PDF/PPTX（python-pptx + img2pdf）"""
```

### 2.4 sync-mcp

```python
# === Tools ===

def init_subject_repo(
    user_id: str,
    subject_id: str,
    github_org: str = "my-ai-learning",
) -> RepoInitResult:
    """
    为科目创建 GitHub 仓库:
    {github_org}/{user_id}-{subject_slug}
    """

def push_artifacts(
    subject_id: str,
    artifacts: List[str],     # artifact:// URI 列表
    commit_message: str,
) -> PushResult:
    """推送学习产物到 GitHub"""

def pull_homework_from_obsidian(
    vault_path: str,
    subject_id: str,
) -> HomeworkBatch:
    """从 Obsidian vault 拉取作业文件"""

def watch_obsidian(
    vault_path: str,
    subject_id: str,
    poll_interval_sec: int = 30,
) -> Generator[FileChange, None, None]:
    """
    监听 Obsidian vault 的文件变更。
    使用 MCP notifications/progress 推送实时事件。
    """
```

---

## 3. 打断机制详细协议

```
学生输入 "为什么这里不能用洛必达？"
  ↓
L7.interrupt(session_id, "为什么这里不能用洛必达？")
  ↓
L2.save_checkpoint()           # 保存当前教学位置
  ↓
L6.handle_interrupt():        # 分析意图 + 生成回应
  ↓
返回 InterruptResult → L7 展示给学生
  ↓
学生选择: 继续原流程 / 跟进 interrupt 回答 / 切换话题
  ↓
如果继续原流程:
  L2.restore_from_checkpoint() → L6.resume()
```

### 打断意图分类规则

| 学生输入模式 | 意图分类 | 处理策略 |
|-------------|----------|----------|
| "为什么..."、"怎么会..." | 概念/过程问题 | 上下文感知回答 |
| "我忘了XX是什么" | 前置缺失 | 插入 mini 复习 |
| "太快了"、"跟不上了" | 过载 | 降速 + 建议休息 |
| "这个和XX有关系吗" | 关联探索 | 回答 + 记录到知识网络 |
| "能举例吗" | 例子请求 | 从 L4 KG 调例子 |
| 与当前主题无关的闲聊 | 分心 | 温和重导向 |
| (长时间无响应) | 可能掉线 | 发 ping，5 分钟后自动保存退出 |

---

## 4. 进度可视化数据

```python
def progress_snapshot(session_id: str) -> ProgressData:
    """
    供前端/L7 渲染进度条/看板的数据:
    
    {
        "overall": {
            "total_concepts": 86,
            "mastered": 47,
            "learning": 23,
            "remaining": 16,
            "percent_complete": 54.7,
        },
        "current_session": {
            "started_at": "2026-05-19T08:00:00",
            "elapsed_hours": 2.5,
            "concepts_covered_today": 5,
            "avg_mastery_change": +0.12,
        },
        "mind_map_mermaid": "graph TD\n...",     # 实时 KG 染色
        "next_review_queue": [...],
        "estimated_time_to_completion": "18.5小时",
    }
    """
```

---

## 5. 与 L6 的协作模式

```
L6 产出: TeachingAction (结构化)
L7 职责: 将 TeachingAction 转化为自然语言 + 可选多模态渲染

示例:
L6 → {type: "explain", content: "多元函数的极限定义：设..."}
L7 → 决定:
  - 纯文本模式: 直接展示
  - 富文本模式: 公式用 KaTeX 渲染
  - 视觉模式: 自动生成概念图/动画
  - 语音模式: TTS 朗读

L6 不关心渲染方式，L7 根据前端能力 + 学生偏好选择展示模式。
```
