# 系统架构图 - 部署视图 — AITutor V2.0

> 单机部署 + 跨平台打包（[SA:BP-016]）

## 1. 部署拓扑（用户本地单机）

```
┌────────── 单台用户机器（Win/Mac/Linux）─────────────────────┐
│                                                              │
│  ┌─ Desktop Shell (GUI) ─────────────────────────────┐     │
│  │  electron-builder / tauri build / cx_Freeze 集成  │     │
│  │  体积: Electron ≤250MB / Tauri ≤50MB (BR-037)     │     │
│  └──────────────┬────────────────────────────────────┘     │
│                 │ 子进程 spawn                               │
│  ┌──────────────▼────────────────────────────────────┐     │
│  │  Backend Single Process (uv run main:app)          │     │
│  │  端口: 8000 (冲突递增)                              │     │
│  │  资源: 内存 200-500MB / CPU 单核即可               │     │
│  └──────────────┬────────────────────────────────────┘     │
│                 │ 本地文件 IO                                │
│  ┌──────────────▼────────────────────────────────────┐     │
│  │  本地存储 (data/)                                   │     │
│  │  ├─ tutor.db (SQLite + WAL 模式)                   │     │
│  │  ├─ logs/ (structlog + OTel 输出)                  │     │
│  │  ├─ obsidian-vault/ (可选)                          │     │
│  │  ├─ research-cache/ (原始文档)                      │     │
│  │  └─ STATUS.md (看板数据源)                          │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                              │
│  可选外部依赖（首次/在线时）:                                │
│  ├─ LLM Provider (OpenAI / Anthropic / Ollama 本地)        │
│  ├─ pdf2zh DeepSeek 翻译 API                                │
│  ├─ Anki-Connect (localhost:8765)                          │
│  └─ research-tool 10 个外部源 (ARXIV/GITHUB/WIKI/...)     │
└──────────────────────────────────────────────────────────────┘
```

## 2. CI/CD 流程（[SA:BP-016]）

```
GitHub Push
   ↓
┌─ CI (GitHub Actions Matrix) ─────────────────────┐
│  windows-latest  │  macos-latest  │  ubuntu-latest│
│  ├─ ruff check    │  ├─ ruff       │  ├─ ruff      │
│  ├─ import-linter │  ├─ import     │  ├─ import    │
│  ├─ redocly lint  │  ├─ redocly    │  ├─ redocly   │
│  ├─ pre-commit    │  ├─ pre-commit │  ├─ pre-commit│
│  ├─ uv lock check │  ├─ uv lock    │  ├─ uv lock   │
│  └─ make build    │  └─ make build │  └─ make build│
│                                                       │
│  任一红 → 阻塞 merge (BR-038)                        │
│  体积超限 → 阻塞 release (EX-037)                    │
└──────────────────────────────────────────────────────┘
   ↓
Release Artifact (3 平台 CLI + Desktop + Web)
   ↓
GitHub Release 标记
```

## 3. 打包工具选择（[SA:BP-016]）

| 组件 | 工具 | 禁用项 | 来源 |
|------|------|--------|------|
| Python CLI | cx_Freeze onedir / Nuitka | **PyInstaller onefile** | [SA:BP-016] |
| Desktop | electron-builder / cargo tauri / cx_Freeze | - | [SA:AR-001 待 PM 决策] |
| Web | Vite build + FastAPI 静态托管 | - | [SA:BP-020-D] |
| 体积校验 | Electron ≤ 250MB (软) / Tauri ≤ 50MB | - | [SA:BR-037] |

## 4. 数据备份策略

| 数据 | 备份方式 | 频率 | 保留期 |
|------|----------|------|--------|
| tutor.db | 启动时自动 .bak.YYYYMMDD (EX-001) | 迁移前 | 30 天滚动 |
| audit_log | SQLite 内归档 (BP-008 兜底审计) | 实时 | 不清理（合规） |
| STATUS.md | 原子写 .tmp + rename (BP-018) | 实时 | 单文件覆写 |
| 知识图谱 (DE-027) | JSON-Lines 导出 (BP-009 治理) | 每周 | 用户自主 |
| 本地资料 (DE-041) | 用户原目录，AI Tutor 只读 | - | - |
