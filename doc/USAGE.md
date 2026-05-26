# 使用指南 — 从一份资料到学完一科

> 这份指南讲**怎么用**：把一科资料喂进去，到分阶段学完、复习。
> **更详细的全工具参考见 [USER-MANUAL.md](./USER-MANUAL.md)**（含 PDF 翻译、web 调研、逐层面板、四 server 工具全表）。
> 接入 MCP host 的配置见 [INTEGRATION.md](./INTEGRATION.md)；生产部署见 [DEPLOYMENT.md](./DEPLOYMENT.md)。
> 真实教材验证见 [48H-VALIDATION.md](./48H-VALIDATION.md)。

---

## 0. 三种用法

| 方式 | 适合 | 怎么驱动 |
|------|------|---------|
| **Claude Desktop / Cursor**（推荐） | 日常学习 | 自然语言，让 Claude 调 4 个 MCP server 的工具 |
| **直接 Python** | 脚本化 / 调试 | 调 `servers.*.server` 里的 tool 函数（见 §6） |
| **状态面板** | 旁观进度 | 浏览器看实时仪表盘（见 §5） |

四个 server 各管一段：**knowledge**（建知识图谱）/ **tutoring**（教学）/ **digest**（复习产物）/ **sync**（Obsidian+git）。
另有一个只读 **dashboard** 看实时状态。

---

## 1. 准备（一次性）

```powershell
cd C:\Users\yhn\Desktop\ai-tutor
uv sync --extra research --extra dev      # 装依赖（research=web采集，dev=测试；两 extra 一起，否则互相卸载）
uv run python scripts/init_db.py          # 建库（或首次调用自动建）
uv run pytest                             # 761 passed + 1 skipped = 健康
# PDF 源还需： uv tool install mineru
```

- **DeepSeek key**：在 `.env` 写 `DEEPSEEK_API_KEY=sk-...`。
  - 配了 → 概念富化 / 教学内容 / 反馈 / 判分走真实 LLM。
  - 没配 → 全部优雅降级到模板/启发式，**流程照样跑通**，只是内容不如真实 LLM 生动。
- 接 Claude Desktop：照 [INTEGRATION.md](./INTEGRATION.md) 把 4 个 server 写进 `claude_desktop_config.json`，重启。

---

## 2. 把一科资料变成知识图谱

### 2.1 采集 `acquire_subject`

```
acquire_subject(subject="高等数学下册", sources=[{"type":"file","uri":"<路径>"}], user_id="yhn")
→ 返回 corpus_id
```

- **支持的源**（可混传，合并进一个 corpus）：
  - `file` `.md`/`.txt`（直读）、`.pdf`（需 `mineru` CLI）；外文 PDF 加 `"translate":"true"` → mineru 抽英文 md 后用 DeepSeek 译成中文。
  - `web`：`{"type":"web","uri":"主题关键词"}` → research-tool 联网采集网页正文（需能访问 duckduckgo/外站，CN 多半要代理）。
  - `video`：暂未接入（抛 DEPENDENCY_MISSING）。
- **PDF 注意**：扫描影像 PDF（无文本层）需要 OCR；本机没装 mineru 时，先把资料整理成
  **带 `#`/`##`/`###` 标题的 Markdown**（标题层级 = 章/节/概念），用 `.md` 源即可，不依赖任何 OCR。
- 详见 [USER-MANUAL.md §6.1](./USER-MANUAL.md#61-采集三种源)。

### 2.2 建图谱 `build_knowledge_graph`

```
build_knowledge_graph(corpus_id=<上一步>, depth="full")
→ 返回 kg_id、quality_report、mermaid
```

| depth | 内容 | 何时用 |
|-------|------|--------|
| `toc` | 纯规则抽章节骨架（不调 LLM，秒级） | 先看结构 / 没 key |
| `concept` | LLM 富化每个概念：定义/例子/误解/难度信号 | 要教学内容 |
| `full`（**推荐**） | concept + **学习时长校准 + 难度校准 + embedding** | 正式学一科 |

- **`full` 才有真实的时长/难度分布**：concept 深度所有概念按默认 30min；full 深度按内容
  校准到 5–45min（一科约几十小时，贴近预算）。冷启动摸底的难度分带也只在 full 下铺开。
- 大教材会**并行富化 + 断点续跑**（139 概念 / 8 worker / 真实 DeepSeek ≈ 40s）。
- **建完即可教**：build 会自动建好 `Subject` 行并把 `kg_id` 指过去——
  后续教学工具直接用 **`subject_id` = 科目名的拼音 slug**（如「高等数学下册」→ `gaodengshuxuexiace`，
  可在 build 日志 / health 里看到）。

### 2.3 （可选）人工确认 `review_kg` / `update_kg`

```
review_kg(kg_id, mode="quick")          → 列出低置信度概念 + 建议
update_kg(kg_id, actions=[...])         → 批准/改定义/合并；mode="versioned" 建新版本
```

---

## 3. 学：冷启动 → 分阶段教学

### 3.1 冷启动摸底（强烈建议先做，省 20–30% 时间）

```
cold_start_probe(user_id="yhn", subject_id=<slug>, num_questions=10)
→ 10 道跨难度摸底题（每题一个 concept）
```

学生作答后：

```
submit_cold_start(user_id, subject_id, answers=[
  {"concept_id":"...", "answer":"学生的回答", "self_report":"sure|unsure|dont_know"}, ...
])
→ 判分 → 种 BKT 先验 + 写画像初值；已掌握的概念后续自动跳过
```

### 3.2 开课 `start_learning_session`

```
start_learning_session(user_id, subject_id, goal="48h_sprint")
→ { session_id, teaching_plan(按章节切的 Phase + 各 Phase 完成度),
    current_action(第一个教学动作), pre_session_insight(进度摘要) }
```

### 3.3 教学循环 — `advance` 与 `respond` 配合

每个 `current_action` / `next_action` 有个 `type`，按它选下一步：

| action.type | 含义 | 下一步调 |
|---|---|---|
| `explain` / `show_example` / `reveal_answer` / `reflection` | 讲解/示例（不需作答） | **`advance(session_id)`** → 下一步 |
| `ask_question` / `give_exercise` / `request_explanation` / `provide_hint` | 要学生作答 | **`respond(session_id, answer)`** → 判分+反馈+推进 |

典型一轮（reduction 策略）：

```
start → [explain 讲解]      → advance
       → [show_example 例子] → advance
       → [ask_question 提问] → respond("学生的回答")  ← 判分 + LLM 反馈 + BKT 更新
       → 概念学完 → next_action 自动切到下一个未掌握概念（已掌握的跳过）
```

- **策略是自动选的**：引擎按 mastery / 认知负荷 / 心流 / 画像在 6 种策略里挑
  （reduction / 降阶法jiangjie / 费曼 / 苏格拉底 / 类比 / 项目驱动），并用心流调节器调难度/脚手架。
- `respond` 的反馈是三级管道（模板 → 针对性补救 → 真实 LLM 润色，过非评判防火墙）。
- `next_action(session_id)` 随时拿"当前该做什么"；`interrupt(session_id, question)` 处理学生打断。

### 3.4 看进度 / 续学

```
get_learning_progress(user_id, subject_id)
→ 总体掌握比例、各 Phase 完成度、当前 Phase、下一个该学的概念（不开会话）

resume_learning(user_id, subject_id)
→ 接着上次：有未结束会话就复用，否则从第一个未掌握概念继续
```

---

## 4. 复习（跨天）

```
learning_insight(user_id, subject_id)              → 强项/弱项/推荐focus
generate_review_plan(user_id, subject_id, available_time_today_min=30)
→ 基于个性化遗忘曲线 + 多因子优先级排出今天该复习什么、用什么复习模式
```

---

## 5. 状态面板（旁观实时状态）

```powershell
uv run python -m servers.dashboard.server     # 默认读 data/tutor.db，→ http://localhost:8501
# 指向别的库：先设 DATABASE_URL=sqlite:///绝对路径.db
```

- **总览页** **http://localhost:8501/**：4 个区域每 3 秒刷新——当前概念/心流/策略 · 策略步骤条 · 掌握度分布 + 最近交互 · 48h Phase 进度。
- **逐层页** **http://localhost:8501/layers**：8 个 Tab 分层只读——L1 存储 / L2 会话 / L3 遗忘曲线 / L4 KG Mermaid 拓扑 / L5 BKT 热力图 / L6 策略状态机+心流 / L7 对话 / PGFGA 心流趋势。

只读、独立进程，不影响教学。

---

## 6. 不接 Claude Desktop：直接 Python 驱动

每个 tool 是 `servers/<x>/server.py` 里的 async 函数，可直接 await。最小闭环：

```python
import asyncio
from servers.knowledge_mcp import server as k
from servers.tutoring_mcp import server as t

async def run():
    fn = lambda x: getattr(x, "fn", None) or x          # 取被 @mcp.tool 包装的原函数
    a = await fn(k.acquire_subject)(subject="高数下",
            sources=[{"type":"file","uri":"examples/gaoshu_xiace_structure.md"}], user_id="yhn")
    b = await fn(k.build_knowledge_graph)(corpus_id=a.corpus_id, depth="full")  # 自动 link subject
    sub = "gaoshuxia"   # = 科目名 slug（见 build 日志）
    st = await fn(t.start_learning_session)(user_id="yhn", subject_id=sub)
    print(st.current_action.content)
    nxt = await fn(t.advance)(st.session_id)            # 讲解→继续
    # ... ask_question 时改用 await fn(t.respond)(st.session_id, "答案")

asyncio.run(run())
```

`scripts/` 下有十几个分层 demo（`demo_full_workflow.py` 是端到端参考）。

---

## 7. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `KG_NOT_BUILT` / `SUBJECT_NOT_FOUND` | 先 `build_knowledge_graph`（它会自动建 Subject + 链 kg_id）；`subject_id` 用科目名 slug |
| 教学只停在第一段讲解 | 讲解步骤要调 **`advance`**，不是 respond；问答步骤才用 respond（见 §3.3） |
| 难度/时长/摸底分带都一个样 | 用了 `depth="concept"`；改 **`depth="full"`** 才有内容驱动的难度/时长/band |
| 概念内容是干巴巴模板 | 没配 `DEEPSEEK_API_KEY`；配上 key 后讲解/反馈走真实 LLM |
| PDF 建不出图谱 | 扫描件无文本层 + 没装 mineru；改喂带标题的 `.md`（见 §2.1） |
| `UNIQUE constraint ... kg_id` | 同 corpus 同 depth 重复 build；删 `data/*.db` 或换 subject/version |
| 面板显示 idle | 当前库没有进行中的会话；先 start_learning_session，或把面板指向有会话的库 |

---

## 8. 一页速查

```
准备:   uv sync --extra research --extra dev → init_db → .env(DEEPSEEK_API_KEY)  # PDF 还需 uv tool install mineru
建图:   acquire_subject(.md/.pdf/web) → build_knowledge_graph(depth=full)   # 自动 link subject
摸底:   cold_start_probe → submit_cold_start
开课:   start_learning_session → [advance(讲解) | respond(问答)] × N → 自动切概念
进度:   get_learning_progress / resume_learning
复习:   learning_insight → generate_review_plan
产物:   digest(formats=[mindmap/notes/quiz/...]) → sync.push_to_obsidian
旁观:   python -m servers.dashboard.server → localhost:8501
```
