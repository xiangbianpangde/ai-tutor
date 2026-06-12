# 接口契约定义 — AITutor V2.0

> 角色：DD-001 | 日期：2026-06-01 | 上游：[AR:API-AITutor-V2.0-20260601] 30 API
> 每个 IC 必须通过 soul 4.12 六项验收

---

## IC-001 GET /health
- **关联接口**：[AR:API-001]
- **入参**：无
- **出参**：`{status: "ok"|"degraded", components: {db, llm, nli}, latency_ms: int}`
- **错误码**：E007 500（内部错误）
- **时序**：同步响应
- **前置条件**：无
- **后置条件**：返回最新健康快照
- **并发安全**：是（只读）
- **幂等性**：是 / 无需幂等键 / N/A
- **性能约束**：≤500ms
- **来源标注**：[AR:API-001] + [SA:BR-030]

## IC-002 POST /v1/middleware/reload
- **关联接口**：[AR:API-002]
- **入参**：`{middleware_name: string, dev_token: string}`
- **出参**：`{status: "reloaded", version: string}`
- **错误码**：E003 403（dev-only）/ E007 500（重载失败）
- **时序**：同步
- **前置条件**：调用方 IP ∈ 127.0.0.1，dev_token 匹配
- **后置条件**：中间件已重新加载，旧实例被替换
- **并发安全**：是（互斥锁保护）
- **幂等性**：否（同 middleware_name 并发重载可能冲突）
- **性能约束**：≤1s
- **来源标注**：[AR:API-002]

## IC-003 GET /v1/openapi.json
- **关联接口**：[AR:API-003]
- **入参**：无
- **出参**：OpenAPI 3.1 JSON Schema
- **错误码**：无（恒 200）
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回完整 OpenAPI 文档
- **并发安全**：是（静态生成）
- **幂等性**：是 / N/A
- **性能约束**：≤200ms
- **来源标注**：[AR:API-003] + [SA:BR-008]

## IC-004 POST /v1/pedagogy/feynman/grade
- **关联接口**：[AR:API-004]
- **入参**：`{user_answer: string(1-10000), question_id: string(UUID), user_id: string}`
- **出参**：`{score: float(0-1), feedback: string, gaps: list[string], trace_id: string}`
- **错误码**：E001 422（输入为空）/ E007 500（LLM 不可用）
- **时序**：同步（30s 超时）
- **前置条件**：用户已登录（user_id 有效）
- **后置条件**：评分已写入 learner_profile
- **并发安全**：是（每用户写锁）
- **幂等性**：是 / 幂等键=question_id+user_id+answer_hash / 24h / 重复返回上次结果
- **性能约束**：≤3s
- **来源标注**：[AR:API-004] + [SA:DE-013/DE-014]

## IC-005 POST /v1/pedagogy/fsrs/schedule
- **关联接口**：[AR:API-005]
- **入参**：`{card_id: string, grade: int(1-4)}`
- **出参**：`{next_due: ISO8601, stability: float, difficulty: float, retry_after: ISO8601|null}`
- **错误码**：E001 422（grade 越界）/ E006 429（AGAIN 风暴）
- **时序**：同步
- **前置条件**：card_id 存在
- **后置条件**：fsrs_cards 表已更新
- **并发安全**：是（按 card_id 写锁）
- **幂等性**：是 / 幂等键=card_id+grade / 5min（AGAIN 风暴窗口）/ 重复返回 retry_after
- **性能约束**：≤100ms
- **来源标注**：[AR:API-005] + [SA:BR-012] + [ADR-006] + [DD洞察-001]

## IC-006 GET /v1/pedagogy/level
- **关联接口**：[AR:API-006]
- **入参**：query `?user_id=string`
- **出参**：`{level: "BEGINNER"|"INTERMEDIATE"|"ADVANCED"|"MASTER", accuracy_7d: float, last_change_at: ISO8601}`
- **错误码**：E004 404（用户不存在）
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回当前阶段（不修改任何数据）
- **并发安全**：是（只读）
- **幂等性**：是 / N/A
- **性能约束**：≤50ms
- **来源标注**：[AR:API-006] + [SA:DE-017/DE-018] + [ADR-009]

## IC-007 GET /v1/pedagogy/break-status
- **关联接口**：[AR:API-007]
- **入参**：query `?user_id=string`
- **出参**：`{elapsed_min: int, recommend_break: bool, suggested_break_min: int}`
- **错误码**：无
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回建议（不强制）
- **并发安全**：是（只读）
- **幂等性**：是 / N/A
- **性能约束**：≤50ms
- **来源标注**：[AR:API-007]

## IC-008 POST /v1/halucheck/verify
- **关联接口**：[AR:API-008]
- **入参**：`{claims: list[{claim_id: string, text: string}], response_text: string(1-50000)}`
- **出参**：`{scores: [{claim_id, nli: float, slm: float, llm: float, final: "PASSED"|"FLAGGED"|"REJECTED"}], overall: float, source: list[string], trace_id: string}`
- **错误码**：E001 422（claims 为空）/ E008 503（LLM 法官全失败）
- **时序**：同步（≤3s P50，≤5s P95）
- **前置条件**：claims 与 response_text 合法
- **后置条件**：评分已写入 hallucination_scores
- **并发安全**：是（只读 + 写）
- **幂等性**：是 / 幂等键=claims 的 hash / 1h / 重复返回上次评分
- **性能约束**：≤5s P95
- **来源标注**：[AR:API-008] + [SA:BR-016~BR-018] + [调研报告:NLI-01]

## IC-009 GET /v1/halucheck/scores/{response_id}
- **关联接口**：[AR:API-009]
- **入参**：path `response_id: string(UUID)`
- **出参**：`{response_id, scores: [...], overall: float, created_at: ISO8601}`
- **错误码**：E004 404（无此 response_id）
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回历史评分（不修改）
- **并发安全**：是（只读）
- **幂等性**：是 / N/A
- **性能约束**：≤200ms
- **来源标注**：[AR:API-009]

## IC-010 POST /v1/pipeline/ingest
- **关联接口**：[AR:API-010]
- **入参**：`{source: "url"|"local", path: string(1-2048), options: dict}`
- **出参**：`{task_id: string(UUID), state: "PENDING"}` (HTTP 202)
- **错误码**：E001 422（path 无效）/ E007 500（采集启动失败）
- **时序**：异步（202 Accepted 立即返回）
- **前置条件**：path 通过白名单校验（SEC-002）
- **后置条件**：pipeline_tasks 表新增一行
- **并发安全**：是
- **幂等性**：是 / 幂等键=path 的 content_hash / 永久（UPSERT）
- **性能约束**：≤1s
- **来源标注**：[AR:API-010] + [SA:DE-023/DE-024] + [ADR-010]

## IC-011 GET /v1/pipeline/status/{task_id}
- **关联接口**：[AR:API-011]
- **入参**：path `task_id: string(UUID)`
- **出参**：`{task_id, state: "PENDING"|"COLLECTING"|...|"COMPLETED"|"FAILED", progress: float(0-1), error: {code, message}|null}`
- **错误码**：E004 404
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回最新状态（不修改）
- **并发安全**：是（只读）
- **幂等性**：是 / N/A
- **性能约束**：≤100ms
- **来源标注**：[AR:API-011]

## IC-012 POST /v1/pipeline/local-sources
- **关联接口**：[AR:API-012]
- **入参**：`{path: string(规范化)}`
- **出参**：`{added: int, sources: list[string]}`
- **错误码**：E001 422（路径含 `..` 等）
- **时序**：同步
- **前置条件**：path 在 data/ 白名单下
- **后置条件**：local_sources 表更新
- **并发安全**：是（写锁）
- **幂等性**：是 / 幂等键=path / 永久 / 重复无副作用
- **性能约束**：≤500ms
- **来源标注**：[AR:API-012] + [SA:CE-016] + [EX-016]

## IC-013 POST /v1/rag/query
- **关联接口**：[AR:API-013]
- **入参**：`{question: string(1-2000), session_id: string, options: {top_k: int(1-20)=5, max_rounds: int(1-5)=5}}` + header `X-Trace-Id: 32hex`
- **出参**：`{answer: string, sources: list[{doc_id, title, url, score}], halu_scores: {...}, ctx_id: string, trace_id: string}`
- **错误码**：E001 422（输入为空）/ E005 408（编排超时）/ E008 503（LLM 全失败）
- **时序**：同步（≤10s P95）
- **前置条件**：session_id 存在
- **后置条件**：rag_contexts 与 cache 已更新
- **并发安全**：是（按 session_id 协调）
- **幂等性**：是 / 幂等键=question+session_id+options_hash / 1h / 重复命中缓存
- **性能约束**：≤10s P95；二次查询 latency 下降 ≥50%（[SA:BR-031]）
- **来源标注**：[AR:API-013] + [SA:BR-019/BR-029/BR-032] + [ADR-005] + [DD洞察-002]

## IC-014 GET /v1/rag/eval/{ctx_id}
- **关联接口**：[AR:API-014]
- **入参**：path `ctx_id: string(UUID)`
- **出参**：`{coverage: float, quality_score: float, sources: list[string], created_at: ISO8601}`
- **错误码**：E004 404
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回评估
- **并发安全**：是（只读）
- **幂等性**：是 / N/A
- **性能约束**：≤200ms
- **来源标注**：[AR:API-014] + [SA:DE-031/DE-032]

## IC-015 GET /v1/sessions
- **关联接口**：[AR:API-015]
- **入参**：query `?user_id=string&limit=int(1-100)=20&offset=int=0`
- **出参**：`{sessions: [{session_id, title, created_at, last_active_at, message_count}], total: int}`
- **错误码**：无
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回会话列表
- **并发安全**：是（只读）
- **幂等性**：是 / N/A
- **性能约束**：≤200ms
- **来源标注**：[AR:API-015] + [SA:DE-033]

## IC-016 POST /v1/sessions/{id}/switch
- **关联接口**：[AR:API-016]
- **入参**：path `id: string(UUID)` + body `{user_id: string}`
- **出参**：`{status: "switched", session_id}`
- **错误码**：E004 404 / E001 422（user_id 不匹配，CE-012）
- **时序**：同步
- **前置条件**：user_id 拥有此 session
- **后置条件**：当前会话切换完成
- **并发安全**：是（每用户单切换）
- **幂等性**：是 / 幂等键=id / 永久 / 重复返回 success
- **性能约束**：≤200ms
- **来源标注**：[AR:API-016] + [CE-012]

## IC-017 GET /v1/memory/long-term
- **关联接口**：[AR:API-017]
- **入参**：query `?user_id=string&limit=int(1-200)=50`
- **出参**：`{facts: [{fact_id, text, importance: float(0-1), created_at, embedding_score: float}], total}`
- **错误码**：E001 422
- **时序**：同步
- **前置条件**：user_id 有效
- **后置条件**：返回长期记忆（user_id 隔离）
- **并发安全**：是（只读 + user_id 强过滤）
- **幂等性**：是 / N/A
- **性能约束**：≤200ms
- **来源标注**：[AR:API-017] + [SA:DE-035] + [CE-012]

## IC-018 POST /v1/sessions/export
- **关联接口**：[AR:API-018]
- **入参**：`{session_id: string, format: "json"|"ndjson"|"markdown"}`
- **出参**：`{export_path: string, size_bytes: int, format}` 或 multipart 下载
- **错误码**：E004 404 / E007 500（JSON 损坏时 EX-036 NDJSON 回退）
- **时序**：同步
- **前置条件**：session_id 存在
- **后置条件**：导出文件已生成
- **并发安全**：是（写锁）
- **幂等性**：是 / 幂等键=session_id+format / 永久 / 重复覆盖
- **性能约束**：≤2s
- **来源标注**：[AR:API-018] + [SA:DE-036] + [EX-036]

## IC-019 POST /v1/research/{subcommand}
- **关联接口**：[AR:API-019]
- **入参**：path `subcommand: "collect"|"deepen"|"clean"|"extract"|"organize"|"backward"` + body `args: dict`
- **出参**：`{task_id, state: "PENDING"}` (202)
- **错误码**：E001 422（subcommand 越界）/ E007 500
- **时序**：异步
- **前置条件**：API Key 已在 env
- **后置条件**：pipeline_tasks 新增
- **并发安全**：是
- **幂等性**：是 / 幂等键=subcommand+args hash / 1h / 重复返回 task_id
- **性能约束**：≤1s
- **来源标注**：[AR:API-019] + [SA:BR-027]

## IC-020 POST /v1/translate/pdf
- **关联接口**：[AR:API-020]
- **入参**：`{file_path: string(白名单下), target_lang: "zh"|"en"|"ja"|...}`
- **出参**：`{translated_path: string, pages: int, duration_ms: int}`
- **错误码**：E001 422 / E005 408（>60s/10 页）/ E008 503（pdf2zh 3 次降级全失败）
- **时序**：同步（≤60s/10 页）
- **前置条件**：DeepSeek API Key 在 env
- **后置条件**：双语 PDF 已生成
- **并发安全**：是
- **幂等性**：是 / 幂等键=file_path+target_lang+content_hash / 永久 / 重复返回相同 path
- **性能约束**：≤60s/10 页
- **来源标注**：[AR:API-020] + [SA:BR-028]

## IC-021 POST /v1/llm/infer
- **关联接口**：[AR:API-021]
- **入参**：`{prompt: string(1-100000), model: "gpt-4o-mini"|"haiku4.5"|"llama3.1-8b", options: {temperature: float(0-2)=0.7, max_tokens: int(1-8192)=2048}}`
- **出参**：`{text: string, model_used: string, tokens_in: int, tokens_out: int, latency_ms: int, provider: string, trace_id: string}`
- **错误码**：E001 422 / E002 401（API Key 缺失）/ E005 408（30s 超时）/ E006 429（限流）/ E008 503（主备切换后仍失败）
- **时序**：同步（30s + 1 次重试）
- **前置条件**：对应 provider API Key 已在 env
- **后置条件**：已写入 audit_log（BR-021 强制）
- **并发安全**：是（Token Bucket 限流 5 QPS/provider）
- **幂等性**：否（LLM 调用天然非幂等）
- **性能约束**：≤30s + 1 重试
- **来源标注**：[AR:API-021] + [SA:BR-027/BR-028/BR-035] + [EX-009/034] + [DD洞察-003]

## IC-022 POST /v1/fsm/match
- **关联接口**：[AR:API-022]
- **入参**：`{input: dict(≤100 字段), context: dict(≤50 字段)}`
- **出参**：`{state: string, transition: {from, to, event, version}, audit_id: string, trace_id: string}`
- **错误码**：E001 422（输入格式错）/ E008 503（audit 写失败）
- **时序**：同步
- **前置条件**：状态机表已加载
- **后置条件**：状态转换已生效，audit_log 已写
- **并发安全**：是（单 FSM 实例写锁）
- **幂等性**：是 / 幂等键=input+context hash / 5min / 重复返回上次 transition
- **性能约束**：≤50ms
- **来源标注**：[AR:API-022] + [SA:BR-020~BR-022] + [ADR-008]

## IC-023 POST /v1/fsm/fallback
- **关联接口**：[AR:API-023]
- **入参**：`{input: dict, llm_response: dict, reason: string}`
- **出参**：`{state: string, audit_id: string, confidence: float}`
- **错误码**：E001 422 / E008 503（audit 写失败阻断兜底）
- **时序**：同步
- **前置条件**：audit_log 写入路径已就绪
- **后置条件**：状态已更新（仅在 audit 成功后）
- **并发安全**：是
- **幂等性**：是 / 幂等键=input hash / 1h / 重复返回上次
- **性能约束**：≤5s（LLM 兜底）
- **来源标注**：[AR:API-023] + [SA:BR-021] + [ADR-008]

## IC-024 GET /v1/fsm/proposals
- **关联接口**：[AR:API-024]
- **入参**：无
- **出参**：`{proposals: [{proposal_id, from_state, to_state, event, weight: float, human_reviewed: bool, created_at}]}`
- **错误码**：无
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回待人工审阅的提案
- **并发安全**：是（只读）
- **幂等性**：是 / N/A
- **性能约束**：≤100ms
- **来源标注**：[AR:API-024] + [SA:BR-022]

## IC-025 WS /ws/status
- **关联接口**：[AR:API-025]
- **入参**：URL query `?token=string&session_id=string` + Origin 头
- **出参**：服务端推送 `{type, payload, trace_id}` 消息
- **错误码**：E003 403（CSWSH 拒绝）/ 心跳超时关闭 / 消息 >64KB 关闭
- **时序**：WebSocket 长连接，30s ping/pong
- **前置条件**：Token 校验通过 + Origin 校验通过（防 CSWSH）
- **后置条件**：连接进入 OPEN 状态
- **并发安全**：是（100 连接上限）
- **幂等性**：N/A（长连接）
- **性能约束**：推送延迟 ≤1s
- **来源标注**：[AR:API-025] + [SA:BR-005] + [EX-024/025] + [调研报告:RI-007]

## IC-026 GET /v1/status.md
- **关联接口**：[AR:API-026]
- **入参**：无
- **出参**：`text/markdown`
- **错误码**：E007 500（写失败阻断推送）
- **时序**：同步
- **前置条件**：STATUS.md 文件存在
- **后置条件**：返回最新状态
- **并发安全**：是（只读 + 原子写保护）
- **幂等性**：是 / N/A
- **性能约束**：≤200ms
- **来源标注**：[AR:API-026] + [SA:DE-040]

## IC-027 POST /v1/anki/generate
- **关联接口**：[AR:API-027]
- **入参**：`{session_id: string, options: {include_feynman: bool=true, include_fsrs: bool=true, deck_name: string}}`
- **出参**：`{apkg_path: string, cards_count: int, anki_pushed: bool, anki_error: string|null}`
- **错误码**：E001 422 / E004 404 / E007 500 / E008 503（Anki-Connect 不可用时 EX-042 仅生成）
- **时序**：同步
- **前置条件**：session_id 存在
- **后置条件**：.apkg 已生成（Anki-Connect 推送可选）
- **并发安全**：是
- **幂等性**：是 / 幂等键=session_id+options hash / 1h / 重复返回相同 path
- **性能约束**：≤5s
- **来源标注**：[AR:API-027] + [SA:DE-042] + [EX-042] + [调研报告:ANK-19]

## IC-028 POST /v1/obsidian/sync
- **关联接口**：[AR:API-028]
- **入参**：`{vault_path: string(白名单下), note_path: string, content: string(≤1MB)}`
- **出参**：`{commit_id: string, file_path: string, throttled: bool}`
- **错误码**：E001 422 / E007 500（git commit 失败）
- **时序**：同步
- **前置条件**：vault_path 在白名单下
- **后置条件**：git commit 完成（每日 ≤1 commit 节流）
- **并发安全**：是（每 vault 单 commit 锁）
- **幂等性**：是 / 幂等键=file_path+content hash / 1d / 重复无副作用
- **性能约束**：≤3s
- **来源标注**：[AR:API-028] + [SA:DE-043]

## IC-029 POST /v1/cli/plugin/install
- **关联接口**：[AR:API-029]
- **入参**：`{plugin_name: string(≤64), source: "pypi"|"local", version: string(可选)}`
- **出参**：`{status: "installed", plugin_name, version, hash: string}`
- **错误码**：E001 422 / E007 500 / E008 503（签名校验失败，V-4 强制）
- **时序**：同步
- **前置条件**：source 可达
- **后置条件**：plugin_registry 已更新
- **并发安全**：是（写锁）
- **幂等性**：是 / 幂等键=plugin_name+version / 永久 / 重复返回 installed
- **性能约束**：≤10s
- **来源标注**：[AR:API-029] + [SA:DE-044/DE-045]

## IC-030 GET / (Web SPA 静态托管)
- **关联接口**：[AR:API-030]
- **入参**：URL path
- **出参**：`text/html` + 静态资源（带 hash 缓存）
- **错误码**：E004 404
- **时序**：同步
- **前置条件**：无
- **后置条件**：返回对应 SPA 路由
- **并发安全**：是（CDN 友好）
- **幂等性**：是 / N/A
- **性能约束**：≤100ms
- **来源标注**：[AR:API-030] + [SA:BP-020-D]
