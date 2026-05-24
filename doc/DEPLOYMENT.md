# 部署文档 — DEPLOYMENT

面向运维 / 几个月后的自己。讲**怎么把 4 个 MCP server 跑起来并长期维护**：传输形态、环境变量、可选依赖、数据目录与备份、数据库、故障排查、安全。

> 想「5 分钟接进 Claude Desktop」看 [INTEGRATION.md](./INTEGRATION.md)。本文是它的上位补充：生产 / 多机 / HTTP / 备份。

---

## 1. 两种传输形态

每个 server（`servers/<name>_mcp/server.py`）的 `main()` 都支持两种 transport：

| 形态 | 启动 | 适用 |
|---|---|---|
| **stdio**（默认） | `uv run python -m servers.knowledge_mcp.server` | 本机，MCP host 直接拉起子进程（Claude Desktop 走这个） |
| **HTTP / SSE** | `... server --transport http` | 远程 / 多机 / 多 host 共享同一后端 |

HTTP 模式监听 `0.0.0.0`，固定端口：

| server | 模块 | HTTP 端口 |
|---|---|---|
| knowledge-mcp | `servers.knowledge_mcp.server` | **8001** |
| tutoring-mcp | `servers.tutoring_mcp.server` | **8002** |
| digest-mcp | `servers.digest_mcp.server` | **8003** |
| sync-mcp | `servers.sync_mcp.server` | **8004** |

四个一起起（HTTP 模式，后台）：

```powershell
cd C:\Users\yhn\Desktop\ai-tutor
foreach ($s in "knowledge","tutoring","digest","sync") {
  Start-Process -NoNewWindow uv -ArgumentList "run","python","-m","servers.${s}_mcp.server","--transport","http"
}
```

> `0.0.0.0` 会监听所有网卡——见 §8 安全。本机自用建议留 stdio。

---

## 2. 环境变量清单

所有 server 通过环境变量读配置（`.env` 会被自动加载，cwd 或父目录均可；key 大小写不敏感）。

| 变量 | 默认 | 作用 | 谁用 |
|---|---|---|---|
| `DATABASE_URL` | `sqlite:///<cwd>/data/tutor.db` | 数据库连接串 | 全部 |
| `AI_TUTOR_DATA_ROOT` | `<cwd>/data`（resolve） | 产物 / 语料 / 输出根目录 | knowledge, digest |
| `AI_TUTOR_GIT_ROOT` | `<cwd>/data/git_repos` | sync git 仓库根 | sync |
| `DEEPSEEK_API_KEY` | （无） | LLM key；缺失则 LLM 路径降级到启发式/模板 | knowledge, tutoring, digest |
| `MINERU_CMD` | （无 → 找 PATH） | PDF→Markdown 的 mineru 命令路径 | knowledge（仅 PDF 源） |

`.env.example` 是模板；`copy .env.example .env` 后填 `DEEPSEEK_API_KEY`。

> **多机/HTTP 部署强约束**：所有 server 必须指向**同一个** `DATABASE_URL` 和 `AI_TUTOR_DATA_ROOT`，否则 knowledge 建的 KG，tutoring/digest 读不到。SQLite 跨机不可行 → 见 §4。

---

## 3. 可选依赖（按需装）

核心功能零重依赖即可跑。要解锁「升级版」产物再装：

```powershell
# pyproject extras
uv sync --extra dev          # 测试（pytest 全家桶 + ruff）
uv sync --extra vector       # chromadb + sentence-transformers（向量索引）
uv sync --extra research     # 复用 ../调研/research-tool 作采集后端

# 软探测依赖（不在 pyproject，单独装；装了就自动升级产物）
uv pip install python-pptx   # digest slides → 真 .pptx（否则自包含 HTML）
uv pip install edge-tts      # digest audio → 真 .mp3（否则朗读讲稿 .md）
```

判断「现在装了哪些」：

```powershell
uv run python -c "import importlib.util as u; [print(n, u.find_spec(n) is not None) for n in ['pptx','edge_tts','chromadb']]"
```

缺失时的降级行为见 [README.md](./README.md) §7 表格。

---

## 4. 数据库

**默认 SQLite**（`data/tutor.db`）——单机、零运维、够私人用。建表：

```powershell
uv run python scripts/init_db.py
# server 首次访问也会自动 init_schema（幂等）
```

**迁移到 PostgreSQL**（多机 / HTTP 模式必须）：

1. 装驱动：`uv pip install "psycopg[binary]"`
2. 设 `DATABASE_URL=postgresql+psycopg://user:pwd@host:5432/aitutor`
3. 建表：`uv run python scripts/init_db.py`（SQLAlchemy 2.0，同一套 models）
4. 所有 server 用同一串。

> schema 演进有 alembic（`uv run alembic upgrade head`）；早期切片改 schema 时直接重建过 `tutor.db`，生产环境改用 alembic 迁移别手删。

---

## 5. 数据目录与备份

`AI_TUTOR_DATA_ROOT`（默认 `data/`）布局：

```
data/
├── tutor.db                 SQLite 主库（KG / 会话 / BKT / 记忆 / 审计）
├── corpus/                  采集的原始语料（md / 转换后文本）
├── output/digest/<kg_id>/   各 KG 的复习产物（mindmap/notes/quiz/slides/...）
└── git_repos/<org>__<user>-<subject>/   sync 的本地 git 仓库（学习产物带版本史）
```

**备份**：
- 最小集：`tutor.db`（所有结构化状态）。SQLite 直接复制文件即可（先停 server 或用 `.backup`）。
- 完整集：整个 `data/`（含产物与 git 仓库）。
- `git_repos/` 本身就是版本历史；配了 GitHub remote 的话 `push_artifacts(push_remote=True)` 已是异地备份。

---

## 6. 健康检查与冒烟

```powershell
# 4 个 server 能否起 + tools/list 响应
uv run python scripts/verify_servers.py        # 期望 4 个 [OK]

# 全量测试
uv run pytest                                   # 期望 461 passed

# 单 server 健康（每个 server 都有 health tool）
#   HTTP 模式下也可对 SSE 端点发 tools/call health
```

每个 server 的 `health` 返回 `{ok, server, version, kg_count|..., db_url}`，可接监控。

---

## 7. 故障排查

| 症状 | 多半原因 | 处理 |
|---|---|---|
| `KG_NOT_FOUND` / 跨 server 读不到数据 | 各 server `DATABASE_URL` / `DATA_ROOT` 不一致 | 统一环境变量；多机用 Postgres |
| `no such column ...` | schema 变了但库是旧的 | `alembic upgrade head`；开发期可重建 `tutor.db` |
| LLM 路径返回启发式/模板结果 | 没配 `DEEPSEEK_API_KEY` | 填 `.env`；或接受降级（concept/respond/multi_agent 都有 fallback） |
| PDF 源报错 | 找不到 `mineru` | 设 `MINERU_CMD` 指向可执行文件；或先把 PDF 转好喂 md |
| slides 出的是 HTML 不是 pptx | 没装 python-pptx | `uv pip install python-pptx`（或接受 HTML） |
| audio 没 mp3 只有 .md | 没装 edge-tts / 无网络 | `uv pip install edge-tts`；注意 edge-tts 走微软在线服务 |
| git 同步中文 commit 乱码/报错 | Windows GBK 控制台 | 已在 `git_sync._run` 用 bytes+utf-8 规避；若复现检查该处 |
| Claude Desktop 看不到 tool | 配置路径/JSON 格式 | 见 INTEGRATION.md；确认 `uv run --directory` 路径正确 |

日志：structlog 输出到 stderr（MCP host 一般会收集）。排查时直接命令行起 server 看输出。

---

## 8. 安全注意

- **HTTP 模式监听 `0.0.0.0`**：会暴露在局域网/公网。仅自用请用 stdio；要远程务必加反向代理 + 认证 + 防火墙，别裸暴露 8001-8004。
- **`DEEPSEEK_API_KEY` 只进 `.env`**，`.env` 不提交版本库（确认 `.gitignore`）。
- **GitHub push**：`init_subject_repo(remote_url=...)` 若把 token 写进 https URL，注意该 URL 会进 git remote 配置；优先用 credential helper。
- **digest HTML 产物**：概念内容来自 LLM/你的笔记，内联进 `<script>` 的 JSON 已转义 `</`（防 XSS）。但产物 HTML 仍是「本地打开」用途，别当可信网页对外托管。

---

## 9. 升级 / 重装

```powershell
# 拉新代码后
uv sync --extra dev          # 同步依赖
uv run alembic upgrade head  # 迁移 schema（如有）
uv run pytest                # 确认没回归
uv run python scripts/verify_servers.py
```

接 Claude Desktop 的配置改动后，**重启 Claude Desktop** 才会重新拉起 server 子进程。
