# PRD 修订建议 — AITutor V3 — V3.0（RESUME 增量版 / 3 条新增 S-NNN）

| 字段 | 值 |
|------|---|
| 项目代号 | AITutor |
| 文档版本 | V3.0（RESUME 增量版 / 3 条新增 S-NNN） |
| 生效日期 | 2026-06-02 |
| 编写角色 | RA-001 |
| 上游 | PRD V3.0（CCI=0.986）+ 调研需求清单 V3.0（4 项用户显式高优项 + RI-001~004） |
| 下游 | PM-001（增量采纳 S-020~S-022） / SA-001 / AR-001 |

---

## 0. V3.0 修订摘要

本版相对 V2.0 的核心结论：
1. **V2.0 给出的 19 条 S-NNN 修订建议 PM 已全部采纳**（18 落地 + 1 决策项保留），V3.0 全部维持；
2. **V3.0 新增 1 个定向 run（4 工具链矩阵化 / 57 来源）** 后产生 **3 条新增 S-NNN（S-020, S-021, S-022）**，全部为"显式化增强"非"假设修正"；
3. **3 条新增 S-NNN 的本质**：把 V2.0 散落在 S-006/S-007/NFR-8 各处的 4 工具链描述**矩阵化、命令化、验收化**——响应用户本轮 prompt 强约束·开发规范 6+1；
4. **唯一 PM 决策项 S-017（GUI 形态三选一）按 PRD V3.0 安排，由 SA-001 1-2 天 POC 后 PM 评审闭环**，不阻塞 PRD 定稿；
5. **4 条 RI-NEW 仍沿用 V2.0 移交 SA-001**（NLI 部署成本 / FSRS+BKT 协同 / Nuitka 商业许可 / 复杂度路由阈值）。

---

## 1. S-001 ~ S-019 闭环状态确认（V2.0 沿用 / 19 条全部维持）

| 编号 | 指向 PRD | 改动方向 | V2.0 → V3.0 状态 |
|------|---------|---------|----------------|
| S-001 | F-001 验收③ | 验收改为 `grep "from mcp.server"` = 0 | ✅ 已落地 |
| S-002 | F-003.2 | FSRS（py-fsrs ≥ 0.16.0） | ✅ 已落地 |
| S-003 | F-008 | 80% 标准 RAG / 20-30% 代理 RAG | ✅ 已落地 |
| S-004 | F-011 | 禁 PyInstaller onefile，走 cx_Freeze onedir 或 Nuitka | ✅ 已落地 |
| S-005 | F-011 验收 | 体积目标分形态量化 | ✅ 已落地 |
| S-006 | NFR-8 | 4 层工具链（Ruff+Import Linter+Redocly+pre-commit） | ✅ 已落地 → **V3.0 由 S-021 强化为"矩阵化"** |
| S-007 | NFR-8 | Spectral 维护风险标注，建议 Redocly 替代 | ✅ 已落地 |
| S-008 | F-004 / F-006 | MinHash Jaccard 0.85 + LLM 保留率 70% | ✅ 已落地 |
| S-009 | F-007 | DeepSeek 翻译抽检 ≥4/5 + 3 次失败降级 | ✅ 已落地 |
| S-010 | F-005 | WebSocket 安全配置 | ✅ 已落地 |
| S-011 | F-002 / F-010 | 短期 + 长期 + 实体三层记忆 | ✅ 已落地 |
| S-012 | F-003.5 | NLI/LLM 法官最终判定 + 重检索 ≤2-3 次 | ✅ 已落地 |
| S-013 | F-002 / F-009 | SQLite+Redis 双后端 + 语义阈值 0.85-0.95 | ✅ 已落地 |
| S-014 | F-017 | Anki 主路径 genanki .apkg | ✅ 已落地 |
| S-015 | F-018 | Obsidian 每日 ≤1 commit + 三方合并 | ✅ 已落地 |
| S-016 | NFR-5 | structlog + OTel Bridge，trace_id 32 hex | ✅ 已落地 |
| S-017 | F-005 / F-011 / OC-1 | GUI 形态三选一 | **📌 PM 决策项保留** |
| S-018 | F-006 / F-007 / OC-4 | pip install -e + uv lock 集成 | ✅ 已落地 |
| S-019 | F-003.6 / NB-6 / OC-10 | 90% 状态机 + 10% LLM 兜底 | ✅ 已落地 |

---

## 2. S-020 ~ S-022 新增（V3.0 / 显式化增强）

### S-020 F-001 验收加引 4 工具链 0 红命令

[建议编号] S-020
[指向条目] PRD §6 F-001 验收标准 / §1.2 G3
[问题描述] V2.0 F-001 验收仅写"服务端无 MCP 协议依赖"（S-001），未显式列出 4 工具链 0 红的可执行命令；V3.0 §0.2 强约束·开发规范 02-代码 提到"ruff check backend/ 0 红"，但未矩阵化到 01-架构/03-Git/04-API 红线
[建议改动] 在 F-001 验收标准末尾追加 4 条命令清单：
- `ruff check backend/ --output-format=github` → 02-代码
- `lint-imports`（指向 `.importlinter`）→ 01-架构
- `redocly lint api/openapi.yaml --extends=recommended-strict` → 04-API
- `pre-commit run --all-files` → 03-Git（本地） + `pytest --cov=ai_tutor --cov-fail-under=80` → 05-测试
[改动原因] 基于 V3.0 新增 run 来源 REDOC-12（Ruff 10-100x 速度）/ REDOC-25（Ruff 900+ 规则）/ REDOC-31（Import Linter `lint-imports` 命令）/ REDOC-39（Redocly CLI `--extends=recommended-strict`）/ REDOC-54（pre-commit vs CI 速度分层）。命令可直接复制执行，验收可量化（"0 红"= 退出码 0）。
[影响评估] 不影响功能逻辑；轻度影响：F-001 验收文档需增加 1 段约 8 行的命令清单。
[决策类型] PM 可直接决定。

---

### S-021 NFR-8 4 工具链 → 6+1 规范矩阵显式化

[建议编号] S-021
[指向条目] PRD §4 NFR-8（V3.0 强化）/ §1.2 G3
[问题描述] V2.0 NFR-8 列出 4 工具链（V2.0 S-006 + S-007），但**未与开发规范 6+1 体系做一一映射**；V3.0 §0.2 已列出 6+1 与 PRD 落地的对应表，但 NFR-8 主文未纳入此矩阵，开发者查阅时存在"知道有工具但不知道对应哪条规范"的间隙
[建议改动] 在 NFR-8 主文追加 4 工具链 → 6+1 规范矩阵（详见 RESEARCH V3.0 §2.3 第 3 点表格），并显式注明：
- **CI 锁版本**：`ruff==<当前稳定版>` / `import-linter==<当前稳定版>` / `redocly-cli==<当前稳定版>`（缓解 R-17 Ruff 1.0 前破坏性变更风险）
- **失败 → 修复手册**链接：Ruff `F401 unused import` / Import Linter `BROKEN: <contract>` / Redocly `error lint/api.openapi.yaml` 的标准修复模式
[改动原因] 基于 V3.0 新增 run 来源 REDOC-30（Import Linter 官方文档）/ REDOC-31（Meet Import Linter 合约类型详解）/ REDOC-32（import-linter PyPI）/ REDOC-33（grimp + NetworkX）/ REDOC-52（Redocly CLI Configurable rules）/ REDOC-53（四级规则集）/ REDOC-09（Ruff 渐进式采用警示）。矩阵使"工具 + 规范 + 验收"三者显式对齐，开发者能精准定位违规。
[影响评估] 不影响功能逻辑；轻度影响：NFR-8 主文增加 1 张约 8 行的矩阵表 + 2 行 CI 锁版本说明。
[决策类型] PM 可直接决定。

---

### S-022 成功指标 S3 显式化（4 工具链全绿 = 规范红线自动检测通过）

[建议编号] S-022
[指向条目] PRD §1.3 S3 成功指标
[问题描述] V2.0 成功指标 S3 = "规范红线自动检测通过（含开发规范 6+1 全部 0 红）"，**测量方式仅写"4 层工具链全绿"**——粒度太粗，无法验证 6+1 规范每条都"0 红"
[建议改动] S3 测量方式细化为：
- **必达**：4 工具链全绿 = `ruff check` / `lint-imports` / `redocly lint` / `pre-commit run --all-files` 4 条命令均退出码 0
- **充分**：6+1 规范矩阵每行"0 命中"（详见 S-021 矩阵）
- **CI 阻断**：失败时 PR 不可 merge（main branch protection + required status checks）
[改动原因] 基于 V3.0 新增 run 来源 REDOC-41（pre-commit CI 复用 `pre-commit run --all-files`）/ REDOC-54（pre-commit vs CI 速度分层，CI 作最终防线）/ REDOC-44（PR 模板 + 强制 CI 通过）。指标可机器量化（CI 退出码 + 矩阵 grep 计数），无需人工。
[影响评估] 不影响功能逻辑；轻度影响：S3 测量方式从 1 行扩展为 3 行。
[决策类型] PM 可直接决定。

---

## 3. PM 决策项 S-017（唯一保留 / 不阻塞 PRD 定稿）

### S-017 GUI 形态三选一（📌 PM 决策项）

[建议编号] S-017
[指向条目] PRD §3.1 F-005 / §3.2 F-011 / §7 OC-1
[问题描述] 桌面端 GUI 三选一（Electron / Tauri / PyWebView），各有显著权衡
[建议改动] PM 不在 PRD 阶段拍板，按 PRD V3.0 安排由 SA-001 在系统分析阶段做 1-2 天 POC 后 PM 评审闭环
[改动原因]（沿用 V2.0 来源 GUI-01~GUI-15）：
- A. Electron：生态成熟但体积 120-250MB / 启动 1-5s
- B. Tauri：体积 2-15MB（-90%）但需 2-4 周 Rust 学习
- C. PyWebView：Python 原生但 WebView2 兼容问题
[影响评估] 不影响 PRD 其他条目；POC 后再回填 F-011 验收的实际体积上限。
[决策类型] 📌 PM 评审 + SA POC 联合决策。

---

## 4. 后续移交事项（PRD 之外）

### 4.1 移交 PM/法务
- **R-11** pdf2zh AGPL 协议商用细则评审（指向 F-007）

### 4.2 移交 SA-001（已显式列入 PRD V3.0 §12.5 / 含 V3.0 新增 RI-004 5 项待落地配置）
- **RI-NEW-1** NLI 模型部署成本（指向 F-003.5 / S-012）— V2.0 §2.2 已给出参数锚点
- **RI-NEW-2** FSRS 调度与 BKT/DKT 协同（指向 F-003.2 / S-002）— schema 对齐建议
- **RI-NEW-3** Nuitka 商业许可审查（指向 F-011 / S-004）— 小规模 POC 验证
- **RI-NEW-4** 复杂度路由的实际分流阈值（指向 F-008 / S-003）— 分流判定器设计 + A/B
- **RI-004 5 项 V3.0 新增待落地配置**（指向 NFR-8 / S-020, S-021, S-022）：
  1. `.github/workflows/redlines.yml` 范例配置
  2. `.importlinter` 合约（Layers + Forbidden）具体范式
  3. pre-commit 钩子 + commitlint 的 CI 整合方式
  4. 双图谱（CodeGraph + Understand-Anything）生成器接入 CI（08-图谱规范）
  5. Redocly CLI 对 OpenAPI 3.1+ 的实际 lint 规则集
  6. 失败 → 修复手册（开发者友好）

### 4.3 移交 AR-001（架构师）
- **R-07** MCP 工具投毒漏洞 5.5%（指向 F-006）— MCP-scan 工具审计纳入架构安全方案
- **R-15** 三平台打包 CI 资源消耗（指向 F-011）— GitHub Actions matrix + 缓存方案设计

---

## 5. 结论

**PRD V3.0 在 PM 增量采纳 S-020~S-022 后即为终版可直接交付 SA-001 / AR-001**。3 条新增 S-NNN 全部为"显式化增强"，不改变 PRD V3.0 主体逻辑，PM 可直接决定（无需用户确认）。唯一保留 PM 决策项 S-017 按 V3.0 安排由 SA POC 后闭环，不阻塞定稿。

> **revisionSeverity = minor**（3 条均为显式化增强）
> **prdNeedsRevision = true**（需 PM 增量采纳 S-020~S-022）
