# 系统架构图-物理视图 — AITutor V3.1

> 视角：架构师 / 开发工程师
> 部署形态：单进程单容器为主 + 桌面/CLI 进程外调用

---

## 一、运行时进程拓扑

```
[ai-tutor serve]                       [ai-tutor doctor / make / dvc]
        │                                       │
        ▼                                       ▼
┌──────────────────────────┐          ┌──────────────────┐
│ FastAPI 单进程 (PID 1)   │          │ 短命 CLI 进程     │
│ ├─ Uvicorn 监听 8000     │          │ ├─ ruff          │
│ ├─ L4 路由 + Auth        │          │ ├─ import-linter │
│ ├─ L3 编排 5 模块(线程)   │          │ ├─ redocly       │
│ ├─ L2 领域 3 模块(线程)   │          │ ├─ pre-commit    │
│ ├─ L1 5 中间件(模块对象)   │          │ └─ pytest --cov  │
│ ├─ LLM 客户端(httpx 异步)│          └──────────────────┘
│ ├─ NLI 客户端(本地推理)   │
│ ├─ WebSocket Hub(后台循环)│
│ └─ Redline 闸门(进程内钩) │
└──────────────────────────┘
        │  ┌─────────────────┐
        ├─►│ LM Studio(本地) │ 备用
        │  └─────────────────┘
        ▼
[SQLite data/tutor.db]      [data/chroma/]        [data/obsidian-vault/]
 [ChromaDB]                  [meta/FILE_GRAPH.md]  [api/openapi.yaml]
```

来源标注：[SA:BP-001] + [SA:BR-002] + [SA:BR-006] + [SA:EX-005/EX-018]

---

## 二、模块-进程映射

| 模块 | 进程内形式 | 线程模型 | 资源占用 |
|------|----------|---------|---------|
| M-001 服务入口 | 协程 | asyncio | CPU 低 / IO 中 |
| M-002 API 网关+WS | 协程 | asyncio | IO 高 |
| M-003 客户端入口 | 外部进程 / Web 静态 | - | 独立 |
| M-004 Session MW | 协程 | asyncio | CPU 中 |
| M-005 Cache MW | 协程 | asyncio | IO 中 |
| M-006 监控事件总线 | 协程 + 装饰器 | asyncio Queue | 极低 |
| M-007 Pipeline MW | 协程 | asyncio | 编排 |
| M-008 RAG 引擎 | 协程 + 线程池(LLM/NLI/翻译) | async + ThreadPool | IO 高 |
| M-009 教学编排 | 协程 | asyncio | CPU 中 |
| M-010 费曼评分 | 协程 + LLM 客户端 | async | CPU 高 |
| M-011 FSRS 调度 | 协程 | asyncio | CPU 中 |
| M-012 阶段校准 | 协程 | asyncio | 极低 |
| M-013 会话编排 | 协程 | asyncio | CPU 中 |
| M-014 数据管线 | 线程池 | ThreadPool(IO+CPU) | IO 中 |
| M-015 打包调度 | 外部进程调用(Nuitka/Tauri) | 同步子进程 | CPU 高 |
| M-016 红线编排+治理 | 外部进程调用(4 工具) | 同步子进程 | CPU 中 |
| M-017 存储 | 文件 + sqlite-vec | 同步 | IO 中 |

来源标注：[TD推断:依据=单进程 asyncio + ThreadPool 混合模型] + [SA:BR-002]

---

## 三、通信协议

| 边界 | 协议 | 端口/文件 | 安全 |
|------|------|---------|------|
| CLI/GUI → 后端 | HTTP REST + WebSocket | 127.0.0.1:8000 | token / loopback |
| Web → 后端 | HTTP REST + WebSocket | 8000 | token + CSP |
| 后端 → LLM | HTTPS(httpx async) | 443 | API key 环境变量 |
| 后端 → NLI | 本地 HTTP / 进程内 | 8001(本地) | loopback |
| 后端 → LM Studio | HTTP | 1234 | loopback |
| 后端 → SQLite | 文件 IO | data/*.db | 文件权限 600 |
| 后端 → Chroma | 文件 IO | data/chroma/ | 文件权限 |
| CI → 后端 | GitHub Actions YAML | workflow 文件 | secrets |

来源标注：[SA:BR-036 默认认证] + [SA:BR-038 日志脱敏] + [SA:BR-039 SQL 参数化]

---

## 四、关键性能约束（落地到进程）

| 指标 | 进程内应对 | 来源 |
|------|----------|------|
| WS 推送延迟 ≤ 1s | M-002 协程直推 + 心跳 5s | [SA:BR-007] |
| PDF 翻译 10 页 ≤ 60s | M-014 线程池 + 3 次降级 | [SA:BR-021] + [SA:EX-018] |
| 50 轮 token 增长 <30% | M-013 摘要压缩 + LRU | [SA:BR-008] + [SA:BR-029] |
| 红线 CI 全绿 ≤ 5min | M-016 并行 4 工具 | [SA:BR-046/049] |
| NLI 重检索 3 轮上限 | M-008 NLI 子模块循环计数 | [SA:BR-018] |
| 缓存命中率监控 | M-005 + M-006 埋点 | [SA:BR-005] |
| LLM 兜底 10% 节流 | M-009 FSM 计数 | [SA:BR-009] |

来源标注：[SA:BR-005/007/008/009/018/021/029/046/049] + [SA:EX-001~EX-033]
