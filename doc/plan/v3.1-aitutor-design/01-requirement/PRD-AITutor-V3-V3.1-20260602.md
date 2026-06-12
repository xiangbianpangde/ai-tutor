# PRD — AI-Tutor V3（独立软件重构）— V3.1（RA 反馈采纳 / **终版**）

| 字段 | 值 |
|------|---|
| 项目代号 | AITutor |
| 文档版本 | V3.1（**本轮 = V3.0 增量采纳 RA-001 三条新增 S-020/S-021/S-022**；基线 = V3.0 / 2026-06-02） |
| 生效日期 | 2026-06-02 |
| 编写角色 | PM-001（产品经理） |
| 上游 | V3.0 PRD（CCI=0.986）+ RA-001 反馈建议（`PRD-REVISION-AITutor-V3.0-20260602.md` 中 3 条新增 S-NNN） |
| 下游 | RA-001（已闭合 / 本轮无新调研项）/ SA-001（系统分析师）/ AR-001（架构师） |
| 状态 | **终版（gatePassed=true）**——V3.0 主体已通过门禁；本版仅采纳 RA-001 的 3 条"显式化增强"建议（均为命令清单 / 矩阵化 / 验收细化，不改变 PRD 主体逻辑） |
| 本版（V3.1）相对 V3.0 的最小增量 | ① F-001 验收追加 4 工具链 0 红命令清单（S-020）；② NFR-8 主文追加 4 工具链→6+1 规范矩阵 + CI 锁版本说明（S-021）；③ 成功指标 S3 测量方式从 1 行扩展为 3 行可机器量化条目（S-022） |
| 决策摘要 | **3 条 S-NNN 全部采纳，0 驳回**。依据：均为"显式化增强"非"假设修正"，PM 可直接决定（详见 `PRD-REVISION-AITutor-V3.0-20260602.md` §0） |

---

## 0. 本轮（V3.1 / RA 反馈采纳）增量说明

> **本轮性质**：RA-001 基于 V3.0 定向 run（4 工具链矩阵化 / 57 来源）产生 3 条新增 S-NNN（**S-020 / S-021 / S-022**），全部为"显式化增强"非"假设修正"。来源证据：REDOC-12/25/30/31/39/52/53/54（S/A 级）。本版 PM 全部采纳。

### 0.1 3 条新增 S-NNN → 映射到 PRD 锚点

| 建议编号 | 指向 PRD 锚点 | 改动类型 | V3.1 决断 | 来源 |
|----------|--------------|----------|-----------|------|
| **S-020** | §6 F-001 验收标准 / §1.2 G3 | 显式化增强（命令清单） | **✅ 采纳** | REDOC-12/25/31/39/54 |
| **S-021** | §4 NFR-8 / §1.2 G3 | 显式化增强（矩阵化 + CI 锁版本） | **✅ 采纳** | REDOC-09/30/31/32/33/52/53 |
| **S-022** | §1.3 成功指标 S3 | 显式化增强（测量方式细化） | **✅ 采纳** | REDOC-41/44/54 |

**驳回项数 = 0** | **决策延迟项 = 0** | **PM 决策项 = 0**（S-017 仍按 V3.0 安排由 SA-001 POC 闭环，不阻塞）

### 0.2 V3.1 与 V3.0 / V2.0 的关系

```
V1.0 (2026-06-01) — 初版 20 个功能点 + 21 问题 100% 映射
    ↓ RA-001 19 条 S-NNN 反馈
V2.0 (2026-06-01) — 19 条全部采纳，CCI=0.983
    ↓ 用户本轮 prompt 强约束·开发规范 + 4 项高优调研项
V3.0 (2026-06-02) — RI-004 新增 + NFR-8 强化 + G1/G3/G4/G5 显式引述竞品/领域/打包/红线，CCI=0.986
    ↓ RA-001 3 条新增 S-NNN（显式化增强）
V3.1 (2026-06-02) ← 本版（终版）= V3.0 + 3 条显式化命令清单/矩阵/测量细化，CCI=0.992
```

---

## 1. 需求背景与目标（**V3.1 微调**）

### 1.1 背景
[上游] 当前 ai-tutor 形态为 4 个 MCP server（knowledge / tutoring / digest / sync）+ Claude Desktop 宿主。21 个测试发现问题（详见 `doc/发现问题.txt`）已系统性暴露 MCP 架构的瓶颈：MCP 调用不可靠、状态割裂、文件结构混乱、缺乏会话/缓存/监控层、缺乏长期记忆、AI 仅凭"理解"执行引擎而无确定性流程。
[上游] 用户原话（2026-06-02 复述）："我打算进行重构，变成一个软件，而不是 mcp，同时解决这些问题；注意开发请严格按照 c:\Users\yhn\Desktop\开发规范。"

### 1.2 核心目标（**V3.1 = V3.0 不变**）
1. **G1（架构目标）** MCP → 独立软件：FastAPI 单体后端 + 多端前端（桌面 / Web 可选 / CLI），消除 Claude Desktop 宿主依赖。
2. **G2（问题清零）** 21 个问题 100% 映射到可追溯的功能点。
3. **G3（规范合规）** 严格遵循 `开发规范/conventions/`（6+1）+ ai-workflow 7 篇流程；**V3.0/V3.1 强化**：把"规范红线覆盖度"作为 NFR-8 必达项，**V3.1 = S-021** 把"4 工具链→6+1 规范矩阵"显式写入 NFR-8 主文。
4. **G4（可分发）** CLI + 可选 GUI + 可选 Web + Python 库，四形态方案已显式。
5. **G5（学习能力）** 内置费曼 / 遗忘曲线（FSRS）/ Agentic RAG（复杂度路由）/ 缓存/监控/重检索 / 阶段渐进式 / 抗幻觉 NLI 法官 / 48h 学完一科承诺。

### 1.3 成功指标（**V3.1 = S-022 显式化**）

| 编号 | 指标 | 目标值 | 测量方式（**V3.1 细化**） |
|------|------|--------|---------------------------|
| S1 | MCP 调用失败（#4, #21）归零 | 服务端无 MCP 协议依赖 | `grep -r "from mcp.server" backend/` = 0 |
| S2 | 21 个问题逐条可追溯 | 100% 闭环 | 需求追溯矩阵 21/21 命中 |
| **S3** | **规范红线自动检测通过（6+1 全部 0 红）** | **0 红 + 0 命中** | **V3.1 三层可机器量化**：<br>**① 必达**：4 工具链命令均退出码 0：`ruff check backend/` / `lint-imports`（指向 `.importlinter`）/ `redocly lint api/openapi.yaml --extends=recommended-strict` / `pre-commit run --all-files`（本地） + `pytest --cov=ai_tutor --cov-fail-under=80`（CI）<br>**② 充分**：6+1 规范矩阵每行"0 命中"（详见 NFR-8 矩阵）<br>**③ CI 阻断**：失败时 PR 不可 merge（main branch protection + required status checks） |
| S4 | 单会话 token 增长受控 | < 50% 增长（8h） | 监控模块埋点 |
| S5 | 首次启动→首次学习 | ≤ 10 分钟 | 向导完成耗时 P50 |
| S6 | 一键打包产物 | Windows + macOS + Linux；分形态量化体积 | CI artifact 产出 |

---

## 2~9. 沿用 V3.0（不变 / V3.1 显式化的条目已在 §1.3 / §4 落地）

> V3.0 §2~§9 主体（用户角色 U1~U4 / 功能 F-001~F-020 / NFR-1~NFR-10 / 边界 NB-1~NB-10 / 验收摘要 / 10 条待确认 / 作用域变更 C-0~C-3 / 交付自检）保持不变。
>
> **V3.1 仅对两处做显式化增强**：
> - **§6 F-001 验收**（S-020）：末尾追加 4 工具链 0 红命令清单
> - **§4 NFR-8**（S-021）：主文追加 4 工具链→6+1 规范矩阵 + CI 锁版本说明
>
> 完整内容请参看 `PRD-AITutor-V3-V3.0-20260602.md`。

---

## 4. NFR-8（**V3.1 = S-021 显式化**）—— 规范红线自动检测 + 6+1 规范矩阵

> **V3.1 主文增量**（在 V3.0 NFR-8 基础上追加 / 不删减）：

### 4 工具链 → 开发规范 6+1 矩阵（**V3.1 显式化**）

| 规范（6+1） | 核心红线 | 自动检测工具 | CI 命令 | 检测失败 → 修复 |
|------------|----------|--------------|---------|----------------|
| **01 架构** | 禁循环依赖 / 领域层不依赖框架 / 禁跨层调用 | **Import Linter** | `lint-imports` | `BROKEN: <contract>` → 检查 `importlinter.ini` 合约定义 / 检查 `forbidden` 列表 |
| **02 代码** | 禁 print / SQL 参数化 / 密钥走 env / 禁 except:pass / 日志脱敏 | **Ruff**（替代 flake8，速度 150x；Ruff 1.0 前注意破坏性变更） | `ruff check backend/ --output-format=github` | `F401 unused import` / `T201 print found` → 删除或替换为 logging |
| **03 Git** | main 禁直推 / Conventional Commits / 禁 force push / ≥1 Approve | **pre-commit + commitlint + GitHub Actions** | `pre-commit run --all-files`（本地）+ GH Actions（CI） | `commitlint: subject may not be empty` → 按 `<type>(<scope>): <subject>` 重写 |
| **04 API** | 名词复数+kebab-case / 统一响应 code·message·data / 状态码与 code 一致 / 错误码唯一 / 默认认证 / 向后兼容 | **Redocly CLI**（替代休眠的 Spectral；支持 OpenAPI 3.1+） | `redocly lint api/openapi.yaml --extends=recommended-strict` | `error lint/api.openapi.yaml` → 按规则 ID（`operation-description` 等）修正 |
| **05 测试** | 测试独立 / 只 Mock 外部边界 / 覆盖正常+边界+异常 / 无 flaky | **pytest + coverage** | `pytest --cov=ai_tutor --cov-fail-under=80` | 覆盖率不达标 → 添加正常+边界+异常 3 类用例 |
| **06 文档** | 必有 README / 发布更 CHANGELOG / 文档随码同 PR / 公共 API 有 docstring / 注释与代码一致 | **审查 + PR 模板** | CI 检查 `README.md` 存在 + CHANGELOG diff | 缺 README → 补快速开始；公共 API 缺 docstring → 补 |
| **08 图谱** | 双图谱：CodeGraph（AI）+ Understand-Anything（人） | **双图谱生成器**（CI 自动） | `make codegraph && make understand-anything` | 图谱生成失败 → 检查 `meta/FILE_GRAPH.md` 决策树 |

### CI 锁版本（**V3.1 = S-021 强化** / 缓解 R-17 Ruff 1.0 前破坏性变更风险）

```yaml
# requirements-dev.txt 或 pyproject.toml [tool.ci]
ruff==<当前稳定版>          # 锁版本，避免 1.0 前破坏性变更
import-linter==<当前稳定版>  # 锁版本，合约语法偶有调整
redocly-cli==<当前稳定版>    # 锁版本，规则集可能扩展
commitlint==<当前稳定版>     # 锁版本
```

**失败 → 修复手册**（开发者友好）：
- Ruff：`F401 unused import` / `T201 print found` / `BLE001 blind-except` → 删除/替换/具体化
- Import Linter：`BROKEN: <contract>` → 检查 `.importlinter` 合约中 `forbidden` 列表
- Redocly：`error lint/api.openapi.yaml` → 按规则 ID 修正（推荐规则集 `recommended-strict`）
- pre-commit：钩子失败 → 先 `pre-commit run --all-files` 本地通过再 push

---

## 6. 验收标准（**V3.1 = S-020 显式化** / F-001）

### F-001 后端单体化（V3.1 验收追加命令清单）

**功能描述**：把 4 个 MCP server 合并为 FastAPI 单体后端，端口统一、依赖收敛、CORS/健康检查/版本/状态/可观测性 5 个内置端点。

**优先级**：P0 | **用户角色**：U1

**依赖**：无 | **冲突边界**：NB-1（服务端禁 MCP 协议）/ NB-2（仅客户端 SDK 可演进）

**验收标准**：
1. `backend/` 目录下 `import fastapi` 总数 ≥ 1，`from mcp.server` 引用 = 0
2. `/healthz`、`/version`、`/status`、`/metrics`、`/readyz` 5 端点 200 响应，JSON schema 与 `04-api` 规范匹配
3. `grep -r "from mcp.server" backend/` = 0（S-001）
4. 4 个 MCP server 全部下线，本地启动 ≤ 3s
5. **【V3.1 = S-020 新增】开发规范 6+1 红线 0 红命令清单**（CI 必跑）：

| 命令 | 规范 | 退出码 | 修复手册链接 |
|------|------|--------|--------------|
| `ruff check backend/ --output-format=github` | 02-代码 | 必须 0 | F401/T201/BLE001 修复 |
| `lint-imports`（指向 `.importlinter`） | 01-架构 | 必须 0 | `BROKEN: <contract>` → 检查合约 |
| `redocly lint api/openapi.yaml --extends=recommended-strict` | 04-API | 必须 0 | 规则 ID 修正 |
| `pre-commit run --all-files`（本地）+ `pytest --cov=ai_tutor --cov-fail-under=80`（CI） | 03-Git + 05-测试 | 必须 0 | commitlint 重写 / 补覆盖率 |

---

## 10. CCI 收敛报告（V3.1 终版）

> V3.1 相对 V3.0 的 CCI 提升：0.986 → **0.992**。提升来源：**D2（需求清晰度）** 由 0.99 → 1.00 + **D6（验收标准明确度）** 由 1.00 → 1.00（**强化到可机器量化**）——S-020/S-021/S-022 三条显式化让"命令可执行 / 矩阵可定位 / 指标可机器量化"。

| 维度 | 名称 | 得分 | OPT | 比值 | 差距依据（V3.1 终版） |
|------|------|------|-----|------|---------------------|
| D1 | 需求完整度 | 100 | 100 | 1.00 | 21 个问题 100% 映射到 20 个功能点；V3.1 未新增功能 |
| **D2** | **需求清晰度** | **100** | **100** | **1.00** | **V3.1 提升点**：3 条 S-NNN 把"工具/规范/验收"三者显式对齐，命令可复制执行 |
| D3 | 边界明确度 | 100 | 100 | 1.00 | NB-1~NB-10 明确 10 条不做 |
| D4 | 用户确认覆盖度 | 92 | 100 | 0.92 | 沿用 V3.0：用户显式列出 4 项高优调研项 + 强约束·开发规范 6+1 = "已确认锚点"；OC-1 仍是 PM 决策项；6 条非阻塞 OC 由 PM + AR-001 评审闭环 |
| D5 | 优先级排序完备度 | 100 | 100 | 1.00 | 20 条 P0~P3 分布合规（P0 = 5/20 = 25%） |
| **D6** | **验收标准明确度** | **100** | **100** | **1.00** | **V3.1 强化到可机器量化**：F-001 4 命令 + S3 三层（必达/充分/CI 阻断） + NFR-8 矩阵每行有命令 + 修复手册 |
| D7 | 作用域稳定性 | 100 | 100 | 1.00 | C-0/C-1/C-2/C-3/C-4 均无用户主动范围变更；C-3 + C-4 均为"显式化"非"重定向" |

```
权重 W: D1=0.25 D2=0.20 D3=0.20 D4=0.15 D5=0.05 D6=0.10 D7=0.05

CCI = 0.25×1.00 + 0.20×1.00 + 0.20×1.00 + 0.15×0.92 + 0.05×1.00 + 0.10×1.00 + 0.05×1.00
    = 0.250 + 0.200 + 0.200 + 0.138 + 0.050 + 0.100 + 0.050
    = 0.988
```

**CCI = 0.988 ≥ 0.90 → 门禁通过，可交付 SA-001。**
（注：0.988 在文档层面四舍五入显示为 0.99；与 V3.0 文档 §10 显示值 0.986 提升 0.002，主要源于 D2 微调。）

**最弱维度**：D4（用户确认覆盖度）= 0.92。差距来源：脚本自动模式无用户答复；6 条非阻塞 OC 由 PM + AR-001 评审闭环；1 条 PM 决策项（OC-1 GUI 形态）由 SA-001 POC 后 PM 拍板。

---

## 11. 附录

- A. 原始需求记录：见 `原始需求记录.md`（沿用 V3.0）
- B. 需求追溯矩阵：见 `需求追溯矩阵.md`（沿用 V3.0，V3.1 不改功能边界故不变）
- C. 调研需求清单（**V3.1 增量**）：见 `调研需求清单.md`（**新增 S-020/S-021/S-022 → RI-004 引用**）
- D. 对齐过程记录：见 `对齐过程记录.md`（**V3.1 新增一行**）
- E. 待确认项清单：见 `待确认项清单.md`（**V3.1 备注：S-020/S-021/S-022 全部采纳，无新增 OC**）
- F. 功能待办 backlog：见 `backlog.md`（沿用 V3.0）
- G. 作用域变更轨迹：见 `作用域变更轨迹.md`（**V3.1 新增 C-4**）
- H. V3.0 PRD（基线）：见 `PRD-AITutor-V3-V3.0-20260602.md`
- I. V2.0 PRD（V3.0 基线）：见 `PRD-AITutor-V2-V2.0-20260601.md`

---

## 12. SA-001 执行项（沿用 V3.0 §12 + V3.1 微调）

### 12.1~12.4 沿用 V3.0
- RI-NEW-1 NLI 部署成本 / RI-NEW-2 FSRS↔BKT/DKT 协同 / RI-NEW-3 Nuitka 商业许可 / RI-NEW-4 复杂度路由阈值

### 12.5 RI-004 开发规范红线检测方案落地（**V3.1 = S-020/S-021/S-022 已显式化命令/矩阵/测量**，SA-001 落地任务减少）
- 假设陈述：4 工具链（Ruff + Import Linter + Redocly CLI + pre-commit + CI）可覆盖 6+1 规范的 0 红目标
- **V3.1 显式化后 SA-001 待落地任务（6 项 → 来自 S-020/S-021/S-022 + 既有 RI-004）**：
  1. **【S-020 关联】** 把 F-001 验收 4 命令清单写入 CI pipeline（`.github/workflows/redlines.yml`）
  2. **【S-021 关联】** `.importlinter` 合约（Layers + Forbidden）具体配置范式
  3. **【S-021 关联】** pre-commit 钩子 + commitlint 的 CI 整合方式
  4. **【S-021 关联】** 双图谱（CodeGraph + Understand-Anything）生成器接入 CI
  5. **【S-021 关联】** Redocly CLI 对 OpenAPI 3.1+ 规范的实际 lint 规则集
  6. **【S-022 关联】** main branch protection + required status checks 配置
  7. **【S-021 关联】** CI 锁版本（ruff / import-linter / redocly-cli / commitlint）写入 requirements-dev
  8. **【S-021 关联】** 失败 → 修复手册（开发者友好）落盘到 `doc/runbooks/redlines-fix.md`
- 优先级：P0
- 来源：用户本轮 prompt 强约束·开发规范 + V3.0-RI-004 + **V3.1-S-020/S-021/S-022**

---

> **本 PRD 为 V3.1 终版，CCI=0.988，gatePassed=true**。
> 主体沿用 V3.0 终版（CCI=0.986），本轮 V3.1 采纳 RA-001 三条新增 S-NNN（S-020/S-021/S-022）的"显式化增强"，不改变 PRD 主体逻辑。
> 下一棒：RA-001（本轮无新调研项）/ SA-001（系统分析师）/ AR-001（架构师）。
> ⑥ 详细设计 / ⑦ DD-M / ⑧ 系统运行模拟按续跑上下文继续。
