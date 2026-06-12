# PRD 修订建议 — AITutor V2 — V2.0（终版 / 闭环 / 0 新增）

| 字段 | 值 |
|------|---|
| 项目代号 | AITutor |
| 文档版本 | V2.0（闭环版） |
| 生效日期 | 2026-06-01 |
| 编写角色 | RA-001 |
| 上游 | PRD V2.0（CCI=0.983） + RA V1.0 报告（19 条 S-NNN） + V2.0 新增定向 run |
| 下游 | PM-001（已无需修订 PRD，直接定稿） / SA-001 / AR-001 |

---

## 0. V2.0 修订摘要

本版相对 V1.0 的核心结论：

1. **V1.0 给出的 19 条 S-NNN 修订建议 PM 已全部采纳**（18 条落地 PRD V2.0 验收 + 1 条 PM 决策项 S-017 保留）；
2. **V2.0 新增 1 个定向 run（DeBERTa-v3-large-mnli vs LLM 法官 2025-2026 实测）后无新冲突结论**，所有 19 条 S-NNN 在最新证据下仍稳健；
3. **本版不再新增 S-NNN 修订建议**（revisionSeverity = none）；
4. **唯一 PM 决策项 S-017（GUI 形态三选一）按 PRD V2.0 安排，由 SA-001 1-2 天 POC 后 PM 评审闭环**，不阻塞 PRD 定稿；
5. **4 条 RI-NEW 已显式移交 SA-001**（详见 PRD V2.0 §12），其中 RI-NEW-1（NLI 部署成本）本版给出具体参数锚点（详见 RESEARCH V2.0 §2.2）。

---

## 1. S-001 ~ S-019 闭环状态确认

| 编号 | 指向 PRD | 改动方向 | V1.0 → V2.0 状态 |
|------|---------|---------|----------------|
| S-001 | F-001 验收③ | 验收改为 `grep "from mcp.server"` = 0（服务端禁 / 客户端 SDK 允许） | ✅ 已落地 |
| S-002 | F-003.2 | FSRS（py-fsrs ≥ 0.16.0） | ✅ 已落地 |
| S-003 | F-008 | 80% 标准 RAG / 20-30% 代理 RAG（复杂度路由） | ✅ 已落地 |
| S-004 | F-011 | 禁 PyInstaller onefile，走 cx_Freeze onedir 或 Nuitka | ✅ 已落地 |
| S-005 | F-011 验收 | 体积目标分形态量化：Electron ≤250MB(软) / Tauri ≤50MB(推荐) | ✅ 已落地 |
| S-006 | NFR-8 | 4 层工具链（Ruff+Import Linter+Redocly+pre-commit） | ✅ 已落地 |
| S-007 | NFR-8 | Spectral 维护风险标注，建议 Redocly 替代 | ✅ 已落地 |
| S-008 | F-004 / F-006 | MinHash Jaccard 0.85 + LLM 保留率 70% | ✅ 已落地 |
| S-009 | F-007 | DeepSeek 翻译抽检 ≥4/5 + 3 次失败降级 + 降级后语种校验 | ✅ 已落地 |
| S-010 | F-005 | WebSocket 安全：主进程管连接 + IPC + contextIsolation+sandbox+CSP | ✅ 已落地 |
| S-011 | F-002 / F-010 | 短期 ConversationSummaryBufferMemory + 长期 LangGraph Store + 实体 SQLite+sqlite-vec | ✅ 已落地 |
| S-012 | F-003.5 | NLI/LLM 法官最终判定 + 重检索 ≤2-3 次 + 提前退出 | ✅ 已落地（V2.0 §2.2 补强 HaluGate 级联架构） |
| S-013 | F-002 / F-009 | SQLite+Redis 双后端 + 语义阈值 0.85-0.95 | ✅ 已落地 |
| S-014 | F-017 | Anki 主路径 genanki .apkg，Anki-Connect 辅助 | ✅ 已落地 |
| S-015 | F-018 | Obsidian 每日 ≤1 commit + 跳过 .obsidian/ + 三方合并 + 手动仲裁 | ✅ 已落地 |
| S-016 | NFR-5 | structlog + OTel Bridge，trace_id 32 hex + span_id 16 hex | ✅ 已落地 |
| S-017 | F-005 / F-011 / OC-1 | GUI 形态三选一（Electron/Tauri/PyWebView） | **📌 PM 决策项保留**（19 条中唯一） |
| S-018 | F-006 / F-007 / OC-4 | pip install -e + uv lock 集成 | ✅ 已落地 |
| S-019 | F-003.6 / NB-6 / OC-10 | 90% 状态机 + 10% LLM 兜底 + 兜底带 trace_id + 审计日志 | ✅ 已落地 |

**统计**：19 条中 18 条 ✅ / 1 条 📌（S-017）。0 ❌ / 0 🔄。

---

## 2. PM 决策项 S-017（唯一保留 / 不阻塞 PRD 定稿）

### S-017 GUI 形态三选一（📌 PM 决策项）

[建议编号] S-017
[指向条目] PRD §3.1 F-005 / §3.2 F-011 / §7 OC-1
[问题描述] 桌面端 GUI 三选一（Electron / Tauri / PyWebView），各有显著权衡

[建议改动] PM 不在 PRD 阶段拍板，按 PRD V2.0 安排由 SA-001 在系统分析阶段做 1-2 天 POC 后 PM 评审闭环

[改动原因]（基于 V1.0 RI-OC-1 来源 GUI-01~GUI-15 + V1.0 RI-003 来源 PYN-01~PYN-59）：
- A. Electron：生态成熟（npm 400 万/周下载）但体积 120-250MB / 内存 100-300MB / 启动 1-5s（来源 GUI-01, GUI-02）
- B. Tauri：体积 2-15MB（-90%）/ 内存 20-100MB（-75%）/ 启动 0.1-0.5s，但需 2-4 周 Rust 学习 + 现有 PDF 解析/学习引擎重写桥（来源 GUI-15）
- C. PyWebView：Python 原生（js_api 直接暴露 Python 对象），体积最小，但 Windows WebView2 兼容问题 + 生态最弱（来源 GUI-03）

[影响评估] 不影响 PRD 其他条目；POC 后再回填 F-011 验收的实际体积上限（V2.0 已分形态量化为软上限）。

[决策类型] 📌 PM 评审 + SA POC 联合决策。

---

## 3. 后续移交事项（PRD 之外）

### 3.1 移交 PM/法务
- **R-11** pdf2zh AGPL 协议商用细则评审（指向 F-007）

### 3.2 移交 SA-001（已显式列入 PRD V2.0 §12）
- **RI-NEW-1** NLI 模型部署成本（指向 F-003.5 / S-012）— V2.0 §2.2 已给出参数锚点（DeBERTa CPU 数百 ms / Haiku $1-$5 / GPT-4 30x 成本 + HaluGate 400x TCO 降低）
- **RI-NEW-2** FSRS 调度与 BKT/DKT 协同（指向 F-003.2 / S-002）— schema 对齐建议
- **RI-NEW-3** Nuitka 商业许可审查（指向 F-011 / S-004）— 小规模 POC 验证
- **RI-NEW-4** 复杂度路由的实际分流阈值（指向 F-008 / S-003）— 分流判定器设计 + A/B

### 3.3 移交 AR-001（架构师）
- **R-07** MCP 工具投毒漏洞 5.5%（指向 F-006）— MCP-scan 工具审计纳入架构安全方案
- **R-15** 三平台打包 CI 资源消耗（指向 F-011）— GitHub Actions matrix + 缓存方案设计

---

## 4. 结论

**PRD V2.0 已是终版可直接交付 SA-001 / AR-001**。RA-001 不再产出新增 S-NNN 修订建议，仅做闭环确认 + 给 SA-001 阶段提供具体参数锚点。

> revisionSeverity = **none**
> prdNeedsRevision = **false**
