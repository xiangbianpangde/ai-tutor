# 文件结构规范模板 — AITutor V2.0

> 角色：DD-001 | 日期：2026-06-01 | 上游：[AR:DP] 部署组件 8 个

---

## 通用规范（5 项强制项，所有模块必须满足）

1. **目录层级 ≥ 2 层**：`src/<package>/<module>/` 或 `app/<package>/<module>/`
2. **文件命名规则明确**：snake_case（Python）/ kebab-case（前端）/ PascalCase（类文件）
3. **每个文件有职责定义**：文件头 docstring 含 `[职责：xxx]`
4. **文件间依赖关系已定义**：模块内禁止循环导入；跨模块通过 Protocol/接口
5. **符合技术栈最佳实践**：Python 3.11 + FastAPI + src layout；前端 Vite + 组件目录

---

## FS-001 M-001 启动与中间件
```
src/aitutor/
  __init__.py                       [职责：包入口，导出 app]
  main.py                           [职责：uvicorn 启动入口]
  app.py                            [职责：FastAPI app 构造 + 中间件装配]
  config/
    __init__.py
    settings.py                     [职责：Pydantic Settings 加载 .env]
    secrets.py                      [职责：env 变量读取 + 校验]
  bootstrap/
    __init__.py
    loader.py                       [职责：load_config 函数]
    registry.py                     [职责：MiddlewareRegistry 类]
    health.py                       [职责：HealthChecker / StartupProbe]
    server.py                       [职责：start_ws_server 函数]
  middleware/
    __init__.py
    session.py                      [职责：Session 中间件]
    cache.py                        [职责：Cache 中间件]
    monitor.py                      [职责：Monitor 中间件（trace_id 注入）]
    pipeline.py                     [职责：Pipeline 中间件]
    rag.py                          [职责：RAG 中间件]
  tests/
    test_bootstrap.py
    test_middleware.py
```
- **依赖关系**：`app.py → bootstrap/* → middleware/*`
- **命名规则**：`模块名_files.py` snake_case
- **来源标注**：[AR:DP-001/DP-002] + [AR:TS-001~004] + [调研报告:RI-004]

---

## FS-002 M-002 教学引擎
```
src/aitutor/pedagogy/
  __init__.py
  orchestrator.py                   [职责：PedagogyOrchestrator 门面]
  feynman/
    __init__.py
    scorer.py                       [职责：FeynmanScorer 策略]
  fsrs/
    __init__.py
    scheduler.py                    [职责：FSRSScheduler 策略]
  stage/
    __init__.py
    assessor.py                     [职责：StageAssessor 策略]
  break_check/
    __init__.py
    advisor.py                      [职责：BreakAdvisor 策略]
  recall/
    __init__.py
    recaller.py                     [职责：Recall 策略]
  entities/
    __init__.py
    learner_profile.py              [职责：LearnerProfile 实体]
  tests/
    test_feynman.py
    test_fsrs.py
    test_stage.py
    test_break.py
    test_recall.py
```
- **依赖关系**：`orchestrator.py → strategies/* → entities/*`
- **命名规则**：每个策略一个子包
- **来源标注**：[AR:TS-008/009] + [AR:DE-013~DE-018]

---

## FS-003 M-003 抗幻觉网关
```
src/aitutor/halugate/
  __init__.py
  orchestrator.py                   [职责：HaluGateOrchestrator 门面]
  layers/
    __init__.py
    nli.py                          [职责：NLILayer 推理]
    slm.py                          [职责：SLMLayer]
    llm_judge.py                    [职责：LLMJudgeLayer]
  cascade.py                        [职责：Chain of Responsibility 编排]
  circuit_breaker.py                [职责：CircuitBreaker 保护 LLM 调用]
  warmup.py                         [职责：启动预热 NLI 模型]
  tests/
    test_nli.py
    test_slm.py
    test_llm_judge.py
    test_cascade.py
    test_circuit_breaker.py
```
- **依赖关系**：`orchestrator.py → cascade.py → layers/* + circuit_breaker.py`
- **命名规则**：每级一个文件
- **来源标注**：[AR:TS-011~013] + [调研报告:NLI-01/05/13]

---

## FS-004 M-004 数据管线
```
src/aitutor/pipeline/
  __init__.py
  orchestrator.py                   [职责：DataPipeline 门面]
  steps/
    __init__.py
    collect.py                      [职责：SourceAdapter 采集]
    clean.py                        [职责：DocumentCleaner 清洗]
    ingest.py                       [职责：DocumentRepository 入库]
    chunk.py                        [职责：分块]
    govern.py                       [职责：去重/治理]
  sources/
    __init__.py
    base.py                         [职责：SourceAdapter 抽象]
    arxiv.py                        [职责：arxiv 适配器]
    github.py                       [职责：github 适配器]
    ...（10 个适配器）
  entities/
    __init__.py
    task.py                         [职责：PipelineTask 实体]
  tests/
    test_collect.py
    test_clean.py
    test_ingest.py
    test_chunk.py
    test_govern.py
```
- **依赖关系**：`orchestrator.py → steps/* → sources/*`
- **命名规则**：每步一个文件 + 每源一个文件
- **来源标注**：[AR:TS-017/018] + [调研报告:RI-005/RI-006]

---

## FS-005 M-005 RAG 检索与生成
```
src/aitutor/rag/
  __init__.py
  state_graph.py                    [职责：RAGStateGraph LangGraph 定义]
  nodes/
    __init__.py
    preprocess.py                   [职责：查询规范化节点]
    retrieve.py                     [职责：向量检索节点]
    rerank.py                       [职责：CrossEncoderReranker]
    llm_generate.py                 [职责：LLM 生成节点]
    postprocess.py                  [职责：抗幻觉后处理]
  index/
    __init__.py
    base.py                         [职责：VectorIndex Protocol 抽象]
    sqlite_vec_impl.py              [职责：sqlite-vec 实现]
  cache/
    __init__.py
    rag_cache.py                    [职责：RAGCache Cache-Aside]
  entities/
    __init__.py
    rag_context.py                  [职责：RAGContext 实体]
  tests/
    test_state_graph.py
    test_retrieve.py
    test_rerank.py
    test_postprocess.py
```
- **依赖关系**：`state_graph.py → nodes/* → index/* + cache/*`
- **命名规则**：每节点一个文件
- **来源标注**：[AR:TS-006/009/010] + [AR洞察-004/007]

---

## FS-006 M-006 会话与长期记忆
```
src/aitutor/memory/
  __init__.py
  session/
    __init__.py
    manager.py                      [职责：SessionManager Repository]
    switcher.py                     [职责：SessionSwitcher]
    entities.py                     [职责：Session 实体]
  short_term/
    __init__.py
    buffer.py                       [职责：ShortTermMemory 包装]
  long_term/
    __init__.py
    store.py                        [职责：LongTermMemory Repository]
    entities.py                     [职责：Fact 实体]
  export.py                         [职责：MemoryExporter 导出]
  tests/
    test_session.py
    test_short_term.py
    test_long_term.py
    test_export.py
```
- **依赖关系**：`session/* + short_term/* + long_term/*` 互不依赖，通过 orchestrator 协调
- **命名规则**：每层一个子包
- **来源标注**：[AR:TS-006/009/010] + [AR:DE-033~DE-036]

---

## FS-007 M-007 集成适配器
```
src/aitutor/integrations/
  __init__.py
  llm/
    __init__.py
    base.py                         [职责：LLMProvider Protocol]
    openai_provider.py              [职责：OpenAIProvider 适配器]
    anthropic_provider.py           [职责：AnthropicProvider 适配器]
    ollama_provider.py              [职责：OllamaProvider 适配器]
    rate_limiter.py                 [职责：TokenBucketLimiter]
  research/
    __init__.py
    adapter.py                      [职责：ResearchAdapter 封装 research-tool]
  pdf/
    __init__.py
    adapter.py                      [职责：PDFTranslateAdapter 包装 pdf2zh]
  tests/
    test_openai.py
    test_anthropic.py
    test_ollama.py
    test_rate_limiter.py
    test_research.py
    test_pdf.py
```
- **依赖关系**：`base.py ← openai/anthropic/ollama`，rate_limiter 独立
- **命名规则**：`*_provider.py` / `adapter.py`
- **来源标注**：[AR:TS-014~018] + [调研报告:RI-007]

---

## FS-008 M-008 流程状态机
```
src/aitutor/fsm/
  __init__.py
  state_machine.py                  [职责：StateMachine 类]
  transition_table.py               [职责：TransitionTable dataclass]
  observers.py                      [职责：FSMObservers 列表]
  audit.py                          [职责：AuditLogger]
  fallback.py                       [职责：LLMFallbackOrchestrator]
  version_check.py                  [职责：版本校验]
  entities/
    __init__.py
    state.py                        [职责：State 实体]
  tests/
    test_state_machine.py
    test_transition.py
    test_audit.py
    test_fallback.py
```
- **依赖关系**：`state_machine.py → transition_table.py + observers.py + audit.py + fallback.py`
- **命名规则**：每职责一个文件
- **来源标注**：[AR:TS-010/019] + [SA:BR-020~BR-022]

---

## FS-009 M-009 状态推送
```
src/aitutor/push/
  __init__.py
  ws/
    __init__.py
    server.py                       [职责：WSConnectionManager]
    heartbeat.py                    [职责：HeartbeatScheduler]
    auth.py                         [职责：CSWSH 校验 + Token]
  events/
    __init__.py
    bus.py                          [职责：EventBus 内存发布订阅]
    broadcaster.py                  [职责：Broadcaster Observer]
    schema.py                       [职责：StatusEvent 数据类]
  status_md.py                      [职责：StatusMDWriter 原子写]
  tests/
    test_ws.py
    test_heartbeat.py
    test_event_bus.py
    test_status_md.py
```
- **依赖关系**：`events/* → ws/*`；`status_md.py` 独立
- **命名规则**：每子包一个主题
- **来源标注**：[AR:TS-002/019/020] + [SA:BR-005] + [AR洞察-002]

---

## FS-010 M-010 扩展生态
```
src/aitutor/extensions/
  __init__.py
  anki/
    __init__.py
    exporter.py                     [职责：AnkiExporter 适配器]
  obsidian/
    __init__.py
    syncer.py                       [职责：ObsidianSyncer]
  plugin/
    __init__.py
    loader.py                       [职责：PluginLoader entry_point]
    registry.py                     [职责：PluginRegistry Repository]
  orchestrator.py                   [职责：ExtensionOrchestrator 门面]
  tests/
    test_anki.py
    test_obsidian.py
    test_plugin.py
```
- **依赖关系**：`orchestrator.py → 3 个子包`
- **命名规则**：每出口一个子包
- **来源标注**：[AR:TS-021] + [调研报告:RI-011/RI-012]

---

## FS-011 前端目录（Vue/React 待 PM 决策）
```
web/
  src/
    components/                     [职责：UI 组件]
    views/                          [职责：页面级组件]
    stores/                         [职责：Pinia/Redux 状态]
    api/                            [职责：API 客户端 + TypeScript 类型]
    router/                         [职责：路由]
    main.ts                         [职责：入口]
  public/                           [职责：静态资源]
  vite.config.ts                    [职责：Vite 配置]
  package.json
  tsconfig.json
```
- **命名规则**：kebab-case.tsx / PascalCase.tsx
- **依赖关系**：`main.ts → router/* → views/* → components/* → api/*`
- **来源标注**：[AR:TS-002 前端部分] + [DD推断:基于 Vite + Vue 3 最佳实践]

---

## FS-012 项目根目录
```
.
  pyproject.toml                    [职责：uv + 项目元数据 + 依赖]
  uv.lock                           [职责：uv 锁定]
  .ruff.toml                        [职责：ruff 规则]
  .import-linter                    [职责：import-linter 架构约束]
  .pre-commit-config.yaml           [职责：pre-commit hooks]
  .redocly.yaml                     [职责：OpenAPI lint]
  README.md
  src/                              [职责：源代码]
  tests/                            [职责：跨模块集成测试]
  docs/                             [职责：文档]
  data/                             [职责：运行时数据（gitignore）]
  .env.example                      [职责：环境变量模板]
```
- **来源标注**：[AR:TS-022] + [调研报告:RI-004]
