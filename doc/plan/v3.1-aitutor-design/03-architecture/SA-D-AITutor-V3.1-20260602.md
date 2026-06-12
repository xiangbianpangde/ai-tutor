# 系统架构图-部署视图 — AITutor V3.1

> 视角：运维 / DevOps
> 部署形态：本地优先 + 单容器 + 三平台打包

---

## 一、单机部署拓扑（默认 / 生产等价）

```
┌─────────── 宿主机 (Win/macOS/Linux) ──────────────┐
│                                                    │
│  ┌── 进程 A: ai-tutor serve (PID 1) ─────────┐    │
│  │  Port 8000                                 │    │
│  │  Volume: ./data  → SQLite + Chroma         │    │
│  │  Env: .env (LLM_KEY / REDIS_URL 可选)       │    │
│  │  Health: /healthz /readyz /metrics          │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  ┌── 进程 B(可选): Redis ───────────────────┐    │
│  │  Port 6379  (仅生产模式启用)                │    │
│  │  Volume: redis-data/                       │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  ┌── 进程 C(可选): LM Studio (本地 LLM) ─────┐    │
│  │  Port 1234  (OpenAI 兼容)                   │    │
│  └────────────────────────────────────────────┘    │
│                                                    │
│  ┌── 文件存储 ──────────────────────────────┐    │
│  │  data/tutor.db              (SQLite 主库)  │    │
│  │  data/chroma/               (向量索引)     │    │
│  │  data/inbox/                (PDF 待处理)   │    │
│  │  data/obsidian-vault/       (本地资料)     │    │
│  │  data/artifacts/            (打包产物)     │    │
│  │  meta/FILE_GRAPH.md         (决策树)       │    │
│  │  api/openapi.yaml           (API 契约)     │    │
│  │  doc/runbooks/redlines-fix.md (修复手册)   │    │
│  └────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────┘
```

来源标注：[SA:BP-001] + [SA:BR-006] + [SA:BR-014/032/036] + [SA:DE-001~DE-048]

---

## 二、CI/CD 部署拓扑

```
GitHub Repo
  ├─ PR push    →  CI workflow (redlines + pytest + build matrix)
  │                ├─ 进程 D1: ruff + import-linter + redocly
  │                ├─ 进程 D2: pre-commit + pytest --cov
  │                ├─ 进程 D3: matrix build (Win/macOS/Linux)
  │                └─ required status checks → branch protection
  └─ main push  →  release workflow
                   ├─ tag + CHANGELOG
                   └─ upload artifact (CLI/GUI/Web 3 形态)
```

来源标注：[SA:BP-021] + [SA:BR-046~050] + [SA:CE-011~015]

---

## 三、环境分层

| 环境 | 用途 | 关键差异 | 部署方式 |
|------|------|---------|---------|
| dev | 本地开发 | SQLite + LM Studio + 热重载 | `ai-tutor serve --reload` |
| test | 单元/集成测试 | 内存 SQLite + mock LLM | `pytest --cov` |
| staging | CI 演练 | SQLite + 真实 LLM key | CI matrix |
| prod | 用户本地 | SQLite 或 Redis + LLM | `ai-tutor serve` / 桌面端启动器 |
| CI | 红线验证 | 容器化 + 4 工具 | GitHub Actions |

来源标注：[TD推断:依据=单进程 + 单容器分层] + [SA:BR-001~005]

---

## 四、扩展部署（演进 V2.0）

| 扩展点 | 触发 | 扩展方式 | 来源 |
|--------|------|---------|------|
| 多用户支持 | B-002 | 增加 Auth 层 + 用户表分区 | [SA:AR-005] |
| 云端备份 | B-001 | 增加 S3 同步 worker | [SA:AR-004] |
| PPT/Word 翻译 | B-003 | 翻译插件 pptx/docx | [SA:AR-007] |
| 扫描件 OCR | B-004 | OCR 引擎插件(已有 IF) | [SA:BP-018] |
| 重要性评分淘汰 | CR-001 | 增加 importance_score 字段 | [SA:AR-017] |

来源标注：[SA:AR-004/005/007/017] + [SA:CR-001]
