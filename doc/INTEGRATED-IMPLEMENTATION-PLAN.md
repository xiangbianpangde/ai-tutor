# 整合实施计划

> 覆盖四项：逐层可视化与测试 / pdf2zh+research+BiliNote 集成 / 视频转图文笔记 / 设计缺口补齐(A+B)
> 总预估：~5 周（约 25 个工作日）
> 原则：每阶段结束时有可运行的交付物

---

## 总览路线图

```
Week 1          Week 2          Week 3          Week 4          Week 5
A类快速补齐 ──┤
12->12 关系     │
lambda加权混合   │
3种动作         │
PaceController  │
诊断正则表       │
认知负荷信号     │
Quality Gate    │
Flow 4->5级     │
               ├─ 逐层可视化 ───────────────────┤
               │ L4/L5/L3 页面                    │ L1/L2/L6/L7/PGFGA │
               │ BDD 按层拆分                      │ BDD 全量回归      │
               │                                  ├─ 工具集成 ───────┤
               │                                  │ pdf2zh adapter   │
               │                                  │ research adapter │
               │                                  │ BiliNote adapter │
               │                                  │                  ├─ B类较大项 ──────┤
               │                                  │                  │ 学生知识网络       │
               │                                  │                  │ 画像演化引擎       │
               │                                  │                  │ SDT 深度支持       │
               │                                  │                  │                  ├─ 视频转图文 ────┤
               │                                  │                  │                  │ yt-dlp+whisper   │
               │                                  │                  │                  │ LLM 结构化        │
```

---

## 阶段零：前置依赖声明

| 本阶段需要的 | 依赖谁 | 状态 |
|-------------|--------|------|
| 逐层可视化 L4 页面需 KG 关系数据 | A类的 12->12 关系补全 | A 类先做 |
| 工具集成 tools-ui 复用 dashboard 框架 | 逐层可视化的 Starlette 多路由改造 | 可视化先做 server 层拆分 |
| 学生知识网络 消费 BKT + 交互历史 | 画像引擎（共享 BKT 数据源） | 可并行 |
| 视频转图文 yt-dlp + whisper | 无前置 | 独立 |

---

## 阶段一：A 类快速补齐（Week 1，约 4 天）

8 个小项，每项 <= 半天，全部可独立验证。

### 1.1 12->12 语义关系补全（0.5 天）

- 文件：`concept_enricher.py` prompt 扩写 + 后处理规则
- Schema 已全定义 12 种，LLM prompt 加一段"请为每对概念标注关系类型"
- 验证：`test_concept_enricher.py` 加 12 种关系的断言

### 1.2 lambda 加权混合（0.5 天）

- 文件：`forgetting_curve.py:fit_lambda`
- 数据点 3-5 时：`lambda = w * lambda_fitted + (1-w) * lambda_default`，`w = n/10`
- 验证：`test_forgetting_curve.py` 加 3/4/5 点三种场景

### 1.3 3 种教学动作（0.5 天）

- 文件：`engine.py` 动作生成分支 + `content_generator.py` 模板
- ShowCounterExample（反例展示）、BreakSuggestion（休息建议）、PaceFeedback（节奏反馈）
- 验证：`test_engine.py` 加 action type 断言

### 1.4 PaceController 独立类（0.5 天）

- 新文件：`servers/tutoring_mcp/pace_controller.py`
- 从 `flow_regulator` + `strategy_selector` 收拢节奏逻辑
- 验证：既有测试全部回归（重构不改变行为）

### 1.5 诊断正则 ERROR_PATTERNS 表（0.5 天）

- 文件：`error_diagnoser.py` 加正则快速路径
- `symbol_mistake`（量词反用 / epsilon-delta 顺序错 / 等号不等号混淆）优先
- 验证：`test_error_diagnoser.py` 加正则匹配 case

### 1.6 认知负荷文本信号（0.5 天）

- 文件：`cognitive_load.py`
- 加 `answer_length_variance`（答案长度波动）和 `question_rephrasing_rate`（"能换个说法吗"触发率）
- 验证：`test_cognitive_load.py` 加信号采集断言

### 1.7 Quality Gate 结构化检查（0.5 天）

- 文件：`kg_full.py` / `kg_review.py`
- 加三项：章节覆盖率 >= 85% / 每概念 >= 1 示例 / 定义-定理-公式分布合理性
- 验证：`test_kg_full.py` 加 quality gate 断言

### 1.8 Flow 4->5 级（0.5 天）

- 文件：`schemas.py:FlowLevel` 扩到 5 级 + `flow_tracker.py` 适配
- SILENT -> SHALLOW -> FLUENT -> DEEP -> IMMERSED
- 验证：`test_flow_tracker.py` 改预期值

**交付物**：8 项 PR 合并，pytest 672 -> ~710 全绿。

---

## 阶段二：逐层可视化 + BDD 重组（Week 2-3，约 8 天）

### 2.1 数据层拆分（1 天）

`state.py` 拆成 8 个函数：

```
get_layer_L1_state(db)   # PluginRegistry.health_all() + storage stats + cache stats
get_layer_L2_state(db)   # 活跃 SessionContext 列表 + 中断恢复记录
get_layer_L3_state(db)   # 遗忘曲线数据 + 复习队列 + 复习模式分布
get_layer_L4_state(db)   # KG Mermaid + 概念-关系拓扑 + 难度分布
get_layer_L5_state(db)   # BKT 热力图数据 + 错误类型饼图 + 认知负荷时序
get_layer_L6_state(db)   # 策略状态机当前态 + 心流曲线 + 增益回路事件
get_layer_L7_state(db)   # 对话历史 + digest 产物列表 + Obsidian 同步状态
get_layer_pgfga_state(db)# 防火墙触发日志 + SDT 信号 + 增益回路健康度
```

### 2.2 路由 + 模板（4 天）

server.py 新增 8 条路由，每个层一个模板：

| 天 | 层 | 核心可视化 |
|----|-----|-----------|
| 2.1 | L4 + L5 | Mermaid 渲染（mermaid.js CDN）+ BKT 热力图（CSS grid 颜色矩阵） |
| 2.2 | L3 + L6 | 遗忘曲线 SVG + 策略状态机动画 |
| 2.3 | L1 + L2 + L7 | 插件健康表 + 对话历史列表 + 产物画廊 |
| 2.4 | PGFGA | 防火墙事件表 + 心流转移图 |

所有模板共用 `index.html` 的 CSS 变量，纯 vanilla。顶部导航栏切换层。

### 2.3 BDD 重组（1.5 天）

从 `BDD/test_bdd_ai_tutor.py`（单文件 58 Scenario）拆成：

```
BDD/features/
├── L1_test_bdd.py    # schemas / errors / storage / llm_client / cache
├── L3_test_bdd.py    # curve / memory / scheduler / review_plan
├── L4_test_bdd.py    # acquire / build / query / review / update / diff / rollback / full
├── L5_test_bdd.py    # bkt / error / cognitive_load / cold_start
├── L6_test_bdd.py    # strategies / engine / respond / interrupt / advance / flow / gain
├── L7_test_bdd.py    # digest / mindmap / notes / quiz / slides / audio
├── sync_test_bdd.py  # obsidian / git / watch
├── conftest.py        # 共享 fixture
```

### 2.4 全量回归（1 天）

```
uv run pytest BDD/features/ -v    # 58 scenarios, 57 pass + 1 skip
uv run pytest                     # 原有全部回归
```

**交付物**：8 层页面可访问；BDD 按层拆分；全量测试回归通过。

---

## 阶段三：pdf2zh / research-tool / BiliNote 集成（Week 3-4，约 6 天）

### 3.1 tools-ui 骨架（1 天）

基于阶段二的 Starlette 基架，新建 `servers/tools-ui/`（端口 8502）：

```
servers/tools-ui/
├── server.py
├── templates/
│   ├── index.html       # 工具列表 + 导航
│   ├── pdf2zh.html      # PDF 解析测试页
│   ├── research.html    # research-tool 调参页
│   └── bilinote.html    # BiliNote 转写测试页
└── adapters/
    ├── pdf2zh_adapter.py
    ├── research_adapter.py
    └── bilinote_adapter.py
```

### 3.2 pdf2zh（1.5 天）

- Adapter：Docker 启动容器 -> POST /api/convert -> 返回 MD。注册到 `PluginRegistry("pdf_parse", priority=10)`
- UI：文件选择 + 参数面板 + docker logs 实时流 + MD 预览
- 接入：`_convert_pdf()` 改为 `PluginRegistry.get("pdf_parse")`，pdf2zh 健康优先，否则 fallback mineru
- BDD：`BDD/features/tools/test_pdf2zh.py`

### 3.3 research-tool（1.5 天）

- Adapter：封装 `research_tool.pipeline`（collect + clean），importlib 探测
- UI：主题输入 + 源筛选 + 采集进度 + 清洗对比 + MD 预览 + 一键送 KG
- 接入：`_acquire_web()` 从 stub 改为真实调用
- BDD：`BDD/features/tools/test_research.py`

### 3.4 BiliNote（1.5 天）

- Adapter：`subprocess.run(["bilinote", url, "-o", out_dir])`，探测 CLI
- UI：B站 URL + 弹幕/截图参数 + 结果预览
- 接入：`AcquireSource(type="video", source="bilibili")` -> BiliNote
- BDD：`BDD/features/tools/test_bilinote.py`

### 3.5 集成验证（0.5 天）

三工具全链路：`acquire -> build_kg -> start_learning_session`。确认 adapter health() 正确参与降级链。

**交付物**：3 adapter + 3 UI；BDD 每工具 >= 2 Scenario；tools-ui 可独立启动。

---

## 阶段四：B 类较大项（Week 4-5，约 6 天）

### 4.1 学生知识网络（2.5 天）

新文件 `servers/tutoring_mcp/knowledge_network.py`：

```
StudentKnowledgeNetwork
├── nodes: dict[concept_id -> StudentConceptNode]
│     mastery, n_reviews, first_learned_at, affective_tag
├── edges: list[StudentDiscoveredEdge]
│     from_id, to_id, relation, strength
├── detect_connections(answer, concept, kg) -> entity linking + 共现
├── reinforce_edge(edge, delta) -> 复习正确+0.1, 错误-0.05
└── metrics() -> density, avg_path_length, isolated_nodes
```

接入 `review_scheduler.py`：加因子 `network_connectivity`（孤立节点优先级提升）

### 4.2 画像演化引擎（2.5 天）

新文件 `servers/tutoring_mcp/profile_evolver.py`：

```
ProfileEvolver.evolve(profile, session_stats, bkt_map, error_history) -> LearnerProfile

规则 1: working_memory_span    连续 N 概念后正确率下降 -> span = N
规则 2: frustration_threshold  连续 N 题错后简单题也崩 -> threshold = N
规则 3: abstract_tolerance     抽象概念正确率 + 求助频次
规则 4: preferred_pace         实际速度 vs 预估时长偏差
规则 5: self_assessment_acc    自评 vs BKT mastery EMA 更新
规则 6: help_seeking_tendency  主动中断频次 / 答题总数
```

引擎 `respond` 后调用 `evolve()` -> 写回 `learner_profiles` 表

### 4.3 SDT 深度支持（1 天）

- **自主选择**：`next_action` 返回加 `options: list[Choice]`（节奏/路径/检测方式三选一）
- **胜任感**：`feedback_generator` L3 prompt 加 compare_prompt + reframe_prompt
- **归属感**（最小版）：SessionContext 加 `recognized_expressions`，记住并引用学生独特表达

**交付物**：3 新文件；BDD 各 >= 5 Scenario；引擎回归。

---

## 阶段五：视频转图文笔记（Week 5，约 2 天）

### 5.1 依赖探测 + 转写（1 天）

新文件 `servers/knowledge_mcp/video_transcriber.py`：

```
VideoTranscriber
├── download_audio(url, out_dir) -> yt-dlp CLI
├── transcribe(audio_path) -> faster-whisper base model
├── to_markdown(segments) -> 时间戳 + 分段文本
└── enrich_with_llm(md_text) -> LLM 识别章节标题
```

importlib 探测依赖，缺则 `DEPENDENCY_MISSING`。不加入必需依赖。

### 5.2 接入 + 验证（1 天）

- `_acquire_video()` 从 stub 改为真实调用。`depth=basic` 纯转写，`depth=full` 转写+LLM 结构化
- BDD：`BDD/features/tools/test_video_transcriber.py`（Mock yt-dlp/whisper）

**交付物**：video 源从 stub 变为可用；BDD >= 2 Scenario

---

## 依赖关系图

```
A 类快速补齐 (W1)
  └─ 产出被阶段二消费（L4 页面用 12种关系；L6 页面用 PaceController）
        │
        ▼
逐层可视化 (W2-3)
  ├─ 消费 A 类产出
  ├─ 产出 Starlette 多路由基架
  └─ 产出被阶段三消费（tools-ui 复用基架）
        │
        ├──────────────────────┐
        ▼                      ▼
工具集成 (W3-4)         B 类较大项 (W4-5)
  ├─ 复用可视化基架      ├─ 消费 A 类的诊断正则/认知负荷信号
  └─ 独立于 B 类         ├─ 知识网络与画像引擎可并行
                           └─ SDT 依赖画像引擎
                                │
                                ▼
                          视频转图文 (W5)
                            └─ 独立，只依赖 acquisition stub 替换
```

---

## 总排期

| 周 | 阶段 | 主要产出 |
|----|------|---------|
| 1 | A 类快速补齐（8 项） | 12种关系 / lambda混合 / 3动作 / PaceController / 诊断正则 / 认知负荷信号 / Quality Gate / Flow 5级。测试 ~710 全绿 |
| 2 | 逐层可视化 前半 | 数据层拆分；L4/L5/L3 页面可访问；BDD 拆分进行中 |
| 3 | 逐层可视化 后半 | L1/L2/L6/L7/PGFGA 页面；BDD 拆分完成；全量回归通过 |
| 4 | 工具集成 + B类前两项 | 3 adapter + 3 UI + 学生知识网络 + 画像引擎 |
| 5 | B类第三项 + 视频转图文 | SDT 自主选择/胜任感；video 源可用 |

---

## 每阶段降级方案

| 阶段 | 如果时间紧 | 降级做法 |
|------|-----------|---------|
| A 类 | 认知负荷文本信号 | 延后 - 当前加权公式已可用 |
| A 类 | PaceController | 延后 - 纯重构，不影响功能 |
| 可视化 | L1/L2 页面 | 延后 - 对调试帮助不如 L4/L5 |
| 工具 | BiliNote | 若 CLI 不可用则跳过，阶段五覆盖通用视频 |
| B 类 | SDT 归属感 | 最小版（记住表达）做；完整版（情绪检测）延后 |
| 视频 | LLM 结构化 | basic 模式先交付，full 模式延后 |
