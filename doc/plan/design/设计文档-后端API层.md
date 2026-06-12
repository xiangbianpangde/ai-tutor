# 设计文档：后端 API 层

> 涉及模块：`backend/api/`、`backend/ws/`、`backend/engines/`（原 `servers/` 4 个 MCP server）

## 背景

当前 4 个 MCP server 各自由 `FastMCP` 框架驱动，tool 通过 `@mcp.tool()` 装饰器暴露。每个 server 是独立进程，通过 stdio/SSE 与 MCP Host 通信。重构后需要：

1. 4 个 server 合并为单一 FastAPI 应用
2. 每个 tool 变为一个 REST endpoint 或 WebSocket 消息类型
3. 保持内部逻辑不变，只改"外壳"

## 目标

- 32 个 tool 完整迁移为 API endpoint，功能不丢失
- 新增 WebSocket 端点用于教学实时通信
- API 设计遵循开发规范：名词复数 + kebab-case、统一 JSON 响应格式
- 现有 672 测试全部适配并通过

## 方案

### Tool → Endpoint 映射

#### knowledge 引擎（9 tool → 9 REST endpoints）

| 原 MCP Tool | Method | Endpoint |
|------------|--------|----------|
| `acquire_subject` | POST | `/api/knowledge/subjects/{id}/acquire` |
| `build_knowledge_graph` | POST | `/api/knowledge/subjects/{id}/graphs` |
| `query_knowledge` | GET | `/api/knowledge/graphs/{id}/query` |
| `review_kg` | GET | `/api/knowledge/graphs/{id}/review` |
| `update_kg` | PATCH | `/api/knowledge/graphs/{id}` |
| `diff_kg` | GET | `/api/knowledge/graphs/diff?a=&b=` |
| `rollback_kg` | POST | `/api/knowledge/subjects/{id}/rollback` |
| `resolve_conflicts` | GET | `/api/knowledge/graphs/{id}/conflicts` |
| `health` | GET | `/api/knowledge/health` |

#### tutoring 引擎（13 tool → REST + WebSocket）

| 原 MCP Tool | 迁移方式 | Method | Endpoint / Message |
|------------|---------|--------|-------------------|
| `cold_start_probe` | REST | POST | `/api/tutoring/subjects/{id}/cold-start/probe` |
| `submit_cold_start` | REST | POST | `/api/tutoring/subjects/{id}/cold-start/submit` |
| `start_learning_session` | REST + WS | POST | `/api/tutoring/sessions` |
| `resume_learning` | REST + WS | POST | `/api/tutoring/sessions/resume` |
| `get_learning_progress` | REST | GET | `/api/tutoring/subjects/{id}/progress` |
| `next_action` | WebSocket | — | `{type: "next_action"}` |
| `advance` | WebSocket | — | `{type: "advance"}` |
| `respond` | WebSocket | — | `{type: "respond", answer: "..."}` |
| `interrupt` | WebSocket | — | `{type: "interrupt", question: "..."}` |
| `checkpoint` | REST | POST | `/api/tutoring/sessions/{id}/checkpoint` |
| `learning_insight` | REST | GET | `/api/tutoring/subjects/{id}/insight` |
| `generate_review_plan` | REST | GET | `/api/tutoring/subjects/{id}/review-plan` |
| `health` | REST | GET | `/api/tutoring/health` |

#### digest 引擎（4 tool → 4 REST endpoints）

| 原 MCP Tool | Method | Endpoint |
|------------|--------|----------|
| `digest` | POST | `/api/digest/generate` |
| `build_quiz_html` | POST | `/api/digest/quiz` |
| `compile_slides` | POST | `/api/digest/slides` |
| `health` | GET | `/api/digest/health` |

#### sync 引擎（6 tool → 6 REST endpoints）

| 原 MCP Tool | Method | Endpoint |
|------------|--------|----------|
| `push_to_obsidian` | POST | `/api/sync/obsidian/push` |
| `pull_homework_from_obsidian` | GET | `/api/sync/obsidian/pull` |
| `init_subject_repo` | POST | `/api/sync/git/init` |
| `push_artifacts` | POST | `/api/sync/git/push` |
| `watch_obsidian` | POST | `/api/sync/obsidian/watch` |
| `health` | GET | `/api/sync/health` |

### WebSocket 教学协议

教学场景用 WebSocket 双向通信。消息格式：

```json
// Client → Server
{"type": "next_action"}
{"type": "advance"}
{"type": "respond", "answer": "极限值等于函数趋近的值"}
{"type": "interrupt", "question": "我不理解ε-δ定义"}

// Server → Client
{"type": "action", "data": {"type": "ask_question", "content": "..."}}
{"type": "result", "data": {"correctness": "correct", "feedback": "..."}}
{"type": "interrupt_result", "data": {"type": "context_aware_answer", "content": "..."}}
{"type": "status", "data": {"cognitive_load": 0.35, "flow": "fluent"}}
{"type": "error", "data": {"code": "SESSION_NOT_FOUND"}}
```

### 统一响应格式

```json
// 成功
{"ok": true, "data": {...}}

// 失败
{"ok": false, "error": {"code": "KG_NOT_FOUND", "hint": "..."}}
```

### FastAPI app 入口结构

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI-Tutor", version="2.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"])  # 本地应用

app.include_router(knowledge_router, prefix="/api/knowledge")
app.include_router(tutoring_router, prefix="/api/tutoring")
app.include_router(digest_router, prefix="/api/digest")
app.include_router(sync_router, prefix="/api/sync")

# WebSocket
@app.websocket("/ws/tutoring/{session_id}")
async def tutoring_ws(websocket, session_id): ...
```

## 影响范围

- `servers/*/server.py`：`@mcp.tool()` 装饰器 → FastAPI route + WebSocket handler
- `shared/`：保持不变，被 `backend/core/` 引用
- `pyproject.toml`：移除 `fastmcp` 依赖，新增 `fastapi`、`uvicorn`、`websockets`
- 现有测试：tool 调用方式变更，需适配。但内部 engine 逻辑测试不受影响

## 风险

| 风险 | 缓解 |
|------|------|
| WebSocket 比 MCP stdio 复杂 | 先实现 REST 版教学（轮询模式），再升级 WebSocket |
| 教学逻辑与通信层耦合 | engine 保持纯函数接口，WS handler 只做序列化/反序列化 |
| 前端未就绪时无法测试 API | 先用 pytest + httpx 测 API，FastAPI 自带 Swagger 可手动调试 |
