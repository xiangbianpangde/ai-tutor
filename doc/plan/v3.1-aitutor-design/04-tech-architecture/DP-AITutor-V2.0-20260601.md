# 部署架构图 — AITutor V2.0

> 角色：AR-001
> 日期：2026-06-01
> 上游：TD-001 SA-D 部署视图 + 性能容量预判表
> 状态：单机部署 + 跨平台打包 + 容器化预留

---

## 一、部署拓扑（用户本地单机）

```
┌────────── 单台用户机器（Win/Mac/Linux）─────────────────────┐
│                                                              │
│  ┌─ DP-001 桌面壳 (GUI) ────────────────────────────┐     │
│  │  electron-builder / tauri build / cx_Freeze 集成  │     │
│  │  体积: Electron ≤250MB / Tauri ≤50MB (BR-037)     │     │
│  │  BrowserWindow: contextIsolation=true, sandbox=   │     │
│  │  true, CSP 严格, IPC 转发                          │     │
│  └──────────────┬────────────────────────────────────┘     │
│                 │ 子进程 spawn (uv run main:app)             │
│  ┌──────────────▼────────────────────────────────────┐     │
│  │  DP-002 Backend Single Process (uvicorn)          │     │
│  │  端口: 8000 (冲突递增 EX-002)                       │     │
│  │  资源: 内存 200-500MB / CPU 单核即可               │     │
│  │  ASGI Loop: Session→Cache→Monitor→Pipeline→RAG   │     │
│  └──────────────┬────────────────────────────────────┘     │
│                 │ 本地文件 IO                                │
│  ┌──────────────▼────────────────────────────────────┐     │
│  │  DP-003 本地存储 (data/)                          │     │
│  │  ├─ tutor.db (SQLite + WAL 模式)                   │     │
│  │  ├─ logs/YYYY-MM-DD/structlog.jsonl + OTel         │     │
│  │  ├─ obsidian-vault/ (可选)                          │     │
│  │  ├─ research-cache/ (原始文档)                      │     │
│  │  ├─ knowledge_graph/*.jsonl                         │     │
│  │  ├─ nli_cache/ (DeBERTa-v3-large-mnli ONNX)        │     │
│  │  ├─ documents/*.md (PDF 解析后)                    │     │
│  │  └─ STATUS.md (原子写)                              │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  可选外部依赖（首次/在线时）:                                │
│  ├─ DP-004 LLM Provider (OpenAI / Anthropic / Ollama)       │
│  ├─ DP-005 pdf2zh DeepSeek 翻译 API                         │
│  ├─ DP-006 Anki-Connect (localhost:8765)                     │
│  └─ DP-007 research-tool 10 个外部源                         │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、部署组件详表（按 3.5 模板）

### DP-001 Desktop Shell
- **对应模块**：M-001/M-010
- **运行环境**：本地 GUI 进程
- **资源配置**：Electron 200MB RAM / Tauri 50MB RAM / PyWebView 30MB RAM
- **配置管理**：.env + pyproject（共享 DP-002）
- **依赖组件**：DP-002 必须就绪（启动后 spawn）
- **启动顺序**：第 1 步（先于 DP-002）
- **健康检查**：子进程存活心跳 + WS 客户端连接状态
- **监控告警**：客户端崩溃 → 重启子进程 + 结构化日志
- **来源标注**：[TD:SA-D §1 桌面壳进程] + [调研报告:RI-OC-1]

### DP-002 Backend Single Process
- **对应模块**：M-001 ~ M-010 全部
- **运行环境**：uvicorn 0.32 + Python 3.11
- **资源配置**：CPU 1 核 / 内存 500MB / 文件描述符 1024
- **配置管理**：pydantic-settings 2.x + .env（[TS-004]）
- **依赖组件**：DP-003 本地存储（必须）；DP-004/005 可选（离线时降级）
- **启动顺序**：第 2 步（DP-001 spawn 后）
- **健康检查**：GET /health ≤500ms（[SA:BR-030]）
- **监控告警**：进程异常退出 → 桌面壳重启；端口冲突 → 递增 EX-002
- **来源标注**：[TD:SA-D §1 后端进程] + [SA:BP-001]

### DP-003 本地存储（data/）
- **对应模块**：M-001~M-010
- **运行环境**：本地文件系统
- **资源配置**：磁盘 ≥2GB（5000 文档预估）；IOPS 无特殊要求（SSD 推荐）
- **配置管理**：路径通过 .env DATA_DIR 配置
- **依赖组件**：文件系统权限 0755
- **启动顺序**：第 0 步（最先初始化）
- **健康检查**：tutor.db 完整性 PRAGMA + 启动前 .bak.YYYYMMDD
- **监控告警**：磁盘 > 80% → WARN；tutor.db 损坏 → 自动从 .bak 恢复
- **来源标注**：[TD:SA-D §4 数据备份策略] + [SA:BR-039]

### DP-004 LLM Provider（可选）
- **对应模块**：M-007
- **运行环境**：HTTPS 443（OpenAI/Anthropic）/ HTTP 11434（Ollama 本地）
- **资源配置**：网络 ≥1Mbps
- **配置管理**：OPENAI_API_KEY / ANTHROPIC_API_KEY / OLLAMA_HOST env
- **依赖组件**：网络可达
- **启动顺序**：第 3 步（DP-002 启动时 ping）
- **健康检查**：ping 30s 超时 + 1 次重试（EX-009）
- **监控告警**：provider 不可用 → 切换主备；全部失败 → 阻断兜底
- **来源标注**：[SA:BR-035] + [调研报告:RI-007]

### DP-005 pdf2zh（可选）
- **对应模块**：M-007
- **运行环境**：CLI 子进程
- **资源配置**：CPU 0.5 核 / 内存 200MB
- **配置管理**：DEEP_SEEK_API_KEY env
- **依赖组件**：pdf2zh 已 pip install
- **启动顺序**：按需（用户喂入中文 PDF 时）
- **健康检查**：3 次失败降级 LM Studio（BR-028）
- **监控告警**：翻译失败率 > 10% → 告警
- **来源标注**：[SA:BR-028] + [调研报告:RI-006]

### DP-006 Anki-Connect（可选）
- **对应模块**：M-010
- **运行环境**：HTTP 8765（Anki 桌面内嵌服务）
- **资源配置**：用户侧 Anki 应用
- **配置管理**：ANKICONNECT_URL env（默认 localhost:8765）
- **依赖组件**：Anki 已安装且 Anki-Connect 插件已启用
- **启动顺序**：按需（生成 .apkg 后导入）
- **健康检查**：HTTP / 200 探测
- **监控告警**：不可用 → EX-042 仅生成 .apkg
- **来源标注**：[调研报告:RI-011/S-014]

### DP-007 research-tool 外部源（按需）
- **对应模块**：M-004
- **运行环境**：HTTPS 443（10 个外部源）
- **资源配置**：网络 ≥1Mbps
- **配置管理**：research-tool 自身 .env
- **依赖组件**：单源失败可降级（EX-027）
- **启动顺序**：按需
- **健康检查**：HTTP 200 探测
- **监控告警**：单源失败 → 跳过该源 + WARN
- **来源标注**：[调研报告:RI-005/S-008]

---

## 三、CI/CD 流程

```
GitHub Push
   ↓
┌─ DP-008 CI (GitHub Actions Matrix) ─────────────────────┐
│  windows-latest  │  macos-latest  │  ubuntu-latest      │
│  ├─ ruff check    │  ├─ ruff       │  ├─ ruff            │
│  ├─ import-linter │  ├─ import     │  ├─ import          │
│  ├─ redocly lint  │  ├─ redocly    │  ├─ redocly         │
│  ├─ pre-commit    │  ├─ pre-commit │  ├─ pre-commit      │
│  ├─ uv lock check │  ├─ uv lock    │  ├─ uv lock         │
│  ├─ pytest        │  ├─ pytest     │  ├─ pytest          │
│  ├─ coverage ≥80% │  ├─ coverage   │  ├─ coverage        │
│  └─ make build    │  └─ make build │  └─ make build     │
│                                                            │
│  任一红 → 阻塞 merge (BR-038)                              │
│  体积超限 → 阻塞 release (EX-037)                          │
│  coverage < 80% → 阻塞 release (BR-040)                    │
└────────────────────────────────────────────────────────────┘
   ↓
Release Artifact: CLI (cx_Freeze/Nuitka) + Desktop (Electron/Tauri/PyWebView) + Web (Vite)
   ↓
GitHub Release 标记
```

---

## 四、打包工具选择

| 组件 | 工具 | 禁用项 | 来源 |
|------|------|--------|------|
| Python CLI | cx_Freeze onedir 7.x / Nuitka 2.x onedir | **PyInstaller onefile** [CVE+误报] | [调研报告:RI-003/S-004] |
| Desktop | electron-builder 32.x / cargo tauri 2.x / cx_Freeze | - | [调研报告:RI-OC-1] + [AR推断] |
| Web | Vite 5.x build + FastAPI 静态托管 | - | [AR推断:Vite SPA] |
| 体积校验 | Electron ≤250MB / Tauri ≤50MB | - | [SA:BR-037] |

---

## 五、启动顺序

```
DP-003 本地存储初始化 (第 0 步)
  ├─ 创建 data/ 目录
  ├─ .env 校验
  ├─ tutor.db 启动前 .bak.YYYYMMDD
  └─ WAL 模式检查
       ↓
DP-001 桌面壳启动 (第 1 步)
  ├─ 加载 .env
  ├─ BrowserWindow 创建（contextIsolation=true）
  └─ spawn DP-002 子进程
       ↓
DP-002 后端进程启动 (第 2 步)
  ├─ 加载 pyproject + .env
  ├─ 校验 SQLite schema 兼容（不兼容走 EX-001 自动迁移）
  ├─ 端口 8000 冲突递增重试 3 次（EX-002）
  ├─ 注册 5 类中间件（[SA:BR-003]）
  ├─ 预加载 DeBERTa-v3 ONNX 模型
  ├─ 启动 WebSocket 推送循环
  └─ 暴露 /health（<500ms）
       ↓
DP-004~007 可选依赖 (按需)
  └─ 网络/进程可达即用，不可达则降级
```

---

## 六、健康检查

| 检查项 | 端点 | 检查方式 | 失败处理 |
|--------|------|---------|---------|
| /health | DP-002 GET /health | 端口 + DB ping | 503 |
| 5 类中间件 | DP-002 内部 /v1/middleware/reload | 重新装配 | 降级 |
| WebSocket | /ws/status | 30s ping | 指数退避 |
| SQLite | tutor.db | PRAGMA integrity_check | 启动失败 |
| LLM Provider | /v1/llm/infer (HEAD) | 30s ping | 主备切换 |
| 磁盘空间 | data/ 父目录 | df 检查 | > 80% WARN |
| 桌面壳心跳 | 父进程 → 子进程 | 5s ping | 重启子进程 |

---

## 七、监控告警

| 监控指标 | 采集方式 | 告警阈值 | 通知方式 |
|---------|---------|---------|---------|
| /health 响应时间 | OTel HTTP span | > 500ms WARN | structlog + 桌面通知 |
| RAG 查询 P95 延迟 | OTel HTTP span | > 2s WARN | 同上 |
| LLM 错误率 | OTel LLM span | > 5% ERROR | 同上 |
| SQLite 慢查询 | sqlite3.set_trace_hook | > 100ms WARN | 同上 |
| 磁盘使用率 | 定时任务 df | > 80% WARN | 桌面通知 |
| 审计日志写入失败 | try/except | 100% ERROR | 阻断兜底 + 桌面通知 |
| WS 连接数 | 内部计数器 | > 80 WARN / > 95 ERROR | 同上 |
| AGAIN 风暴 | 评分日志聚合 | > 10/分钟 WARN | 同上 |
| FSM 兜底调用率 | FSM 内部计数器 | > 15% ERROR | 同上 |

---

## 八、容器化（V-1+ 预留）

```yaml
# V-1 阶段 Docker Compose 草图 [AR推断]
services:
  backend:
    image: aittutor/backend:v2.0
    build: ./backend
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data
    environment:
      - OPENAI_API_KEY
      - ANTHROPIC_API_KEY
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
```

**约束**：本期默认单机部署；V-1+ 才提供 docker-compose 模板；V-3 引入 K8s。[AR推断:TD 演进路线]

---

## 九、容量规划

| 维度 | 当前上限 | 触发扩容 | 扩容方式 | 来源 |
|------|---------|---------|---------|------|
| 知识图谱节点 | 10000 | > 10000 | V-2 Neo4j | [TD:ER V-2] |
| 文档数 | 5000 | > 5000 | sqlite-vec 索引分片 | [SA:PC] |
| 审计日志 | 不限 | 磁盘 > 80% | 归档 fs 单独分区 | [SA:PC] |
| FSRS 卡片 | 不限 | 扫描 > 5s | 增量索引 | [SA:PC] |
| 并发用户 | 1 | > 1 | V-3 多用户 | [TD:ER V-3] |
| WebSocket 连接 | 100 | > 100 | 单进程 65535 上限 | [SA:PC] |
| LLM QPS | 5 | > 5 | 熔断 + 队列 | [SA:PC] |

---

## 十、AR 洞察

### [AR-洞察-010] DeBERTa-v3 ONNX 模型预加载
DP-002 启动时预加载 NLI 模型（TS-012/013）耗时约 3-5s（首次从磁盘读 ONNX），会延长整体启动时间。**建议**：在桌面壳启动画面阶段就异步预加载（与 DP-001 启动并行），启动完成后通过 IPC 通知用户。[AR推断:启动期 UX 优化]
