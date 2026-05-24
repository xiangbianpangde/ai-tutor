# 48 小时完整数据流

> 演示：从"我要学同济版高等数学下册"到 48 小时后的学习报告  
> 时间轴格式：T+hh:mm

---

## T=-24h（提前准备）

```
用户: 设置系统
  → 配置 Tutoring Server 的 LLM provider（DeepSeek / OpenAI / Anthropic）
  → 拉取 Docker 镜像: docker compose pull（pdf2zh, mineru, whisper, redis）
  → 确认 GPU 可用（nvidia-smi）
```

---

## T=0:00（开始）

```
用户 → tutoring-mcp.start_learning_session("yhn", "同济高数下册", "48h_sprint")
  
  系统响应:
    "你还没有这个科目的知识库。请先运行 acquire_subject。"
    
用户 → knowledge-mcp.acquire_subject(
    subject="同济版高等数学下册",
    version="8th",
    sources=["textbook", "video"],
)

  系统:
    ① fetch_textbook → Anna's Archive → 返回 3 个匹配
       链接: [Anna's, LG, Z-Library]
       → 用户选择下载一个 PDF（手动），放入输入目录

    ② pdf_to_markdown("高数下_v8.pdf")
       → Docker pdf2zh 容器启动
       → OCR 模式: 扫描版 PDF → 数学公式保留 → Markdown 输出
       → GPU 加速: 单页 ~3 秒 × 400 页 = ~20 分钟
       
    ③ transcribe_video(源="B站配套视频")
       → yt-dlp 下载视频音频
       → faster-whisper (base) 转写 → 中文文本
       → LLM 总结 → 章节对齐 summary
       → 并行执行（与 pdf→md 同时） → ~10 分钟

    ④ web_collect("高数下册 重点 笔记")
       → DuckDuckGo 搜索
       → 抓取 5 个网页 → 提取正文 → 保存本地
       → ~5 分钟

    ⑤ normalize_corpus([pdf_md, video_transcript, web_collected])
       → 去重（文档指纹 + 语义相似度）
       → 章节对齐（以教材目录为骨架）
       → 统一 Markdown 格式
       → ~5 分钟

    返回:
      corpus_id = "gaoshu-v8-yhn-20260519"
      stats: {total_chapters: 12, estimated_concepts: 800+, sources: 3}
      artifact_uris: [...]
```

---

## T=0:45 知识图谱构建

```
用户 → knowledge-mcp.build_knowledge_graph(corpus_id, "full")

  ① Passage Splitter → 分割为语义段落 (~2min)
  ② Concept Detector → 识别 ~847 个概念 (~15min, 批量 LLM调用)
  ③ Relation Extractor → 抽取 ~3200 个关系 (~10min)
  ④ Difficulty Scorer → 难度评分 (~2min)
  ⑤ Embedding Indexer → 向量索引 (~5min, 本地模型)
  ⑥ Quality Gate → 质量检查
       pass: 章节覆盖率 92%
       warnings: 3 个概念无示例, 1 个依赖循环(多元→偏导→多元)
       → 自动修复: 用 LLM 补充示例; 弱化循环边

  返回:
    kg_id = "gaoshu-v8-kg-v1"
    triples_count: 3247
    quality_report: {overall: "pass"}
    visual_export: {mermaid: "graph TD\n...", gml_path: "..."}
```

---

## T=1:30 教学会话启动

```
用户 → tutoring-mcp.start_learning_session("yhn", "gaoshu-v8-kg-v1", "48h_sprint", available_hours=48)

系统内部:
  ① L6 加载 KG → 分析概念依赖图
  ② L5 加载用户知识状态 → 
     已有掌握: 线性代数(78%)、一元微积分(91%)
     全新内容: 多元微积分、曲线积分、曲面积分
  ③ L6 构建教学路径（降阶法 bottom_up）:
     Phase 1 (8h): 向量代数+空间解析几何（仅新内容）
     Phase 2 (12h): 多元函数微分学
     Phase 3 (14h): 多元函数积分学
     Phase 4 (8h): 曲线积分+曲面积分
     Phase 5 (4h): 级数
     缓冲: 2h
  ④ L3 插入复习节点: 每 3 个新概念后插入 1 个复习概念
  ⑤ L5 画像冷启动: 假设 working_memory_span=5, preferred_pace=fast

  返回:
    {
      session_id: "sess-gaoshu-v8-001",
      teaching_plan: {5 phases, 47 教学片断, 37.5h 教学 + 8h 巩固},
      current_action: {
        type: "explain",
        content: "欢迎！你已经有扎实的一元微积分基础...我们从空间直角坐标系开始。",
        estimated_duration_min: 12,
      }
    }
```

---

## T=1:45 ~ T=45:00 教学循环

### 示例：一个教学片断的完整交互

```
T=1:45
用户 → tutoring-mcp.next_action(session_id)
系统 → {type: "explain", content: "空间直角坐标系由三个互相垂直的坐标轴..."}

T=1:57 (讲解结束)
用户 → tutoring-mcp.next_action(session_id)
系统 → {type: "ask_question", content: "点P(2,3,1)到xy平面的距离是多少？"}

T=1:59
用户 → tutoring-mcp.respond(session_id, "1")
系统 → {
  correctness: "correct",
  feedback: "对！z坐标的绝对值就是到xy平面的距离。",
  mastery_update: {concept: "空间直角坐标系", mastery: 0.65 → 0.78},
  next_action: {type: "explain", content: "接下来我们看向量的坐标表示..."}
}

---

T=2:12 (讲到向量叉积)
用户 → tutoring-mcp.interrupt(session_id, "叉积为什么满足右手定则？")

系统内部:
  L2.save_checkpoint() → 保存当前状态
  L6.handle_interrupt(question) → intent: concept_question
  分析: 学生已经掌握叉积定义，但对其定向规则有深层疑问
  → 这是"good interruption"（深层理解）

系统 → {
  type: "context_aware_answer",
  content: "好问题！叉积的方向不是人为规定的——它来自向量空间的方向性。在右手系下...（详细解释）",
  position_saved: true,
  resume_prompt: "理解了叉积方向后，我们继续看它的几何意义？"
}

---

T=3:45 (完成 Phase 1 的三个教学片断)
用户 → tutoring-mcp.checkpoint(session_id, "self_summary", 
          "我学到了空间直角坐标系、向量运算、叉积。叉积的方向性需要多练。")

系统 → {
  self_assessment: "你的总结覆盖了 3/3 核心概念。你特别注意到叉积的难点——很好。",
  mastery_update: {
    "空间直角坐标系": 0.92, "向量运算": 0.88, "叉积": 0.71,
  },
  cognitive_load: 0.41,  # 正常范围
  next: "休息5分钟后进入多元函数极限",
}
```

---

## T=10:00 系统主动干预示例

```
系统内部 L5 检测:
  - 最近 4 个概念: mastery 全部 < 0.5
  - 认知负荷: 0.78 (> 0.7 阈值)
  - 行为信号: 答题时间 > baseline * 1.8, 连续 2 次修正答案

系统 → tutoring-mcp.next_action(session_id)
  → {type: "break_suggestion", 
     content: "你最近几次答题的准确率在下降，可能太累了。建议休息 15 分钟。当前进度已保存。"}
```

---

## T=22:00 跨科目知识关联（自动）

```
系统 L3 检测:
  学生刚学完"多元函数极值" + 2 天前刚复习过"一元极值"
  学生在费曼解释中自发说: "多元极值就是多个方向都要考虑..."
  → L3 记录: StudentDiscoveredEdge(multi_extreme, single_extreme, "analogous_to")
  → 下次复习 multi_extreme 时，自动带上 single_extreme 的题目做对比
```

---

## T=45:00 教学完成

```
用户 → tutoring-mcp.learning_insight("yhn", "gaoshu-v8-kg-v1")

系统 → {
  overall_mastery: 0.73,
  concepts_mastered: 73/86,
  concepts_learning: 10,
  unknown: 3,
  
  strengths: ["向量运算", "偏导数计算", "二重积分"],
  weaknesses: [
    {"concept": "坐标变换(三重积分)", "mastery": 0.34, "root_cause": "空间想象能力"},
    {"concept": "格林公式的应用", "mastery": 0.41, "root_cause": "条件判断不熟"},
  ],
  
  learning_style_evolution: {
    "abstract_tolerance": "从0.48提升到0.61 (+27%)",
    "working_memory_span": "从5提升到6",
    "self_assessment_accuracy": "从0.55提升到0.68 (更准确了)",
  },
  
  recommended_focus: [
    "重点突破坐标变换（预计4小时）",
    "格林公式条件判断练习（预计2小时）",
    "剩余3个未知概念即可快速掌握（1.5小时）",
  ],
  
  next_review_plan: {
    "tomorrow": ["坐标变换(早)", "格林公式(午)"],
    "day_3": ["叉积", "方向导数", "三重积分"],
    "day_7": ["拉格朗日乘数法", "斯托克斯公式"],
  },
}
```

---

## T=47:30 产物同步

```
用户 → digest-mcp.digest(kg_id="gaoshu-v8-kg-v1", 
                           formats=["mindmap", "notes", "quiz", "slides"])

系统:
  ① mindmap → Mermaid → mermaid-cli → PNG (~2min)
  ② notes → 手写风格 PDF（含错题标注） (~5min)
  ③ quiz → quiz-template.html 渲染 (~3min)
  ④ slides → 汇编 PDF + PPTX (~5min)

用户 → sync-mcp.push_artifacts("gaoshu-v8-kg-v1", 
         artifacts=[...], commit="完成48h高数下册完整学习")

系统:
  → GitHub: yhn/gaoshu-v8 → commit abc123
  → GitHub Pages: https://yhn.github.io/gaoshu-v8/ → 学习产物可浏览
```

---

## T=48:00 最终状态

```
学习报告:
  ✓ 核心概念掌握: 73/86 (85%)
  ✓ 总学习时间: 38.5h 教学 + 5h 巩固 + 4.5h 缓冲
  ✓ 错题库: 47 道（已按错误类型分类）
  ✓ 个人遗忘曲线: 14 个概念有足够数据点开始拟合
  ✓ 学习者画像: 5 个维度已稳定，2 个维度仍在演化中
  
  GitHub: ✅ 所有产物已同步
  Obsidian: ✅ 作业已提交并批改

下次行动建议:
  → 明天: 复习坐标变换（预测正确率43%→目标70%）
  → 7 天后: 全面复习（预测总掌握度从73%降到58%→需复习）
  → 开始新科目: "线性代数"（已检测到前置知识充足，预计只需30h）
```
