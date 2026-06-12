# 接口技术规范 — AITutor V2.0

> 角色：AR-001
> 日期：2026-06-01
> 上游：TD-001 30 个 IF（IF-001 ~ IF-030）
> 覆盖率：30/30 = 100%（D4 = 100%）

---

## 一、接口技术规范总览

| 接口 | 关联模块 | 协议 | 序列化 | 认证 | 限流 | 版本策略 |
|------|---------|------|--------|------|------|---------|
| API-001 | M-001 | REST | JSON | 无（本地） | 1000 QPS | URL v1 |
| API-002 | M-001 | REST | JSON | 无 | 10 QPS | URL v1 |
| API-003 | M-001 | REST | OpenAPI 3.1 | 无 | 100 QPS | URL v1 |
| API-004 ~ 007 | M-002 | REST | JSON | 无 | 50 QPS | URL v1 |
| API-008 ~ 009 | M-003 | REST | JSON | 无 | 30 QPS（计算密集） | URL v1 |
| API-010 ~ 012 | M-004 | REST | JSON | 无 | 5 QPS（采集） | URL v1 |
| API-013 ~ 014 | M-005 | REST | JSON | 无 | 10 QPS（编排） | URL v1 |
| API-015 ~ 018 | M-006 | REST | JSON | 无 | 100 QPS | URL v1 |
| API-019 ~ 021 | M-007 | REST | JSON | API Key（env） | 5 QPS/provider | URL v1 |
| API-022 ~ 024 | M-008 | REST | JSON | 无 | 100 QPS（FSM） | URL v1 |
| API-025 | M-009 | WebSocket | JSON | Token（CSWSH 防） | 100 连接 | 协议 v1 |
| API-026 | M-009 | REST | text/markdown | 无 | 50 QPS | URL v1 |
| API-027 ~ 029 | M-010 | REST | JSON | 无 | 10 QPS | URL v1 |
| API-030 | M-010 | REST | text/html | 无 | 100 QPS | URL v1 |

---

## 二、接口详表（按 3.4 模板）

### API-001 GET /health
- **关联契约**：[TD:IF-001]
- **协议**：REST
- **序列化**：JSON
- **认证**：无（健康检查）
- **限流策略**：1000 QPS（健康检查高频）
- **版本策略**：URL v1（无版本变化）
- **兼容性矩阵**：
  - v1.0 | v1.0 | v1.0 | 完全兼容
  - 升级路径：无
- **错误处理**：HTTP 200 / 503（服务不可用时）；无业务错误码
- **性能要求**：响应时间 ≤500ms（[SA:BR-030]）
- **来源标注**：[TD:IF-001] + [SA:BR-030]

### API-002 POST /v1/middleware/reload
- **关联契约**：[TD:IF-002]
- **协议**：REST
- **序列化**：JSON `{middleware_name: string}`
- **认证**：dev-only（仅 127.0.0.1 + dev token）
- **限流策略**：10 QPS（重载操作低频）
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0 ↔ v1.0 完全兼容
- **错误处理**：200 成功 / 403 dev-only 拒绝 / 503 重载失败
- **性能要求**：响应时间 ≤1s
- **来源标注**：[TD:IF-002]

### API-003 GET /v1/openapi.json
- **关联契约**：[TD:IF-003]
- **协议**：REST
- **序列化**：OpenAPI 3.1
- **认证**：无
- **限流策略**：100 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0 锁定 OpenAPI 3.1
- **错误处理**：200 成功
- **性能要求**：响应时间 ≤200ms
- **来源标注**：[TD:IF-003] + [SA:BR-008]

### API-004 POST /v1/pedagogy/feynman/grade
- **关联契约**：[TD:IF-004]
- **协议**：REST
- **序列化**：JSON `{user_answer, question_id, user_id}`
- **认证**：无（本地）
- **限流策略**：50 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0 稳定
- **错误处理**：200 + score / 422 输入校验失败 / 500 LLM 不可用
- **性能要求**：响应时间 ≤3s（LLM 评分）
- **来源标注**：[TD:IF-004] + [SA:DE-013/DE-014]

### API-005 POST /v1/pedagogy/fsrs/schedule
- **关联契约**：[TD:IF-005]
- **协议**：REST
- **序列化**：JSON `{card_id, grade (1-4)}`
- **认证**：无
- **限流策略**：50 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0 锁定 grade 1-4 枚举
- **错误处理**：200 + next_due / 422 grade 越界 / 429 AGAIN 风暴（5min/卡 [ADR-006]）
- **性能要求**：响应时间 ≤100ms（py-fsrs 计算）
- **来源标注**：[TD:IF-005] + [SA:BR-012] + [ADR-006]

### API-006 GET /v1/pedagogy/level
- **关联契约**：[TD:IF-006]
- **协议**：REST
- **序列化**：JSON `{level, accuracy_7d, last_change_at}`
- **认证**：无
- **限流策略**：50 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0 ↔ v1.0
- **错误处理**：200
- **性能要求**：≤50ms（SQLite 单查询）
- **来源标注**：[TD:IF-006] + [SA:DE-017/DE-018] + [ADR-009]

### API-007 GET /v1/pedagogy/break-status
- **关联契约**：[TD:IF-007]
- **协议**：REST
- **序列化**：JSON `{elapsed_min, recommend_break: bool}`
- **认证**：无
- **限流策略**：50 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200
- **性能要求**：≤50ms
- **来源标注**：[TD:IF-007]

### API-008 POST /v1/halucheck/verify
- **关联契约**：[TD:IF-008]
- **协议**：REST
- **序列化**：JSON `{claims: [...], response_text}`
- **认证**：无
- **限流策略**：30 QPS（计算密集）
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 + scores[] / 422 输入为空 / 503 LLM 法官全部失败
- **性能要求**：响应时间 ≤3s（P50），≤5s（P95，BR-018）
- **来源标注**：[TD:IF-008] + [SA:BR-016~BR-018] + [调研报告:NLI-01]

### API-009 GET /v1/halucheck/scores/{response_id}
- **关联契约**：[TD:IF-009]
- **协议**：REST
- **序列化**：JSON
- **认证**：无
- **限流策略**：30 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 / 404
- **性能要求**：≤200ms（SQLite 查询）
- **来源标注**：[TD:IF-009]

### API-010 POST /v1/pipeline/ingest
- **关联契约**：[TD:IF-010]
- **协议**：REST
- **序列化**：JSON `{source: "url|local", path, options}`
- **认证**：无
- **限流策略**：5 QPS（采集低频）
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：202 + task_id / 422 路径无效 / 500 采集失败
- **性能要求**：≤1s（异步任务入队）
- **来源标注**：[TD:IF-010] + [SA:DE-023/DE-024]

### API-011 GET /v1/pipeline/status/{task_id}
- **关联契约**：[TD:IF-011]
- **协议**：REST
- **序列化**：JSON `{state, progress, error?}`
- **认证**：无
- **限流策略**：5 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 / 404
- **性能要求**：≤100ms
- **来源标注**：[TD:IF-011]

### API-012 POST /v1/pipeline/local-sources
- **关联契约**：[TD:IF-012]
- **协议**：REST
- **序列化**：JSON `{path: "..."}`
- **认证**：无
- **限流策略**：5 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 / 422 路径无效（含特殊字符 EX-016 规范化）
- **性能要求**：≤500ms
- **来源标注**：[TD:IF-012] + [SA:CE-016]

### API-013 POST /v1/rag/query
- **关联契约**：[TD:IF-013]
- **协议**：REST
- **序列化**：JSON `{question, session_id?, options}`
- **认证**：无（本地）；trace_id 32 hex 透传
- **限流策略**：10 QPS（编排密集）
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 + answer / 408 超时 / 422 输入为空 / 503 LLM 全失败
- **性能要求**：响应时间 ≤10s（P95）；二次查询 latency 下降 ≥50%（[SA:BR-031]）
- **来源标注**：[TD:IF-013] + [SA:BR-019/BR-029/BR-032] + [ADR-005]

### API-014 GET /v1/rag/eval/{ctx_id}
- **关联契约**：[TD:IF-014]
- **协议**：REST
- **序列化**：JSON `{coverage, quality_score, sources: [...]}`
- **认证**：无
- **限流策略**：10 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 / 404
- **性能要求**：≤200ms
- **来源标注**：[TD:IF-014] + [SA:DE-031/DE-032]

### API-015 ~ 018 (M-006 会话记忆)
- **API-015** GET /v1/sessions → JSON `{sessions: [...]}`
- **API-016** POST /v1/sessions/{id}/switch → JSON 200
- **API-017** GET /v1/memory/long-term → JSON `{facts: [...]}`
- **API-018** POST /v1/sessions/export → JSON `{export_path}` / multipart 下载
- **关联契约**：[TD:IF-015/016/017/018]
- **协议**：REST
- **序列化**：JSON
- **认证**：无
- **限流策略**：100 QPS（CRUD）
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 / 404 / 422 / 500（JSON 损坏 EX-036 NDJSON 回退）
- **性能要求**：≤200ms
- **来源标注**：[TD:IF-015~018] + [SA:DE-033~DE-036]

### API-019 ~ 021 (M-007 集成适配器)
- **API-019** POST /v1/research/{subcommand} → JSON `{subcommand: collect/deepen/clean/extract/organize/backward}`
- **API-020** POST /v1/translate/pdf → JSON `{file_path, target_lang}`
- **API-021** POST /v1/llm/infer → JSON `{prompt, model, options}`
- **关联契约**：[TD:IF-019/020/021]
- **协议**：REST
- **序列化**：JSON
- **认证**：API Key 来自环境变量（不入请求体）[SA:BR-035]
- **限流策略**：5 QPS/provider（LLM）；10 QPS（research/pdf）
- **版本策略**：URL v1
- **兼容性矩阵**：
  - LLM Provider：v1.0 OpenAI 1.40+ / Anthropic 0.39+ / Ollama 0.4+
  - 升级路径：v1.0 → v1.1 自动 SDK 升级；v1.x → v2.0 需双写过渡期
- **错误处理**：200 / 401 密钥缺失 / 429 限流 / 503 主备切换后仍失败
- **性能要求**：LLM 30s 超时 + 1 次重试（EX-009/034）；pdf 翻译 ≤60s/10 页
- **来源标注**：[TD:IF-019/020/021] + [SA:BR-027/BR-028/BR-035]

### API-022 ~ 024 (M-008 状态机)
- **API-022** POST /v1/fsm/match → JSON `{input, context}` → `{state, transition}`
- **API-023** POST /v1/fsm/fallback → JSON `{input, llm_response}` → `{state, audit_id}`
- **API-024** GET /v1/fsm/proposals → JSON `{proposals: [...]}`
- **关联契约**：[TD:IF-022/023/024]
- **协议**：REST
- **序列化**：JSON
- **认证**：无
- **限流策略**：100 QPS（FSM 匹配）
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0 + version 字段
- **错误处理**：200 / 422 输入格式错 / 503 audit 写失败阻断兜底
- **性能要求**：匹配 ≤50ms；兜底 ≤5s（LLM）
- **来源标注**：[TD:IF-022/023/024] + [SA:BR-020~BR-022] + [ADR-008]

### API-025 WS /ws/status
- **关联契约**：[TD:IF-025]
- **协议**：WebSocket（[SA:BR-005]）
- **序列化**：JSON `{type: "status_update", payload: {...}, trace_id}`
- **认证**：CSWSH 防护 + Token 校验（[SA:BR-005]）
- **限流策略**：100 连接
- **版本策略**：协议 v1（消息 schema 不变）
- **兼容性矩阵**：v1.0 ↔ v1.0
- **错误处理**：心跳超时 30s 关闭；消息大小限制 64KB
- **性能要求**：推送延迟 ≤1s（[SA:BR-005]）
- **来源标注**：[TD:IF-025] + [SA:BR-005] + [调研报告:RI-007]

### API-026 GET /v1/status.md
- **关联契约**：[TD:IF-026]
- **协议**：REST
- **序列化**：text/markdown
- **认证**：无
- **限流策略**：50 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 / 500（写失败阻断推送）
- **性能要求**：≤200ms
- **来源标注**：[TD:IF-026] + [SA:DE-040]

### API-027 ~ 029 (M-010 扩展)
- **API-027** POST /v1/anki/generate → JSON `{session_id, options}` → `{apkg_path}`
- **API-028** POST /v1/obsidian/sync → JSON 200 + `{commit_id}`
- **API-029** POST /v1/cli/plugin/install → JSON `{plugin_name}` → 200
- **关联契约**：[TD:IF-027/028/029]
- **协议**：REST
- **序列化**：JSON
- **认证**：无
- **限流策略**：10 QPS
- **版本策略**：URL v1
- **兼容性矩阵**：v1.0
- **错误处理**：200 / 422 / 500 / 503（Anki-Connect 不可用 EX-042 仅生成 .apkg）
- **性能要求**：≤5s
- **来源标注**：[TD:IF-027~029] + [SA:DE-042~DE-045] + [调研报告:RI-011/RI-012]

### API-030 GET / (Web SPA 静态托管)
- **关联契约**：[TD:IF-030]
- **协议**：REST
- **序列化**：text/html + 静态资源
- **认证**：无
- **限流策略**：100 QPS
- **版本策略**：URL v1（资源带 hash 缓存）
- **兼容性矩阵**：v1.0
- **错误处理**：200 / 404
- **性能要求**：≤100ms（CDN 友好）
- **来源标注**：[TD:IF-030] + [SA:BP-020-D]

---

## 三、通用错误码规范

| 错误码 | HTTP | 含义 | 触发场景 |
|--------|------|------|---------|
| E000 | 200 | 成功 | - |
| E001 | 422 | 输入校验失败 | Pydantic 校验失败 |
| E002 | 401 | 凭证缺失 | BR-035 密钥缺失 |
| E003 | 403 | 权限不足 | dev-only 入口被外部访问 |
| E004 | 404 | 资源不存在 | session_id / task_id 无效 |
| E005 | 408 | 超时 | LLM 30s / pdf 60s |
| E006 | 429 | 限流 | AGAIN 风暴 / LLM QPS 超限 |
| E007 | 500 | 内部错误 | 未捕获异常 |
| E008 | 503 | 服务不可用 | LLM 全失败 / NLI 加载失败 |

---

## 四、限流策略汇总

| 限流类型 | 触发条件 | 策略 |
|---------|---------|------|
| QPS 限流 | API 全局 | 按 API 单独配置（见 §一） |
| 突发限流 | LLM provider | 5 QPS/provider 令牌桶（capacity=10） |
| 并发限流 | LLM 总数 | ≤10 并发 |
| 业务限流 | AGAIN 风暴 | 5min/卡 1 次（ADR-006） |
| 重试限流 | LLM 失败 | 1 次（EX-009） |
| WS 限流 | 连接数 | 100 连接 / 64KB 消息 |

---

## 五、可观测性要求

所有 API 必须满足：
- **trace_id**：32 hex 透传（[SA:BR-004]）
- **span_id**：进入时生成，跨 Agent 串联
- **结构化日志**：structlog JSONL 输出（[TS-019]）
- **OTel 上报**：OTLP 协议（[TS-020]）
- **P95 延迟监控**：在 Monitor 中间件统一埋点

---

## 六、AR 洞察

### [AR-洞察-009] LLM 限流令牌桶参数依据
TS-014/015/016 LLM 三角定价显示 Haiku/GPT-4o-mini 单价低，**真正瓶颈是 provider 速率限制**（OpenAI Tier 1: 500 RPM，Anthropic: 50 RPM）。建议令牌桶 capacity=10、refill_rate=5/s，可保证 95% 流量不被限流同时不超 provider 配额。[AR推断:provider 速率限制]
