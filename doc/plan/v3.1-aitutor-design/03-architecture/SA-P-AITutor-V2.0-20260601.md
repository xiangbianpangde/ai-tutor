# 系统架构图 - 物理视图 — AITutor V2.0

> 部署形态：单进程 FastAPI 单体 + 桌面壳进程（子进程拉起后端）

## 1. 进程模型

```
┌─────────────────── 桌面壳进程 (Electron/Tauri/PyWebView) ─────────────┐
│  BrowserWindow (contextIsolation=true, sandbox=true, CSP 严格)        │
│  ├─ Renderer 进程 (UI: Vite build)                                    │
│  │    ├─ 看板 / 学习界面 / 向导 / 设置                                │
│  │    └─ WebSocket Client (指数退避重连)                              │
│  └─ Main 进程 (Node/Rust/Python)                                      │
│       ├─ 子进程管理器 → spawn(uv run backend.main:app)                │
│       └─ IPC 转发 (UI ↔ 子进程)                                       │
└──────────────────┬────────────────────────────────────────────────────┘
                   │ localhost:8000 (HTTP) / ws://localhost:8000/ws
┌──────────────────▼─────────── 后端进程 (FastAPI 单进程) ───────────────┐
│  ASGI Loop (uvicorn)                                                  │
│  ├─ Middleware Stack (BR-003 强制 5 类)                               │
│  │    Session → Cache → Monitor → Pipeline → RAG                     │
│  ├─ WebSocket 推送循环 (主进程管连接)                                 │
│  └─ Router (OpenAPI Schema 可见, [BR-008])                            │
│                                                                       │
│  ┌────────── LLM Provider 抽象层 (BR-035 密钥环境变量) ──────────┐  │
│  │  OpenAI / Anthropic / Ollama 三后端，失败降级到更小模型      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌────────── 异步任务 (asyncio.Task) ─────────────────────────────┐  │
│  │  ├─ FSRS 调度 (每 5 分钟扫表)                                  │  │
│  │  ├─ 翻译任务 (并发 5 页/批)                                    │  │
│  │  └─ knowledge graph 实体/关系抽取                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

## 2. 通信协议

| 连接 | 协议 | 端口 | 触发 | 失败处理 |
|------|------|------|------|----------|
| 桌面壳→后端 | HTTP/REST | 8000 | 用户操作 | 指数退避 (1/2/4/8s) |
| 桌面壳→后端 | WebSocket | 8000 | 状态推送 | 心跳 + 自动重连 (EX-025) |
| 浏览器→后端 | HTTP/WS | 8000 | Web 端访问 (F-020) | CORS 白名单 (EX-045) |
| 后端→LLM | HTTPS | 443 | Pipeline step 5 | 30s 超时 + 重试 1 次 (EX-009/034) |
| 后端→pdf2zh | IPC + 文件 | - | 中文 PDF | 失败 3 次降级 LM Studio (BR-028) |
| 后端→Anki | HTTP | 8765 | apkg 导入 (可选) | 端口冲突允许自定义 (CE-017) |

## 3. 运行时线程/协程

| 协程 | 触发 | 频率 | 关键资源 |
|------|------|------|----------|
| FSRS Scheduler | asyncio.create_task | 每 5 分钟 | SQLite fsrs_cards 表 |
| 25min Rest Checker | Monitor 心跳 | 每 1 分钟 | session.start_ts (monotonic) |
| WebSocket Push | 任务完成事件触发 | 实时 | DE-005 连接池 |
| Translation Worker | 用户喂入中文 PDF | 异步 | 并发 5 页/批 |
| 实体抽取 | 文档入库后 | 异步 | LLM 抽取调用 |

## 4. 启动顺序（[SA:BP-001]）

1. 加载 pyproject + .env → 合并配置
2. 校验 SQLite schema 兼容（不兼容走 EX-001 自动迁移）
3. 端口 8000 冲突递增重试 3 次（EX-002）
4. 注册 5 类中间件（[BR-003]）
5. 启动 WebSocket 推送循环
6. 暴露 /health（要求 < 500ms，[BR-030]）
