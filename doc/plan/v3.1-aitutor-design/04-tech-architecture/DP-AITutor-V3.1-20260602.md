# 部署架构图 — AITutor V3.1

> 单进程单服务器部署，V4.0 预留多服务扩展点。

---

## 一、部署拓扑

```
┌────────────────────────────────────────────────────┐
│  用户桌面 / 笔记本（开发机）                          │
│  ┌──────────────────────────────────────────────┐  │
│  │  AITutor V3.1 单进程                          │  │
│  │  ┌─────────────┐ ┌─────────────┐             │  │
│  │  │ CLI (M-003) │ │ GUI (V3.5)  │             │  │
│  │  └──────┬──────┘ └──────┬──────┘             │  │
│  │  ┌──────┴──────────────┴──────┐              │  │
│  │  │   FastAPI 0.115 (Uvicorn)   │              │  │
│  │  │   ASGI:8000 (loopback)       │              │  │
│  │  │   ┌──────────────────────┐   │              │  │
│  │  │   │ 5 类中间件强制装配    │   │              │  │
│  │  │   │ M-004 Session        │   │              │  │
│  │  │   │ M-005 Cache (SQLite) │   │              │  │
│  │  │   │ M-006 Monitor (OTel) │   │              │  │
│  │  │   │ M-007 Pipeline       │   │              │  │
│  │  │   │ M-008 RAG Engine     │   │              │  │
│  │  │   └──────────────────────┘   │              │  │
│  │  │   ┌──────────────────────┐   │              │  │
│  │  │   │ 业务模块 M-002/003/  │   │              │  │
│  │  │   │ 009~014/016/017      │   │              │  │
│  │  │   └──────────────────────┘   │              │  │
│  │  │   ┌──────────────────────┐   │              │  │
│  │  │   │ LLM Provider (外部)   │   │              │  │
│  │  │   │ OpenAI/Anthropic/    │   │              │  │
│  │  │   │ Ollama/LM Studio     │   │              │  │
│  │  │   └──────────────────────┘   │              │  │
│  │  └──────────────┬───────────────┘              │  │
│  │  ┌──────────────┴───────────────┐              │  │
│  │  │ M-017 存储                   │              │  │
│  │  │ ~/.<app>/data.db (SQLite)    │              │  │
│  │  │ ~/.<app>/chroma/  (ChromaDB) │              │  │
│  │  │ ~/.<app>/files/   (PDF/图片) │              │  │
│  │  │ ~/.<app>/.pre-commit-cache/ │              │  │
│  │  └──────────────────────────────┘              │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  浏览器（Web 入口） http://localhost:8000/web │  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘

外部依赖（仅 loopback / 远端 LLM）：
- LLM Provider（OpenAI/Anthropic/Ollama/LM Studio，HTTPS）
- NLI 模型（本地进程内 lazy load，1.5GB）
- pdf2zh（本地 Python 库）
- ChromaDB（嵌入式）
- GitHub Actions（CI 触发打包 / 红线检测）
```

---

## 二、部署组件清单

### DP-001 AITutor 主进程

- **对应模块**：M-001~M-017
- **运行环境**：本地 / Docker（CI 测试）
- **资源配置**：CPU 2-4 核 / 内存 4-8GB / 存储 10GB（含模型）
- **配置管理**：
  - `pyproject.toml`（uv 锁版本）
  - `.env`（`OPENAI_API_KEY` / `REDIS_URL` / `NLI_MODEL_PATH` / `CLIENT_GUI`）
  - `~/.config/aitutor/config.toml`（用户级配置）
- **依赖组件**：LLM Provider / NLI 模型 / pdf2zh 依赖
- **启动顺序**：1（系统启动时）
- **健康检查**：`GET /health` → 200 OK（启动 ≤30s 后）
- **监控告警**：Prometheus scrape `/metrics`（CPU/内存/请求/WS 连接数/缓存命中/pipeline FSM 兜底率）
- **来源标注**：[TD:SA-P-AITutor] + [TD:SA-D-AITutor]

### DP-002 LLM Provider（外部）

- **对应模块**：AG-007/AG-008/AG-010 LLM 调用
- **运行环境**：云端 SaaS（OpenAI/Anthropic）/ 本地（Ollama/LM Studio）
- **资源配置**：外部管理
- **配置管理**：`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` 环境变量
- **依赖组件**：网络可达
- **启动顺序**：依赖（主进程启动后调用）
- **健康检查**：httpx 调用 health endpoint
- **监控告警**：LLM 调用 p99 / 兜底率 / 错误码分布
- **来源标注**：[TD:B-003] + [调研报告:RI-001]

### DP-003 NLI 模型

- **对应模块**：AG-008 (M-008 NLI 子能力)
- **运行环境**：进程内 lazy load
- **资源配置**：CPU 1 核 / 内存 1.5GB（HuggingFace transformers）
- **配置管理**：`NLI_MODEL_PATH` / `NLI_MODEL_NAME`（默认 `MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`）
- **依赖组件**：模型文件本地存在
- **启动顺序**：首次 RAG 请求时 lazy load
- **健康检查**：模型加载成功 + 推理 p99 ≤2s
- **监控告警**：NLI 加载时长 / NLI 推理 p99 / LLM 兜底占比
- **来源标注**：[调研报告:RI-009/NLI-01/05/13] + [TD:SR-005]

### DP-004 SQLite 数据库

- **对应模块**：M-017 主存
- **运行环境**：本地文件（embedded）
- **资源配置**：WAL 模式 + 100MB 上限
- **配置管理**：`DATABASE_URL=sqlite+aiosqlite:///~/<app>/data.db`
- **依赖组件**：文件系统
- **启动顺序**：2（5MW 装配时）
- **健康检查**：`PRAGMA integrity_check` 启动期一次
- **监控告警**：数据库大小 / 写锁等待时间
- **来源标注**：[TD:DE-001~048] + [调研报告:RI-010]

### DP-005 ChromaDB

- **对应模块**：M-008 RAG 检索 + M-014 数据入库
- **运行环境**：嵌入式（PersistentClient）
- **资源配置**：CPU 0.5 核 / 内存 1GB / 存储 5GB
- **配置管理**：`CHROMA_PERSIST_DIR=~/.<app>/chroma`
- **依赖组件**：文件系统
- **启动顺序**：3（5MW 装配时）
- **健康检查**：`heartbeat()` API + 集合计数
- **监控告警**：HNSW 查询 p99 / 集合大小
- **来源标注**：[TD:DE-026/037] + [调研报告:RI-008]

### DP-006 GitHub Actions（CI）

- **对应模块**：M-015 打包 + M-016 红线编排
- **运行环境**：GitHub-hosted runner
- **资源配置**：3 平台矩阵（ubuntu-latest / windows-latest / macos-latest）
- **配置管理**：`.github/workflows/{redlines.yml,release.yml}`
- **依赖组件**：GitHub Secrets
- **启动顺序**：4（PR push / tag 触发）
- **健康检查**：workflow exit code
- **监控告警**：CI 失败率 / 4 工具退出码分布
- **来源标注**：[TD:DE-046/047/048] + [TD:ADR-010]

### DP-007 Prometheus（可选 / 监控）

- **对应模块**：M-006 → AG-018
- **运行环境**：Docker / 本地二进制
- **配置管理**：`prometheus.yml`（scrape_interval=15s）
- **启动顺序**：5（主进程启动后 scrape）
- **健康检查**：`/-/healthy`
- **监控告警**：Grafana dashboard
- **来源标注**：[调研报告:RI-013]

---

## 三、配置管理

### 3.1 环境分层

| 环境 | 用途 | 配置来源 |
|------|------|---------|
| dev | 本地开发 | `.env.development` |
| test | CI 跑测试 | GitHub Actions env |
| prod | 用户桌面 | `.env`（用户编辑）|

### 3.2 关键配置项

| Key | Default | 说明 |
|-----|---------|------|
| `OPENAI_API_KEY` | - | 必填（云端 LLM）/ 选填（Ollama） |
| `REDIS_URL` | `""` | 空 = SQLite 默认 / 非空 = Redis 后端 |
| `NLI_MODEL_PATH` | `~/.<app>/models/nli` | NLI 模型本地路径 |
| `CLIENT_GUI` | `cli` | cli / tauri / electron / pywebview（V3.5 决策） |
| `LOG_LEVEL` | `INFO` | structlog 级别 |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `""` | 空 = 本地日志 / 非空 = OTLP 导出 |
| `DATABASE_URL` | `sqlite+aiosqlite:///~/<app>/data.db` | 主存 |

---

## 四、启动顺序

```
1. OS 启动（systemd / 开机自启 / 用户双击）
   ↓
2. Uvicorn 启动 → 加载 pyproject.toml + .env
   ↓
3. M-001 服务入口：5MW 装配（Session/Cache/Monitor/Pipeline/RAG）
   ↓
4. M-002 API 网关挂载 → 启动 HTTP 监听（loopback:8000）
   ↓
5. M-003 客户端入口（CLI 立即可用 / Web 浏览器访问 / GUI 启动 / 库 import）
   ↓
6. M-006 事件总线：Prometheus scrape 就绪
   ↓
7. 主进程就绪 ← 健康检查返回 200
```

**总启动时长 ≤30s**（[TD:PC-AITutor:启动时间]）

---

## 五、健康检查与监控

### 5.1 健康检查端点

| 端点 | 用途 | 触发 |
|------|------|------|
| `GET /health` | 进程存活 | systemd / Docker |
| `GET /ready` | 5MW 装配完成 | K8s readinessProbe |
| `GET /metrics` | Prometheus scrape | Prom 15s interval |
| `WS /ws` | 客户端连接 | 用户主动 |

### 5.2 关键监控指标

| 指标 | 类型 | 阈值 | 告警 |
|------|------|------|------|
| `aitutor_cpu_usage` | Gauge | > 80% | WARN |
| `aitutor_memory_bytes` | Gauge | > 6GB | WARN |
| `aitutor_ws_connections` | Gauge | > 800/1000 | WARN |
| `aitutor_request_duration_seconds` | Histogram | p99 > 5s | WARN |
| `aitutor_cache_hit_rate` | Gauge | < 30% | WARN |
| `aitutor_pipeline_fsm_fallback_rate` | Gauge | > 15% | WARN |
| `aitutor_nli_inference_seconds` | Histogram | p99 > 2s | WARN |
| `aitutor_pdf_translation_seconds` | Histogram | p95 > 60s | WARN |
| `aitutor_artifact_size_bytes` | Gauge | CLI > 50MB / GUI > 200MB | WARN（不阻塞） |
| `aitutor_ci_duration_seconds` | Histogram | p95 > 5min | WARN |

来源标注：[TD:PC-AITutor] + [调研报告:RI-013]

---

## 六、依赖与外部服务

| 依赖 | 类型 | 必需 | 降级策略 |
|------|------|------|---------|
| LLM Provider (云端) | HTTPS API | 否（可用本地替代）| 切到 Ollama |
| LLM Provider (本地) | HTTP loopback | 否（可用云端替代）| - |
| NLI 模型 | 文件系统 | 是 | 降级 LLM 法官 |
| pdf2zh 依赖 | PyPI | 是 | pdfplumber → LM Studio 3 次降级 |
| ChromaDB | PyPI | 是 | 无降级（核心依赖）|
| SQLite | 系统库 | 是 | 无降级（核心依赖）|
| GitHub Actions | SaaS | 否（可本地跑测试）| 本地 pre-commit |
| Prometheus | 可选 | 否 | 不影响主流程 |
