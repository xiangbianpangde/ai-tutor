# 文件结构规范 — AITutor V3.1

> 17 模块（M-001~M-017）全有完整文件结构规范（5 项全通过）。
> 来源：[AR:DP-001~007] + [DD推断:依据=Python src layout 最佳实践]

---

## 全局目录结构

```
aitutor/
├── pyproject.toml                # 项目配置（uv 锁版本）
├── .env.example                  # 环境变量模板
├── .env                          # 环境变量（git ignore）
├── .ruff.toml                    # Ruff 规则集
├── .importlinter.toml            # Import Linter 架构边界
├── .redocly.yaml                 # Redocly OpenAPI 规范
├── .pre-commit-config.yaml       # pre-commit hook
├── README.md
├── docs/
│   ├── api/                      # OpenAPI 生成产物
│   ├── architecture/             # 架构文档
│   └── redline/                  # 修复手册
├── src/
│   └── aitutor/                  # 主包
│       ├── __init__.py
│       ├── main.py               # M-001 服务入口
│       ├── config.py             # 配置加载
│       ├── app_factory.py        # FastAPI 工厂
│       ├── api/                  # M-002 API 网关
│       │   ├── __init__.py
│       │   ├── deps.py           # Depends 注入
│       │   ├── auth.py           # Auth 依赖
│       │   ├── rate_limit.py     # 限流
│       │   ├── v1/
│       │   │   ├── __init__.py
│       │   │   ├── session.py    # /session 路由
│       │   │   ├── turn.py       # /turn 路由
│       │   │   ├── ingest.py     # /ingest 路由
│       │   │   ├── health.py     # /health 路由
│       │   │   └── ws.py         # /ws 路由
│       │   └── openapi.py        # OpenAPI 生成
│       ├── clients/              # M-003 客户端入口
│       │   ├── __init__.py
│       │   ├── cli.py            # CLI 入口
│       │   ├── web.py            # Web 入口
│       │   ├── gui/              # GUI 占位（V3.5）
│       │   └── lib.py            # Library 入口
│       ├── session/              # M-004 Session
│       │   ├── __init__.py
│       │   ├── models.py         # Session 实体
│       │   ├── repository.py     # Repository
│       │   ├── state_machine.py  # 状态机
│       │   └── service.py        # 业务逻辑
│       ├── cache/                # M-005 Cache
│       │   ├── __init__.py
│       │   ├── semantic.py       # 语义缓存
│       │   ├── lru.py            # LRU 淘汰
│       │   ├── backend.py        # 双后端
│       │   └── proxy.py          # 缓存代理
│       ├── monitor/              # M-006 事件总线
│       │   ├── __init__.py
│       │   ├── bus.py            # 事件总线
│       │   ├── trace.py          # trace_id
│       │   └── logger.py         # 结构化日志
│       ├── pipeline/             # M-007 Pipeline
│       │   ├── __init__.py
│       │   ├── orchestrator.py   # 调度器
│       │   ├── state.py          # FSM
│       │   ├── stages/
│       │   │   ├── __init__.py
│       │   │   ├── preprocess.py
│       │   │   ├── retrieve.py
│       │   │   ├── rerank.py
│       │   │   ├── llm.py
│       │   │   └── postprocess.py
│       │   └── fallback.py       # 兜底
│       ├── rag/                  # M-008 RAG 引擎
│       │   ├── __init__.py
│       │   ├── engine.py         # 引擎入口
│       │   ├── routing/          # 路由子能力
│       │   │   ├── __init__.py
│       │   │   ├── keyword.py
│       │   │   └── adapter.py
│       │   ├── nli/              # NLI 子能力
│       │   │   ├── __init__.py
│       │   │   ├── scorer.py
│       │   │   └── model.py
│       │   ├── indexing/         # 索引子能力
│       │   │   ├── __init__.py
│       │   │   ├── chroma.py
│       │   │   └── adapter.py
│       │   └── translation/      # 翻译子能力
│       │       ├── __init__.py
│       │       └── adapter.py
│       ├── teaching/             # M-009 教学编排
│       │   ├── __init__.py
│       │   ├── orchestrator.py
│       │   ├── state_machine.py
│       │   └── dispatcher.py
│       ├── feynman/              # M-010 费曼评分
│       │   ├── __init__.py
│       │   ├── scorer.py
│       │   ├── prompt.py
│       │   └── parser.py
│       ├── fsrs/                 # M-011 FSRS
│       │   ├── __init__.py
│       │   ├── scheduler.py
│       │   └── throttle.py
│       ├── stage/                # M-012 阶段校准
│       │   ├── __init__.py
│       │   ├── evaluator.py
│       │   └── transition.py
│       ├── memory/               # M-013 长期记忆
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── repository.py
│       │   ├── lru.py
│       │   └── extractor.py
│       ├── ingest/               # M-014 数据管线
│       │   ├── __init__.py
│       │   ├── pipeline.py
│       │   ├── translate/
│       │   │   ├── __init__.py
│       │   │   ├── pdf2zh.py
│       │   │   ├── pdfplumber.py
│       │   │   └── lmstudio.py
│       │   ├── clean.py
│       │   ├── chunk.py
│       │   └── ingester.py
│       ├── build/                # M-015 打包调度
│       │   ├── __init__.py
│       │   ├── orchestrator.py
│       │   ├── nuitka.py
│       │   ├── upx.py
│       │   └── verifier.py
│       ├── redline/              # M-016 红线编排
│       │   ├── __init__.py
│       │   ├── orchestrator.py
│       │   ├── tools/
│       │   │   ├── __init__.py
│       │   │   ├── ruff.py
│       │   │   ├── import_linter.py
│       │   │   ├── redocly.py
│       │   │   └── precommit.py
│       │   ├── error_hub.py
│       │   └── reports.py
│       ├── storage/              # M-017 存储
│       │   ├── __init__.py
│       │   ├── unit_of_work.py
│       │   ├── sqlite_repo.py
│       │   ├── chroma_repo.py
│       │   ├── file_store.py
│       │   └── migrations/
│       │       ├── __init__.py
│       │       └── v1_initial.py
│       └── shared/               # 横切关注点
│           ├── __init__.py
│           ├── exceptions.py     # 异常类型
│           ├── errors.py         # 错误码
│           ├── types.py          # 类型定义
│           └── utils.py          # 工具函数
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_session/
│   │   ├── test_cache/
│   │   ├── test_pipeline/
│   │   ├── test_rag/
│   │   ├── test_teaching/
│   │   ├── test_feynman/
│   │   ├── test_fsrs/
│   │   ├── test_stage/
│   │   ├── test_memory/
│   │   ├── test_ingest/
│   │   ├── test_build/
│   │   ├── test_redline/
│   │   ├── test_storage/
│   │   └── test_api/
│   ├── integration/
│   │   ├── test_pipeline_e2e.py
│   │   ├── test_ingest_e2e.py
│   │   └── test_api_e2e.py
│   └── fixtures/
│       ├── pdfs/
│       ├── chunks/
│       └── configs/
├── scripts/
│   ├── dev.sh                     # 开发启动
│   ├── build.sh                   # 本地构建
│   └── migrate.py                 # 数据库迁移
└── .github/
    └── workflows/
        ├── redlines.yml           # 红线 CI
        └── release.yml            # 发布 CI
```

---

## 文件命名规则

| 文件类型 | 命名规则 | 示例 |
|---------|---------|------|
| 模块入口 | `__init__.py` | `aitutor/session/__init__.py` |
| 模型定义 | `<module>_models.py` 或 `models.py` | `aitutor/session/models.py` |
| 业务逻辑 | `service.py` 或 `orchestrator.py` | `aitutor/session/service.py` |
| 接口入口 | `<feature>.py` | `aitutor/api/v1/session.py` |
| 状态机 | `state_machine.py` | `aitutor/session/state_machine.py` |
| 适配器 | `adapter.py` | `aitutor/rag/routing/adapter.py` |
| Repository | `repository.py` 或 `<entity>_repo.py` | `aitutor/session/repository.py` |
| 测试文件 | `test_<module>.py` | `tests/unit/test_session/test_models.py` |
| Fixture | `conftest.py`（共享）| `tests/conftest.py` |
| 配置 | `pyproject.toml` / `.env` / `.ruff.toml` | - |

**规则**：
- 全部 snake_case（Python PEP8）
- 模块名不超过 3 词
- 私有成员前缀单下划线（`_internal_helper`）
- 抽象基类前缀 `Base`（`BaseRepository`）

---

## 文件职责矩阵

| 文件 | 职责 | 依赖 |
|------|------|------|
| `main.py` | 服务入口（Uvicorn 启动）| `app_factory` |
| `config.py` | 配置加载（pydantic-settings）| 无 |
| `app_factory.py` | FastAPI 应用工厂 | `api/` + `monitor/` |
| `<module>/service.py` | 业务逻辑（编排 + 流程控制）| `repository` + `models` |
| `<module>/repository.py` | 数据访问 | `storage` + `models` |
| `<module>/models.py` | 实体定义（Pydantic / dataclass）| `shared/types` |
| `<module>/state_machine.py` | 状态转换 | `models` |
| `<module>/adapter.py` | 外部能力封装 | `shared/exceptions` |
| `api/v1/<feature>.py` | HTTP 路由（FastAPI APIRouter）| `service` + `deps` |
| `api/ws.py` | WebSocket 端点 | `monitor/bus` |
| `monitor/bus.py` | 事件总线 | `monitor/trace` |
| `monitor/trace.py` | trace_id 32hex | `shared/types` |
| `redline/orchestrator.py` | 4 工具编排 | `redline/tools/*` |
| `redline/error_hub.py` | 错误聚合 | `shared/errors` |
| `storage/unit_of_work.py` | 事务管理 | `sqlite_repo` + `chroma_repo` + `file_store` |
| `storage/migrations/` | Schema 迁移 | `unit_of_work` |

---

## 文件间依赖关系

### 顶层依赖图

```
main.py
  ↓
app_factory.py
  ↓
api/v1/*  →  api/deps.py  →  api/auth.py
                ↓
          service.py  →  repository.py  →  models.py
                ↓             ↓              ↓
            state_machine  storage/*  shared/types
                ↓             ↓
          monitor/bus  migrations/*
                ↓
          monitor/trace
                ↓
          shared/exceptions
```

### 关键约束（Import Linter 强制）

| 层级 | 允许依赖 | 禁止依赖 |
|------|---------|---------|
| `api/` | `service` + `deps` + `shared` | `repository`（必须经 service）|
| `service.py` | `repository` + `models` + `monitor` | `api`（反向依赖禁止）|
| `repository.py` | `storage` + `models` | `api` + `service` |
| `models.py` | `shared/types` | 任何其他模块 |
| `shared/` | 无 | 任何业务模块（避免循环）|

**违规检测**：`Import Linter` 配置 `.importlinter.toml` 自动检测。

---

## 各模块文件结构（5 项检查全通过）

### M-001 服务入口

```
aitutor/
├── main.py               ← 启动入口
├── config.py             ← 配置加载
└── app_factory.py        ← FastAPI 工厂
```
- 目录层级：3 层 ✅
- 文件命名：snake_case ✅
- 文件职责：明确 ✅
- 依赖关系：main → app_factory → api ✅
- 技术栈最佳实践：src layout ✅

### M-002 API 网关

```
aitutor/api/
├── __init__.py
├── deps.py
├── auth.py
├── rate_limit.py
├── openapi.py
└── v1/
    ├── session.py
    ├── turn.py
    ├── ingest.py
    ├── health.py
    └── ws.py
```
- 目录层级：3 层 ✅
- 文件命名：snake_case + v1/ 版本目录 ✅
- 文件职责：每个文件单一职责 ✅
- 依赖关系：v1/* → deps → service ✅
- 技术栈最佳实践：FastAPI APIRouter 分层 ✅

### M-003 客户端入口

```
aitutor/clients/
├── cli.py
├── web.py
├── lib.py
└── gui/  (V3.5 占位)
```
- 目录层级：2-3 层 ✅
- 文件命名：按形态命名 ✅
- 文件职责：每形态一个文件 ✅
- 依赖关系：clients → service ✅
- 技术栈最佳实践：Facade 模式 + 入口分发 ✅

### M-004 Session

```
aitutor/session/
├── __init__.py
├── models.py
├── repository.py
├── state_machine.py
└── service.py
```
- 目录层级：2 层 ✅
- 文件命名：清晰职责 ✅
- 文件职责：models/repository/state_machine/service 分工 ✅
- 依赖关系：service → repository → models ✅
- 技术栈最佳实践：Repository 模式 + FSM 分离 ✅

### M-005 Cache

```
aitutor/cache/
├── semantic.py
├── lru.py
├── backend.py
└── proxy.py
```
- 目录层级：2 层 ✅
- 文件命名：按策略命名 ✅
- 文件职责：策略分离 ✅
- 依赖关系：proxy → backend/lru/semantic ✅
- 技术栈最佳实践：Proxy 模式 ✅

### M-006 事件总线

```
aitutor/monitor/
├── bus.py
├── trace.py
└── logger.py
```
- 目录层级：2 层 ✅
- 文件命名：简洁 ✅
- 文件职责：bus/trace/logger 三分离 ✅
- 依赖关系：bus → trace/logger ✅
- 技术栈最佳实践：Observer + Mediator ✅

### M-007 Pipeline

```
aitutor/pipeline/
├── orchestrator.py
├── state.py
├── fallback.py
└── stages/
    ├── preprocess.py
    ├── retrieve.py
    ├── rerank.py
    ├── llm.py
    └── postprocess.py
```
- 目录层级：3 层 ✅
- 文件命名：stages/ 子目录 ✅
- 文件职责：5 阶段独立 ✅
- 依赖关系：orchestrator → stages/* ✅
- 技术栈最佳实践：Pipeline 模式 ✅

### M-008 RAG 引擎

```
aitutor/rag/
├── engine.py
├── routing/
│   ├── keyword.py
│   └── adapter.py
├── nli/
│   ├── scorer.py
│   └── model.py
├── indexing/
│   ├── chroma.py
│   └── adapter.py
└── translation/
    └── adapter.py
```
- 目录层级：3 层 ✅
- 文件命名：按子能力命名空间 ✅
- 文件职责：4 子能力清晰隔离 ✅
- 依赖关系：engine → 4 子能力 ✅
- 技术栈最佳实践：策略 + 模板 + 适配器 ✅
- **特殊**：通过子能力命名空间隔离内聚度过低问题（DD 洞察 001）

### M-009 教学编排

```
aitutor/teaching/
├── orchestrator.py
├── state_machine.py
└── dispatcher.py
```
- 目录层级：2 层 ✅
- 文件命名：清晰 ✅
- 文件职责：编排+FSM+分发 ✅
- 依赖关系：orchestrator → state_machine + dispatcher ✅
- 技术栈最佳实践：FSM + Mediator ✅

### M-010 费曼评分

```
aitutor/feynman/
├── scorer.py
├── prompt.py
└── parser.py
```
- 目录层级：2 层 ✅
- 文件命名：清晰 ✅
- 文件职责：评分+Prompt+解析 ✅
- 依赖关系：scorer → prompt + parser ✅
- 技术栈最佳实践：Strategy ✅

### M-011 FSRS

```
aitutor/fsrs/
├── scheduler.py
└── throttle.py
```
- 目录层级：2 层 ✅
- 文件命名：简洁 ✅
- 文件职责：调度+节流 ✅
- 依赖关系：scheduler → throttle ✅
- 技术栈最佳实践：Singleton + Decorator ✅

### M-012 阶段校准

```
aitutor/stage/
├── evaluator.py
└── transition.py
```
- 目录层级：2 层 ✅
- 文件命名：清晰 ✅
- 文件职责：评估+转换 ✅
- 依赖关系：evaluator → transition ✅
- 技术栈最佳实践：Strategy ✅

### M-013 长期记忆

```
aitutor/memory/
├── models.py
├── repository.py
├── lru.py
└── extractor.py
```
- 目录层级：2 层 ✅
- 文件命名：清晰 ✅
- 文件职责：models/repository/lru/extractor 分工 ✅
- 依赖关系：repository → models + lru ✅
- 技术栈最佳实践：Repository + LRU ✅

### M-014 数据管线

```
aitutor/ingest/
├── pipeline.py
├── clean.py
├── chunk.py
├── ingester.py
└── translate/
    ├── pdf2zh.py
    ├── pdfplumber.py
    └── lmstudio.py
```
- 目录层级：3 层 ✅
- 文件命名：translate/ 子目录 + 3 降级后端 ✅
- 文件职责：管线+清洗+分块+入库+翻译 ✅
- 依赖关系：pipeline → translate/clean/chunk/ingester ✅
- 技术栈最佳实践：Template + ThreadPool + 3 次降级 ✅

### M-015 打包调度

```
aitutor/build/
├── orchestrator.py
├── nuitka.py
├── upx.py
└── verifier.py
```
- 目录层级：2 层 ✅
- 文件命名：清晰 ✅
- 文件职责：调度+Nuitka+UPX+校验 ✅
- 依赖关系：orchestrator → nuitka/upx/verifier ✅
- 技术栈最佳实践：Command + Factory ✅

### M-016 红线编排

```
aitutor/redline/
├── orchestrator.py
├── error_hub.py
├── reports.py
└── tools/
    ├── ruff.py
    ├── import_linter.py
    ├── redocly.py
    └── precommit.py
```
- 目录层级：3 层 ✅
- 文件命名：tools/ 子目录 + 4 工具独立 ✅
- 文件职责：编排+工具+错误聚合+报告 ✅
- 依赖关系：orchestrator → tools/* + error_hub ✅
- 技术栈最佳实践：Chain + Observer ✅

### M-017 存储

```
aitutor/storage/
├── unit_of_work.py
├── sqlite_repo.py
├── chroma_repo.py
├── file_store.py
└── migrations/
    ├── __init__.py
    └── v1_initial.py
```
- 目录层级：3 层 ✅
- 文件命名：migrations/ 子目录 + 版本化 ✅
- 文件职责：UoW + 3 后端 + 迁移 ✅
- 依赖关系：UoW → sqlite_repo + chroma_repo + file_store + migrations ✅
- 技术栈最佳实践：Repository + UnitOfWork ✅

---

## 文件结构规范统计

| 指标 | 数量 | 通过率 |
|------|------|--------|
| 模块数 | 17 | - |
| 通过 5 项检查模块 | 17 | 100% |
| 目录层级 | 2-3 层 | 100% |
| 文件命名一致性 | 100% snake_case | 100% |
| 文件间依赖定义 | 17/17 | 100% |
| 符合技术栈最佳实践 | 17/17 | 100% |

来源标注：[AR:DP-001~007] + [DD推断:依据=Python src layout + FastAPI 最佳实践]
