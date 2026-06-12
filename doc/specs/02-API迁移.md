# BDD 规格：02 — API 迁移（MCP → REST + WebSocket）

> 对应功能点：#2 | 设计文档：[设计文档-后端API层](../plan/design/设计文档-后端API层.md)

## 功能：32 个 MCP Tool 迁移为 REST API / WebSocket

### 场景 1：knowledge 引擎 — 采集资料
- 前置条件：后端已启动
- 操作步骤：
  1. `POST /api/knowledge/subjects/gaoshu/acquire` body: `{"sources": [{"type": "file", "uri": "mini_subject.md"}]}`
- 预期结果：返回 `{"ok": true, "data": {"corpus_id": "...", "stats": {...}, "artifacts": [...]}}`

### 场景 2：tutoring 引擎 — 开新课
- 前置条件：subject 已有关联 KG
- 操作步骤：
  1. `POST /api/tutoring/sessions` body: `{"user_id": "yhn", "subject_id": "gaoshu"}`
- 预期结果：返回 `{"ok": true, "data": {"session_id": "...", "teaching_plan": {...}, "current_action": {...}}}`

### 场景 3：tutoring 引擎 — WebSocket 教学循环
- 前置条件：已创建 session
- 操作步骤：
  1. 建立 WebSocket `ws://localhost:18501/ws/tutoring/{session_id}`
  2. 发送 `{"type": "next_action"}`
  3. 收到 `{"type": "action", "data": {"type": "ask_question", "content": "..."}}`
  4. 发送 `{"type": "respond", "answer": "学生的回答"}`
  5. 收到 `{"type": "result", "data": {"correctness": "correct", "feedback": "..."}}`
- 预期结果：完整的问答循环无报错，result 包含判分 + mastery 变化

### 场景 4：digest 引擎 — 生成产物
- 前置条件：有已构建的 KG
- 操作步骤：
  1. `POST /api/digest/generate` body: `{"kg_id": "...", "formats": ["mindmap", "quiz"]}`
- 预期结果：返回 task_id，轮询后得到产物文件路径

### 场景 5：sync 引擎 — 推送到 Obsidian
- 前置条件：已配置 Obsidian vault 路径
- 操作步骤：
  1. `POST /api/sync/obsidian/push` body: `{"vault_path": "...", "artifacts": [...]}`
- 预期结果：文件写入 vault 目录，返回写入文件列表

### 场景 6：异常场景 — 会话不存在
- 前置条件：session_id 无效
- 操作步骤：
  1. WebSocket 连接到 `ws://localhost:18501/ws/tutoring/invalid-id`
- 预期结果：返回 `{"type": "error", "data": {"code": "SESSION_NOT_FOUND"}}` 并关闭连接

### 场景 7：异常场景 — KG 未构建
- 前置条件：subject 没有关联 KG
- 操作步骤：
  1. `POST /api/tutoring/sessions` body: `{"user_id": "yhn", "subject_id": "no-kg-subject"}`
- 预期结果：返回 `{"ok": false, "error": {"code": "KG_NOT_BUILT"}}`

### 场景 8：旧版 672 测试适配通过
- 前置条件：所有 MCP tool 已迁移
- 操作步骤：
  1. `uv run pytest tests/ servers/ -x`
- 预期结果：672 测试全部通过（允许少量因 API 签名变更的适配修改）
