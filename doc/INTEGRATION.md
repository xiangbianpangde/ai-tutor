# 接入 Claude Desktop / Cursor — 集成手册

把 4 个 MCP server（knowledge / tutoring / digest / sync）接到 Claude Desktop 或
任意支持 stdio 协议的 MCP host。预计 5 分钟跑通。

## 0. 先决条件

| 项 | 要求 |
|---|---|
| Python | ≥ 3.12 |
| uv | 已装（`uv --version` 不报错）|
| ai-tutor 代码 | 在 `C:/Users/yhn/Desktop/ai-tutor`（如果你的路径不同，下面所有路径都要改）|
| 依赖 | `cd ai-tutor && uv sync --extra dev` 跑过 |
| 数据库 | `uv run python scripts/init_db.py` 跑过（或自动 init_schema）|
| DeepSeek key | `.env` 里有 `DEEPSEEK_API_KEY`（没有也能跑，但 concept/insight/respond 等 LLM 路径会降级到启发式）|

**验证基础设施**：

```powershell
cd C:\Users\yhn\Desktop\ai-tutor
uv run pytest             # 应看到 290+ tests pass
uv run python scripts/verify_servers.py   # 应看到 4 个 [OK]
```

---

## 1. 找 Claude Desktop 配置文件

| OS | 路径 |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json`<br>即 `C:\Users\<你>\AppData\Roaming\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

文件不存在就新建。

## 2. 写配置

把 `examples/claude_desktop_config.example.json` 的 `mcpServers` 段**合并**到上面那个
JSON 文件里。最小可用配置（粘进 JSON 根级）：

```json
{
  "mcpServers": {
    "ai-tutor-knowledge": {
      "command": "uv",
      "args": ["run", "--directory", "C:/Users/yhn/Desktop/ai-tutor",
               "python", "-m", "servers.knowledge_mcp.server"],
      "env": {
        "DATABASE_URL": "sqlite:///C:/Users/yhn/Desktop/ai-tutor/data/tutor.db",
        "AI_TUTOR_DATA_ROOT": "C:/Users/yhn/Desktop/ai-tutor/data",
        "DEEPSEEK_API_KEY": "sk-填你的key"
      }
    },
    "ai-tutor-tutoring": { ... 同结构 ... },
    "ai-tutor-digest":   { ... 同结构 ... },
    "ai-tutor-sync":     { ... 同结构 ... }
  }
}
```

要点：
- 路径用 `/` 或 `\\`，**别用单 `\`**（JSON 会把 `\D` 当转义）
- `DEEPSEEK_API_KEY` 没填也能跑（自动降级）
- `--directory` 让 uv 在正确的工程目录运行（避免找不到 pyproject.toml）

完整模板（4 个 server 全在）见 `examples/claude_desktop_config.example.json`。

## 3. 重启 Claude Desktop

**完全退出**（系统托盘 → Quit），再开。等 10 秒让 4 个 server 启动。

## 4. 验证接入成功

在 Claude Desktop 里：
1. 进任意会话
2. 看输入框下方的工具图标，应该出现 `ai-tutor-knowledge`、`ai-tutor-tutoring`、`ai-tutor-digest`、`ai-tutor-sync` 4 个
3. 让 Claude 调一下 health：

> "调一下 ai-tutor-tutoring 的 health tool"

应返回：
```json
{"ok": true, "server": "tutoring-mcp", "version": "0.1.0", "session_count": 0, "db_url": "sqlite:///..."}
```

## 5. 第一次完整工作流

复制以下 prompt 给 Claude：

> 我要学一份机器学习笔记。流程：
> 1. 先用 sync.pull_homework_from_obsidian 看看我的 vault `C:/Users/yhn/Documents/GitHub/xbpd_obsidian` 里和"机器学习"相关的最近 3 个笔记
> 2. 选一个最新的，调 knowledge.acquire_subject 摄入（type="file"）
> 3. knowledge.build_knowledge_graph(depth="concept") 让 DeepSeek 富化
> 4. knowledge.review_kg(quick) 看低置信概念，必要时 update_kg approve_all
> 5. digest(formats=["mindmap", "notes", "quiz"]) 生成产物
> 6. sync.push_to_obsidian 把产物放回 vault
> 7. 最后调 tutoring.start_learning_session 开教学，把首个 action 给我

Claude 会逐步调用你的 4 个 server，每步把结果摘要返回。

## 6. 不接 Claude Desktop 直接跑

下面这条命令就是 host 编排的"教科书示范"，跑完你能在 SQLite + Obsidian
里看到完整产物：

```powershell
cd C:\Users\yhn\Desktop\ai-tutor
$env:PYTHONIOENCODING="utf-8"
uv run python scripts/demo_full_workflow.py --mock --dry-push
```

加 `--mock` 用 MockLLM 免付费；去掉 `--mock` 用真 DeepSeek；去掉 `--dry-push` 真写到 vault。

## 7. 故障排查

| 现象 | 排查 |
|---|---|
| Claude Desktop 看不到工具 | 重启 / 路径里有中文/空格用引号包 / 改成 `\\` 转义 |
| 提示 "spawn uv ENOENT" | uv 不在 PATH。把 `command` 改成 uv 绝对路径 `C:/Users/<你>/.local/bin/uv.exe` |
| tools/list 报错 | 单独跑 `uv run python -m servers.knowledge_mcp.server` 看 stderr |
| `KG_NOT_BUILT` | 没把 kg_id 写回 subject。让 Claude 先 build_knowledge_graph 再 start_session |
| `PLUGIN_NOT_AVAILABLE` (depth=concept) | DEEPSEEK_API_KEY 未配，或拼写错；用 `Deepseek_API_KEY` / `DEEPSEEK_API_KEY` 都接 |
| 测试和 Claude Desktop 写到不同 db | 检查 `DATABASE_URL` 三处一致：`.env` / Claude config / shell |
| 中文乱码 | `$env:PYTHONIOENCODING="utf-8"` 或在 Claude config 的 env 里加上 |
| `UNIQUE constraint failed: concepts.id` | 同 subject_slug 重跑 build 会冲突；删 `data/tutor.db` 或改 subject |

## 8. 4 个 server / 23 个 tool 速查

### `ai-tutor-knowledge`（L4 知识工程，7 tools）

| Tool | 关键参数 | 返回 |
|---|---|---|
| `acquire_subject` | subject, sources=[{type,uri}], version | corpus_id |
| `build_knowledge_graph` | corpus_id, depth=toc/concept/full | kg_id, quality_report, mermaid |
| `query_knowledge` | kg_id, query, query_type=concept/neighbors | 结果列表 |
| `review_kg` | kg_id, mode=quick/full, limit | 低置信概念 + suggested_actions |
| `update_kg` | kg_id, actions=[KgEditAction] | applied/failed |
| `resolve_conflicts` | kg_id | (stub) |
| `health` | — | ok + kg_count |

### `ai-tutor-tutoring`（L2+L5+L6，8 tools）

| Tool | 关键参数 | 返回 |
|---|---|---|
| `start_learning_session` | user_id, subject_id, goal | session_id + teaching_plan + first action |
| `next_action` | session_id | TeachingAction |
| `respond` | session_id, answer | ResponseResult（含 error_analysis）|
| `learning_insight` | user_id, subject_id | InsightReport |
| `generate_review_plan` | user_id, subject_id, available_time_today_min | DailyReviewPlan |
| `interrupt` | (stub) | — |
| `checkpoint` | (stub) | — |
| `health` | — | ok + session_count |

### `ai-tutor-digest`（L7 多模态产物，2 tools）

| Tool | 关键参数 | 返回 |
|---|---|---|
| `digest` | kg_id, formats=[mindmap\|notes\|quiz\|slides\|audio\|simulation\|multi_agent] | artifacts 列表 |
| `health` | — | ok |

支持的 format：mindmap / notes / quiz 完整；slides / audio / simulation / multi_agent 是 stub（warning 但不中断）。

### `ai-tutor-sync`（Obsidian + GitHub，6 tools）

| Tool | 关键参数 | 返回 |
|---|---|---|
| `push_to_obsidian` | vault_path, subject_id, artifacts, subdir | 写入路径 + 数量 |
| `pull_homework_from_obsidian` | vault_path, subject_id, limit | 笔记列表（按 mtime 倒序）|
| `push_artifacts` (GitHub) | (stub) | — |
| `init_subject_repo` (GitHub) | (stub) | — |
| `watch_obsidian` | (stub) | — |
| `health` | — | ok |

## 9. 推荐工作流

### 4 小时学一份新笔记

```
acquire → build(concept) → review_kg → digest → push_to_obsidian
↓
（在 Obsidian / 浏览器里看笔记和 quiz）
↓
start_session → next_action ↔ respond × N → learning_insight
```

### 跨日复习

```
（隔天）learning_insight → 看 weaknesses
generate_review_plan(30) → 按 review_mode 做练习
respond × N → 累积新 review_history → 下次 plan 更准
```

## 10. 调优

- **LLM 成本**：所有 LLM 调用自动走 LRU 缓存。同 prompt 第二次调用不付费。命中率
  可在 server 日志的 `cache stats` 看到。
- **并发**：每个 MCP server 是单进程；Claude Desktop 把 4 个 server 拉起 4 个进程。
  并发瓶颈在 SQLite 单写。如果觉得慢可以换 PostgreSQL：`DATABASE_URL=postgresql+psycopg://...`。
- **数据隔离**：所有数据在 `data/tutor.db`。给不同用户用不同 `DATABASE_URL` 即可。

## 11. 进一步阅读

- `ROADMAP.md` — 完整切片列表 + 测试覆盖 + 未来计划
- `scripts/demo_full_workflow.py` — 完整 11-step 工作流参考实现
- `../使用AI进行学习的技巧/ai-tutor-状态仪表板.html` — 项目当前状态可视化
- `../使用AI进行学习的技巧/ai-tutor-system-design/` — 完整 v3.0 设计文档
