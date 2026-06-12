# 接口注释清单 — M-007 Pipeline 调度

> 对应模块: M-007
> 关联接口契约: IC-002（学习回合）/ IC-003（RAG 检索）
> 来源标注: [DD-001:IC-002] + [DD-001:IC-003] + [DD-001:MD-M-007]
> 作者: DD-M-007-20260602

---

## 接口清单汇总

| 接口编号 | 接口名称 | 关联契约 | 实现文件 | 函数签名注释 | 参数说明 | 返回值说明 | 错误码说明 |
|---------|---------|---------|---------|------------|---------|-----------|-----------|
| API-M007-001 | 执行 Pipeline 主入口 | IC-002 | orchestrator.py:execute_pipeline | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-002 | query 预处理 | IC-002 | orchestrator.py:preprocess | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-003 | RAG 检索 | IC-003 | orchestrator.py:retrieve | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-004 | 重排序 | 无 | orchestrator.py:rerank | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-005 | LLM 调用 | IC-002 | orchestrator.py:call_llm | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-006 | 答案后处理 | IC-002 | orchestrator.py:postprocess | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-007 | 状态阶段标记 | 无 | state.py:mark_stage | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-008 | 状态机转换 | 无 | state.py:transition_state | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-009 | FSM 卡死检测 | 无 | state.py:is_stuck | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-010 | 兜底触发判定 | 无 | fallback.py:should_fallback | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-011 | 执行兜底 | IC-002 | fallback.py:execute_fallback | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-012 | 写 audit_log | 无 | fallback.py:write_audit | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-013 | Stage 基类 | 无 | stages/preprocess.py:BaseStage | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-014 | 阶段1 执行 | IC-002 | stages/preprocess.py:PreprocessStage.run | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-015 | 阶段1 分词 | 无 | stages/preprocess.py:PreprocessStage.tokenize | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-016 | 阶段1 关键词提取 | 无 | stages/preprocess.py:PreprocessStage.extract_keywords | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-017 | 阶段1 意图识别 | 无 | stages/preprocess.py:PreprocessStage.detect_intent | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-018 | 阶段2 执行 | IC-003 | stages/retrieve.py:RetrieveStage.run | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-019 | 阶段2 RAG 调用 | IC-003 | stages/retrieve.py:RetrieveStage._call_rag | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-020 | 阶段2 结果适配 | 无 | stages/retrieve.py:RetrieveStage._adapt_result | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-021 | 阶段3 执行 | 无 | stages/rerank.py:RerankStage.run | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-022 | 阶段3 NLI 评分 | 无 | stages/rerank.py:RerankStage._nli_score | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-023 | 阶段4 执行 | IC-002 | stages/llm.py:LLMStage.run | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-024 | 阶段4 prompt 构造 | 无 | stages/llm.py:LLMStage._build_prompt | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-025 | 阶段4 Provider 调用 | 无 | stages/llm.py:LLMStage._call_provider | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-026 | 阶段5 执行 | IC-002 | stages/postprocess.py:PostprocessStage.run | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-027 | 阶段5 占位符替换 | 无 | stages/postprocess.py:PostprocessStage._replace_placeholders | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| API-M007-028 | 阶段5 引用源段落 | IC-002 | stages/postprocess.py:PostprocessStage._build_sources_section | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |

**接口总数：28 / 28 全部注释化（D4=100%）**

---

## 关键契约映射

### IC-002 学习回合 → M-007 函数映射

| IC-002 字段 | M-007 实现 |
|------------|-----------|
| 入参 session_id | execute_pipeline 参数 |
| 入参 user_id | 由 M-002 网关注入 session 上下文 |
| 入参 query | execute_pipeline 参数 |
| 出参 answer | PipelineResult.answer（来自 postprocess 阶段） |
| 出参 sources | PipelineResult.sources（来自 postprocess 阶段） |
| 出参 fsm_fallback | PipelineResult.fsm_fallback（来自 fallback） |
| 出参 trace_id | state.trace_id |
| 错误码 E00704 | execute_pipeline 触发 |
| 错误码 E00702 | execute_fallback 触发 |
| 性能约束 P95≤5s | execute_pipeline 总耗时 |
| 幂等键 request_id | execute_pipeline 入口参数 |

### IC-003 RAG 检索 → M-007 函数映射

| IC-003 字段 | M-007 实现 |
|------------|-----------|
| 入参 query | retrieve 参数（来自 QueryFeatures.keywords） |
| 入参 top_k=5 | RetrieveStage.top_k |
| 出参 top_k_chunks | retrieve 返回值 |
| 出参 route_decision | 通过 state 传递 |
| 错误码 E00705 | RetrieveStage.run 触发 |
| 错误码 E00801 | retrieve 阶段 NLI 不达标触发 |
| 错误码 E00803 | RetrieveStage._call_rag 重路由失败触发 |
| 性能约束 P95≤10s | retrieve 阶段耗时 |

---

## 来源标注

[DD-001:IC-002 出参字段行] + [DD-001:IC-003 出参字段行] + [DD-001:MD-M-007 函数签名行] + [DD-M推断:依据=8 接口契约→28 函数映射]
