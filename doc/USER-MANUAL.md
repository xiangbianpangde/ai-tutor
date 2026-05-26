# AI-Tutor 使用手册（详细版）

> 本手册是 [USAGE.md](./USAGE.md)（快速上手）的详细参考版：覆盖安装、环境变量、四个 MCP
> server 的**每一个工具**、三种采集源（含 PDF 翻译与 web 调研）、完整学习闭环、状态面板、
> 复习与产物、Obsidian/Git 同步、直接 Python 驱动与故障排查。
> MCP host 接入配置见 [INTEGRATION.md](./INTEGRATION.md)；生产部署见 [DEPLOYMENT.md](./DEPLOYMENT.md)。

---

## 目录

1. [系统是什么](#1-系统是什么)
2. [安装与依赖](#2-安装与依赖)
3. [环境变量](#3-环境变量)
4. [三种使用方式](#4-三种使用方式)
5. [启动各服务](#5-启动各服务)
6. [完整工作流](#6-完整工作流一份资料到学完一科)
7. [knowledge-mcp 工具全表](#7-knowledge-mcp-知识工程)
8. [tutoring-mcp 工具全表](#8-tutoring-mcp-教学引擎)
9. [digest-mcp 工具全表](#9-digest-mcp-复习产物)
10. [sync-mcp 工具全表](#10-sync-mcp-obsidiangit-同步)
11. [状态面板](#11-状态面板dashboard)
12. [直接 Python 驱动](#12-直接-python-驱动)
13. [故障排查](#13-故障排查)
14. [一页速查](#14-一页速查)

---

## 1. 系统是什么

AI-Tutor 是一个**七层认知架构**的个性化教学系统，把"一份资料"变成"分阶段学完一科 + 个性化复习"。
能力分散在 **4 个 MCP server** + **1 个只读状态面板**：

| 组件 | 职责 | 关键能力 |
|------|------|---------|
| **knowledge-mcp** | L4 知识工程 | 采集（file/PDF/web）→ 建知识图谱 → 人工审查 → 版本管理 → 查询 |
| **tutoring-mcp** | L2/L3/L5/L6 教学引擎 | 冷启动摸底 → 分阶段教学循环 → BKT 追踪 → 错误诊断 → 心流调节 → 复习调度 |
| **digest-mcp** | L7 产物 | 思维导图 / 笔记 / 测验 / 幻灯片 / 音频 / 模拟题 |
| **sync-mcp** | L7 同步 | 推送到 Obsidian、拉作业、Git 仓库同步 |
| **dashboard** | 旁观 | 总览页 + 逐层（8 层）只读可视化 |

数据全部落在**一个 SQLite 库**（默认 `data/tutor.db`），各 server 是独立进程、通过这个库协作。
配了 DeepSeek key → 概念富化 / 判分 / 反馈 / 翻译走真实 LLM；没配 → 全部优雅降级到模板/启发式，**流程照样跑通**。

---

## 2. 安装与依赖

```powershell
cd C:\Users\yhn\Desktop\ai-tutor

# 核心 + 调研(web 采集) + 测试依赖一起装（缺一不可一起 sync，否则会互相卸载）
uv sync --extra research --extra dev

# 建库（或首次调用任意工具时自动建表）
uv run python scripts/init_db.py

# 自检：应 761 passed + 1 skipped
uv run pytest -q
```

### 可选外部 CLI（按需）

| 工具 | 用途 | 安装（隔离，不污染核心 venv） | 不装的后果 |
|------|------|------------------------------|-----------|
| **mineru** | PDF → markdown 抽取（OCR/版面） | `uv tool install mineru` | PDF 源报 `DEPENDENCY_MISSING`；改喂 `.md` 可绕过 |
| **yt-dlp / faster-whisper** | video 源（尚未接入） | 暂不需要 | video 源仍是 stub |

> **为什么 mineru 走独立 CLI 而非 pip 依赖**：它拖 torch 等重依赖，直接装进核心 venv 会
> 拖垮环境。pdf2zh 的**翻译**部分已树内并入（`md_translator`，仅用已有的 openai），不再需要外部 pdf2zh CLI。

---

## 3. 环境变量

写在项目根的 `.env`（已被 `.gitignore` 忽略，不会进版本库）。大小写不敏感。

| 变量 | 作用 | 例子 / 默认 |
|------|------|------------|
| `DEEPSEEK_API_KEY` | LLM：概念富化 / 判分 / 诊断 / 反馈 / **markdown 翻译** | `sk-...`（没配则全程模板/启发式降级） |
| `DEEPSEEK_BASE_URL` | DeepSeek endpoint | 默认 `https://api.deepseek.com` |
| `TAVILY_API_KEY` | web 采集的 Tavily 搜索引擎（可选） | 没配则退到免费 duckduckgo |
| `DATABASE_URL` | 数据库位置 | 默认 `sqlite:///data/tutor.db` |
| `AI_TUTOR_DATA_ROOT` | 文件产物根目录 | 默认 `./data` |
| `MINERU_CMD` | mineru 可执行路径（不在 PATH 时） | 默认走 PATH 的 `mineru` |
| `DASHBOARD_PORT` | 状态面板端口 | 默认 `8501` |

`.env` 示例：
```
deepseek_api_key=sk-xxxxxxxx
deepseek_api_url=https://api.deepseek.com
tavily_api_key=tvly-xxxxxxxx
```

---

## 4. 三种使用方式

| 方式 | 适合 | 怎么驱动 |
|------|------|---------|
| **Claude Desktop / Cursor**（推荐） | 日常学习 | 自然语言让 Claude 调 4 个 server 的工具；配置见 INTEGRATION.md |
| **直接 Python** | 脚本化 / 调试 | `await` 调 `servers.*.server` 里的 tool 函数（见 §12） |
| **状态面板** | 旁观进度 | 浏览器看实时仪表盘（见 §11） |

---

## 5. 启动各服务

每个 MCP server 默认 **stdio**（供 MCP host 拉起）；加 `--transport sse` 起 HTTP 服务：

```powershell
uv run python -m servers.knowledge_mcp.server                 # stdio
uv run python -m servers.knowledge_mcp.server --transport sse # http :8001
uv run python -m servers.tutoring_mcp.server  --transport sse # http :8002
uv run python -m servers.digest_mcp.server    --transport sse # http :8003
uv run python -m servers.sync_mcp.server      --transport sse # http :8004
uv run python -m servers.dashboard.server                     # web  :8501
```

接 Claude Desktop：把 4 个 server 以 stdio 方式写进 `claude_desktop_config.json`（见 INTEGRATION.md），重启 host 即可用自然语言驱动。

---

## 6. 完整工作流（一份资料 → 学完一科）

```
采集 acquire_subject ──► 建图 build_knowledge_graph ──► (审查 review_kg/update_kg)
   │                                                          │
   ├─ file(.md/.txt/.pdf)                                     ▼
   ├─ file(.pdf, translate)  ── mineru→翻译              冷启动 cold_start_probe / submit_cold_start
   └─ web (research-tool)                                     │
                                                              ▼
                              开课 start_learning_session ──► 教学循环 advance / respond ──► 自动切概念
                                                              │
            进度 get_learning_progress / resume_learning ◄────┤
                                                              ▼
                              复习 learning_insight / generate_review_plan
                                                              ▼
                              产物 digest ──► 同步 sync.push_to_obsidian / push_artifacts
```

### 6.1 采集三种源

所有采集都用 `acquire_subject(subject, sources=[...], user_id, version)`，`sources` 每项是一个 dict：

**① 本地文件（markdown / 文本）**——最稳，无外部依赖：
```
acquire_subject(subject="高等数学下册",
                sources=[{"type":"file","uri":"C:/path/gaoshu.md"}], user_id="yhn")
```
markdown 的 `#`/`##`/`###` 标题层级 = 章/节/概念，是建图的骨架。

**② 本地 PDF**——需 `mineru` CLI：
```
# 中文 PDF：直接 mineru 抽 markdown
acquire_subject(subject="高数", sources=[{"type":"file","uri":"book.pdf"}], user_id="yhn")

# 外文 PDF：mineru 抽英文 md → 树内 md_translator 用 DeepSeek 译成中文（保留公式/代码/图片/专名）
acquire_subject(subject="ML教材",
                sources=[{"type":"file","uri":"paper.pdf","translate":"true"}], user_id="yhn")
```
`"translate":"true"` 触发翻译（8 并发分块），译文走你 `.env` 的 DeepSeek key。

**③ web 调研**——用桌面已并入的 research-tool 采集网页正文：
```
acquire_subject(subject="向量空间",
                sources=[{"type":"web","uri":"向量空间 线性代数 入门"}], user_id="yhn")
```
`uri` 是调研主题/关键词。流程 = research-tool 的 collect（duckduckgo/Tavily 搜索 + httpx 抓取）→ clean（清洗正文）→ 合并成一个 markdown 语料。**需联网**（CN 环境多半要代理）；采集到 0 篇 → `CORPUS_NOT_FOUND`。

> 可一次传多个源，全部合并进一个 corpus。`video` 源目前仍是 stub（抛 `DEPENDENCY_MISSING`）。

### 6.2 建图谱

```
build_knowledge_graph(corpus_id=<上一步返回>, depth="full")
→ kg_id, quality_report, mermaid
```

| depth | 内容 | 何时用 | 调 LLM |
|-------|------|--------|--------|
| `toc` | 纯规则抽章节骨架 + part_of/prerequisite_strong 边 | 先看结构 / 没 key | 否（秒级） |
| `concept` | LLM 富化每概念：定义/例子/误解/难度信号 + **12 种语义关系抽取** | 要教学内容 | 是 |
| `full`（推荐） | concept + **时长校准 + 难度校准 + embedding** | 正式学一科 | 是 |

- build 完成会**自动建 `Subject` 行并把 `kg_id` 指过去**，后续教学工具直接用 `subject_id`（= 科目名的拼音 slug，见 build 日志）。
- 质量门会输出告警（章节覆盖率 / 每概念示例 / 类别分布 / 孤立节点 / 低置信），供 `review_kg` 审查。

### 6.3 （可选）人工审查

```
review_kg(kg_id, mode="quick")        → 列低置信概念 + 建议
update_kg(kg_id, actions=[...], mode="versioned")  → 批准/改定义/加删边/合并；versioned 建新版本
resolve_conflicts(kg_id)              → 检测环/反向前置/重复/悬空边/孤岛
```

### 6.4 冷启动摸底（建议先做，省 20–30% 时间）

```
cold_start_probe(user_id="yhn", subject_id=<slug>, num_questions=10)
→ 10 道跨难度摸底题（每题一个 concept）

submit_cold_start(user_id, subject_id, answers=[
  {"concept_id":"...", "answer":"学生回答", "self_report":"sure|unsure|dont_know"}, ...
])
→ 判分 → 种 BKT 先验 + 画像初值；已掌握概念后续自动跳过
```

### 6.5 开课与教学循环

```
start_learning_session(user_id, subject_id, goal="48h_sprint")
→ { session_id, teaching_plan(分 Phase), current_action(首个教学动作), pre_session_insight }
```

每个 action 有 `type`，按它选下一步：

| action.type | 含义 | 下一步 |
|---|---|---|
| `explain` / `show_example` / `reveal_answer` / `reflection` / `show_counter_example` / `pace_feedback` / `break_suggestion` | 讲解/展示（不需作答） | **`advance(session_id)`** |
| `ask_question` / `give_exercise` / `request_explanation` / `provide_hint` | 要学生作答 | **`respond(session_id, answer)`** |

典型一轮：
```
start → explain → advance → show_example → advance → ask_question → respond("学生答案")
      → 判分 + 三级反馈 + BKT 更新 → 概念学完 → next_action 自动切下一个未掌握概念
```

- **策略自动选**：引擎按 mastery / 认知负荷 / 心流 / 画像在 7 种策略里挑（reduction / 降阶法 jiangjie / 费曼 / 苏格拉底 / 类比 / 项目驱动 / 间隔复习），并用心流调节器调难度与脚手架。
- **系统主动动作**：答错触发概念混淆/过度泛化且概念带反例 → `show_counter_example`；认知负荷跨过过载阈值 → `pace_feedback`（主动告知放慢）；回路断裂 → `break_suggestion`。
- `interrupt(session_id, question)` 处理学生打断（自动存断点、分类意图、作答、引导恢复）。
- `checkpoint(session_id, kind)` 保存自我小结 / 测验结果断点。

### 6.6 进度 / 续学 / 复习

```
get_learning_progress(user_id, subject_id)   → 掌握比例 / 各 Phase / 下一个该学的（不开会话）
resume_learning(user_id, subject_id)         → 复用未结束会话，否则从第一个未掌握概念继续
learning_insight(user_id, subject_id)        → 强项/弱项/推荐 focus
generate_review_plan(user_id, subject_id, available_time_today_min=30)
  → 基于个性化遗忘曲线 + 多因子优先级，排今天复习什么、用什么模式
```

### 6.7 产物与同步

```
digest(kg_id, formats=["mindmap","notes","quiz","slides"])  → 复习产物文件
sync.push_to_obsidian(vault_path, subject_id, artifacts=[...])  → 推进 Obsidian 库
```

---

## 7. knowledge-mcp 知识工程

| 工具 | 签名（关键参数） | 说明 |
|------|------------------|------|
| `acquire_subject` | `(subject, sources:[{type,uri,translate?}], user_id="default", version=None)` | 采集 file/PDF/web 语料并落库，返回 corpus_id |
| `build_knowledge_graph` | `(corpus_id, depth="toc"\|"concept"\|"full")` | 建 KG；自动建 Subject + 链 kg_id |
| `review_kg` | `(kg_id, mode="quick"\|"full", limit=20)` | 列低置信概念 + 质量报告 |
| `update_kg` | `(kg_id, actions:[...], mode="in_place"\|"versioned")` | 6 种编辑 op：edit_definition/add_edge/remove_edge/delete/merge/approve |
| `diff_kg` | `(kg_id_a, kg_id_b)` | 按 base_id 对齐对比两版本 |
| `rollback_kg` | `(subject_id, target_kg_id)` | 回退当前 KG 到祖先版本 |
| `resolve_conflicts` | `(kg_id)` | 检测 5 种结构冲突（环/反向/重复/悬空/孤岛） |
| `query_knowledge` | `(kg_id, query, query_type="concept"\|"neighbors"\|"path"\|"subgraph", max_results=10, target=None)` | 查概念/邻居/学习路径/子图 |
| `health` | `()` | DB 可达 + KG 数 |

---

## 8. tutoring-mcp 教学引擎

| 工具 | 签名 | 说明 |
|------|------|------|
| `cold_start_probe` | `(user_id, subject_id, num_questions=10)` | 出跨难度摸底题 |
| `submit_cold_start` | `(user_id, subject_id, answers:[{concept_id,answer,self_report}])` | 判分 → BKT 先验 + 画像初值 |
| `start_learning_session` | `(user_id, subject_id, goal="48h_sprint"\|"semester_study"\|"exam_review"\|"quick_overview")` | 开课，返回 session_id + 首动作 + 计划 |
| `next_action` | `(session_id)` | 拿当前该做的教学动作 |
| `advance` | `(session_id)` | 讲解/展示后"继续下一步" |
| `respond` | `(session_id, answer)` | 提交回答 → 判分 + 反馈 + mastery 变化 + 可能的系统动作 |
| `interrupt` | `(session_id, question)` | 学生打断：存断点 → 意图分类 → 作答 → 引导恢复 |
| `checkpoint` | `(session_id, kind="self_summary"\|"test_result", content=None)` | 保存断点 |
| `get_learning_progress` | `(user_id, subject_id)` | 跨会话进度（不开会话） |
| `resume_learning` | `(user_id, subject_id, goal=...)` | 续学 |
| `learning_insight` | `(user_id, subject_id)` | 学习报告（聚合 BKT + 复习历史） |
| `generate_review_plan` | `(user_id, subject_id, available_time_today_min=60)` | 个性化复习计划 |
| `health` | `()` | DB 可达 + session 数 |

---

## 9. digest-mcp 复习产物

| 工具 | 签名 | 说明 |
|------|------|------|
| `digest` | `(kg_id, formats=["mindmap","quiz"], corpus_id=None, grade="college")` | 生成复习产物。formats 可选：`mindmap`/`notes`/`quiz`/`slides`/`audio`/`simulation`/`multi_agent` |
| `build_quiz_html` | `(kg_id, quiz_count=10, seed=None)` | 单独出可交互测验 HTML |
| `compile_slides` | `(kg_id)` | 出幻灯片（装 python-pptx → .pptx，否则降级自包含 HTML） |
| `health` | `()` | DB 可达 + KG 数 |

---

## 10. sync-mcp Obsidian/Git 同步

| 工具 | 签名 | 说明 |
|------|------|------|
| `push_to_obsidian` | `(vault_path, subject_id, artifacts:[...], subdir="AI-Tutor")` | 把产物写进 Obsidian 库 |
| `pull_homework_from_obsidian` | `(vault_path, subject_id, limit=None)` | 从库里拉学生写的作业/笔记 |
| `init_subject_repo` | `(user_id, subject_id, github_org="my-ai-learning", remote_url=None)` | 初始化科目的 git 仓库 |
| `push_artifacts` | `(subject_id, artifacts:[...], commit_message="...", user_id="default")` | 提交并推送产物到 git |
| `watch_obsidian` | `(vault_path, subject_id, since_iso=None)` | 列出库里自某时刻起变更的文件 |
| `health` | `()` | 自检 |

---

## 11. 状态面板（dashboard）

```powershell
uv run python -m servers.dashboard.server         # 默认读 data/tutor.db
# 指向别的库： 先设 DATABASE_URL=sqlite:///绝对路径.db
```

- **总览页** `http://localhost:8501/` — 4 区每 3 秒刷新：当前概念/心流/策略 · 策略步骤条 · 掌握度分布 + 最近交互 · 48h Phase 进度。
- **逐层页** `http://localhost:8501/layers` — 8 个 Tab 分层只读：
  - **L1** 存储统计（各表行数）；**L2** 会话 + 中断；**L3** 遗忘曲线 + 到期复习 + 复习模式分布；
  - **L4** KG 难度分布 + 关系类型 + **Mermaid 拓扑**；**L5** **BKT 掌握度热力图** + 错误分布 + 认知负荷；
  - **L6** 策略状态机步骤条 + **心流曲线**；**L7** 对话历史；**PGFGA** 心流趋势。
  - 运行时瞬态数据（插件健康/防火墙/SDT/增益事件）诚实标注 `未落库`，不臆造。
- 只读、独立进程，不影响教学。`/api/state` 与 `/api/layer/{L1..L7,pgfga}` 是其 JSON 接口。

---

## 12. 直接 Python 驱动

每个 tool 是 `servers/<x>/server.py` 里被 `@mcp.tool()` 包装的 async 函数；取原函数后 `await`：

```python
import asyncio
from servers.knowledge_mcp import server as k
from servers.tutoring_mcp import server as t

def fn(tool):                       # 取 @mcp.tool 包装前的原函数
    return getattr(tool, "fn", tool)

async def run():
    a = await fn(k.acquire_subject)(
        subject="高数下",
        sources=[{"type": "file", "uri": "examples/gaoshu_xiace_structure.md"}],
        user_id="yhn",
    )
    b = await fn(k.build_knowledge_graph)(corpus_id=a.corpus_id, depth="full")
    subject_id = b.kg_id.split("-")[0]          # 或看 build 日志里的 subject slug
    st = await fn(t.start_learning_session)(user_id="yhn", subject_id=subject_id)
    print(st.current_action.type, st.current_action.content)
    nxt = await fn(t.advance)(st.session_id)    # 讲解→继续；问答步骤改用 respond
    # r = await fn(t.respond)(st.session_id, "学生的回答")

asyncio.run(run())
```

`scripts/` 下有十几个分层 demo，`scripts/demo_full_workflow.py` 是端到端参考。

---

## 13. 故障排查

| 现象 | 原因 / 处理 |
|------|------------|
| `KG_NOT_BUILT` / `SUBJECT_NOT_FOUND` | 先 `build_knowledge_graph`（自动建 Subject + 链 kg_id）；`subject_id` 用科目名 slug |
| 教学只停在第一段讲解 | 讲解步骤调 **`advance`**；问答步骤才 `respond` |
| PDF 报 `DEPENDENCY_MISSING` | 没装 mineru → `uv tool install mineru`；或改喂带标题的 `.md` |
| 外文 PDF 没翻译 | 采集时漏了 `"translate":"true"`；且需 `.env` 有 DEEPSEEK_API_KEY |
| web 采集 `CORPUS_NOT_FOUND` | 网络访问不到 duckduckgo/外站（CN 需代理）；或主题太窄换关键词 |
| markdown 翻译报缺 DeepSeek | `.env` 没配 DEEPSEEK_API_KEY |
| 难度/时长/摸底分带都一个样 | 用了 `depth="concept"`；改 `depth="full"` |
| 概念内容是干巴模板 | 没配 DEEPSEEK_API_KEY；配上走真实 LLM |
| 测试意外变慢/走真实 API | 测试应离线确定性；conftest 已屏蔽 .env 加载——别在测试里手动 `load_env()` |
| `UNIQUE constraint ... kg_id` | 同 corpus 同 depth 重复 build；删 `data/*.db` 或换 subject/version |
| 面板显示 idle | 当前库无进行中会话；先 start_learning_session，或把面板指向有会话的库 |
| `uv sync` 把 pytest/ruff 卸了 | 用 `uv sync --extra research --extra dev`（两个 extra 一起，否则互相卸载） |

---

## 14. 一页速查

```
准备:   uv sync --extra research --extra dev → init_db → .env(DEEPSEEK_API_KEY[, TAVILY_API_KEY])
        PDF 需要: uv tool install mineru
采集:   file:  acquire_subject(sources=[{type:file, uri:x.md|x.pdf}])
        译PDF: acquire_subject(sources=[{type:file, uri:x.pdf, translate:"true"}])
        web:   acquire_subject(sources=[{type:web,  uri:"主题关键词"}])      # 需联网
建图:   build_knowledge_graph(corpus_id, depth=full)                         # 自动 link subject
审查:   review_kg / update_kg(versioned) / resolve_conflicts
摸底:   cold_start_probe → submit_cold_start
开课:   start_learning_session → [advance(讲解) | respond(问答)] × N → 自动切概念
进度:   get_learning_progress / resume_learning
复习:   learning_insight → generate_review_plan
产物:   digest(formats=[mindmap/notes/quiz/slides/...]) → sync.push_to_obsidian
旁观:   python -m servers.dashboard.server → :8501  (总览 / + 逐层 /layers)
```
