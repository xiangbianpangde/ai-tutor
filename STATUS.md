# AI-Tutor 开发状态

> 更新: 2026-06-15（**v2 11 功能点全部就位 + 前端补全 + 端到端真管线 + 真编译/真跑实证**：
> C3-C5 共 9 backend 模块 + #7 WebSocket + React 前端（5 页面/向导/3 可视化）+ test_e2e_pipeline
> 真建图全链；**939 测试全绿**；**Electron 运行时真跑（截图）+ 真 Nuitka onedir 编译全后端**；
> D2/D3 收束四阶段已执行待签核 / C1+D1 已签核；**已产 139MB NSIS 安装包 + 打包应用真跑实证**，
> #21 仅剩"真人双击安装包走一遍"的人工验收）
> 流程档位: 标准
> 收束节点: 功能点3后 / 功能点7后 / 功能点11后

---

## v1 总体进度（已完成）

| 维度 | 状态 |
|------|------|
| MCP server | 4/4 ✅ |
| Tool 总数 | 32 ✅ |
| 教学策略 | 7（2 完整 + 5 精简）|
| 测试 | 797 全绿（2026-06-13，基线 792 + FIX-L 4 条 + FIX-M 1 条）|
| 架构 | MCP Server + Claude Desktop |

## 2026-06-12 · 22 问题根因调查与修复

> 根因报告（每问题：现象→根因 file:line→修复→落点）：`doc/reports/根因分析-22问题.md`
> 22 问题归结为 5 条系统性根因：R1 语料缺整理 / R2 标题当概念 / R3 引擎↔宿主契约模糊 / R4 MCP 长事务不匹配 / R5 横切关注点无接线

| 修复 | 内容 | 修的问题 |
|------|------|---------|
| FIX-A | 标题解析治理：代码围栏跳过 + 噪声标题过滤 + 重复名告警（kg_enrich_adapter）| #22 #1 #3 |
| FIX-B | 合并语料治理：真实标题(`<!--title-->`) + 剥元数据 + 标题降级 + 薄残文跳过（research_adapter）| #1 #22 |
| FIX-C | acquire 多源合并 `00_corpus.md`——KG 不再只吃第一个源（acquisition_adapter）| #8 #14 |
| FIX-D | 判分题目感知：score(+question)，答非所问最高 partial（llm_scorer/engine/cold_start）| #18 #20 |
| FIX-E | PRACTICE 死循环修复：接受 answered 事件（reduction）| #16 #20 |
| FIX-F | 连续学习 ≥50min → 主动休息建议；接线 total_elapsed/active_time（engine/schemas）| #10 |
| FIX-G | feynman 选择器门槛可达（默认画像即可触发）| #12 |
| FIX-H | 中文 PDF 语种映射 zh→ch 收尾 + 回归测试（pdf_parser）| #17 #19 |
| FIX-I | 调研 deepen 开关：LLM 拆 3-5 子面分别采集归并（research_adapter，默认关）| #9 #15 |
| FIX-J | digest 新产物 study_pack：语料拆 15-30min/份 + 索引（替代手工拆 121 份）| #2 #8 |

**真实语料验证**：ACP 75,393 行 merged md 重过新解析器——概念 356→211，噪声 126→**0**。
**架构级问题**（#3#4#5#6#7#11#15#21）：根因确认在 v1 架构，修复落 v2（验收红线已写入 `doc/plan/开发清单.md`），v1 不再投入。

## 2026-06-12/13 · 新科目复跑验证（FastAPI 后端开发）+ FIX-K

> worklog：`worklogs/2026-06-12_复跑验证-tutor_cli-FIX-K.md`。STATUS「下一步」第 1 项完成。

- **tutor_cli**（`scripts/tutor_cli.py`）：统一 CLI 入口，11 子命令覆盖采集→建图→质检→
  产物→教学全程，ID 自动链路（`data/cli_state.json`）——任何新科目零脚本零 SQL 跑通。
  替代 17 个硬编码一次性脚本（acp_*/step*，已归档进 git 历史后删除）。
- **FIX-K**（web 语料噪声形态 + 重建语义，9 条回归测试）：
  - K1 噪声标题过滤扩展 12 类（时间戳/文件名路径/dotfile/装饰注释/emoji/批注引导/
    含逗号整句/尾冒号/代码行/截断标题/GitHub 路径/英文整句注释）
  - K2 `strip_site_suffix` 站点尾巴剥离（两遍，未剥离不重组）
  - K3 `_persist_kg` 幂等重建：同 kg_id 整体替换；**同科目重新采集后重建撞概念主键**
    （concept.id 无 corpus 命名空间）→ 撞 id 旧根版本 KG 自动替换（曾只能手工删库）
  - K4 deepen 子面重复文章按 (URL, 正文哈希) 去重
  - K5 study_pack 递归下钻 H3-H6（web 伞形语料不再切出 3 个千分钟大块）
- **复跑结果**：3 主题 deepen 采集 99,174 行 → 六轮过滤迭代 369→**199** 概念
  （全量禁类扫描 1/199=0.5%，三禁类=0）→ study_pack 75 份 → 教学 21 步掌握 2 概念，
  3 次答非所问攻击全判 incorrect，give_exercise 占比 15%，增益回路自发 break_suggestion。

## 2026-06-13 · 第二批挑战过堂 + FIX-L/M

> worklog：`worklogs/2026-06-13_第二批挑战过堂-FIX-L-FIX-M.md` +
> `worklogs/2026-06-13_v3.1-走向决议.md`。6/6 全过，其中 2 题按"发现问题=得分"拿分。

| 修复 | 内容 | 来源挑战 |
|------|------|---------|
| FIX-L | 判分启发式回退**永不授 correct**（曾经：含概念名废话 correct 0.7 + 冷启动白拿 0.88 先验；切题极简反被压 0.4）。主题相关性同看概念名+定义 n-gram，降级判分 evidence 明示 | 判分反向攻击（LLM 主路径 3/3 极简正确 correct 0.90+ 无冗长偏好；回退路径中招已修） |
| FIX-M | 论文/文档骨架节名过滤（摘要/致谢/参考文献/目录/附录A/abstract/references…只杀无歧义纯骨架；引言/结论/相关工作保留） | 换体裁攻击（AAAI 论文 PDF：禁类 3/19=15.8% → 0/16=0%，两次全量扫描） |

附带：① 死系统代理（127.0.0.1:7897）= DeepSeek/mineru/uv 全链 10054 的根因，
NO_PROXY 进程级绕法入持久记忆；② mineru 工具环境腐烂修复（six/scipy/ftfy/einops/
pyclipper + transformers<5）；③ tutor_cli 不再吞 TutorError.hint（外部 CLI stderr）。

---

## v2 重构进度

| 功能点 | BDD 规格 | 状态 | 完成日期 |
|--------|---------|------|---------|
| 1 后端骨架：FastAPI 统一应用 | specs/01-基础骨架.md | ✅ C1 完成（backend/ 跑通 :18501）| 2026-06-13 |
| 2 API 迁移：MCP → REST | specs/02-API迁移.md | ◐ 网关+信封+health 就位；32 tool 迁移随引擎 C2-C4 | - |
| 3 中间件层：Session/File/Cache/Monitor | specs/03-中间件层.md | ◐ C2：M-005 缓存层就位（SQLite 跨重启）；Session/File/Monitor 待续 | - |
| 4 Electron 前端骨架 | specs/04-前端应用.md | ✅ React 渲染层：5 页面+侧边栏路由+首次向导+WS 客户端（指数退避重连）。Vite build 通过 + 真浏览器验证（仪表盘拉真后端 5/5 子系统）；Electron 运行时真跑待桌面环境 | 2026-06-15 |
| 5 可视化：KG图/遗忘曲线/掌握度 | specs/05-可视化.md | ✅ ForceGraph（d3-force 力导向图）+ ForgettingCurve（FSRS 保持率）+ MasteryHeatmap（认知负荷）；后端 /graphs/{kg}/view 配套。真浏览器验证 FSRS 评分往返 | 2026-06-15 |
| 6 数据管线：采集→清洗→结构化 | specs/06-数据管线.md | ⏳ 待开始 | - |
| 7 research-tool 深度集成 | specs/07-research-tool集成.md | ⏳ 待开始 | - |
| 8 pdf2zh 深度集成 | specs/08-pdf2zh集成.md | ⏳ 待开始 | - |
| 9 Agentic RAG + 缓存 + 监控 | specs/09-AgenticRAG.md | ◐ C3：M-008 RAG 引擎（词法检索+NLI风格验证+自主重检索状态机+REST）；真向量后端/NLI模型延后 | 2026-06-15 |
| 10 策略升级 + 健康监控 + 幻觉检测 | specs/10-策略升级.md | ◐ C3 M-009 教学编排 + C4 M-010 费曼/M-011 FSRS/M-012 阶段校准/M-013 长期记忆/M-016 红线编排（REST 齐备） | 2026-06-15 |
| 11 打包发布：Electron + Python 嵌入 | specs/11-打包发布.md | ◐ C5：M-015 打包调度（Nuitka onedir FSM + 软压缩 + 校验）+ M-001 收尾（聚合健康）；真编译/Electron 真验=发布阶段 | 2026-06-15 |

## 收束节点历史

| 节点 | 触发条件 | 执行日期 | 状态 | 报告 |
|------|---------|---------|:---:|------|
| D1 | C1 完成（后端骨架+API+前端入口）| 2026-06-13 | ✅ 已审计（人签核，"继续"授权进 C2）| [收束报告-D1-C1](doc/reports/收束报告-D1-C1.md) |
| D2 | C3 完成（核心引擎就位）| 2026-06-15 | ◐ 四阶段已执行（885 测试/覆盖率96%/审计4工具全过/真机8路由+curl验证），**待人签核** | [收束报告-D2-C3](doc/reports/收束报告-D2-C3.md) |
| D3 | C5 完成（11 功能点全过）| 2026-06-15 | ◐ 四阶段已执行（934 测试/覆盖率96%/审计4工具全过+打包硬红线/真机25路由+聚合健康），**待人签核** | [收束报告-D3-C5](doc/reports/收束报告-D3-C5.md) |

> D1 四阶段结果：测试 810 passed / backend 覆盖率 92% / ruff+import-linter 全过 /
> **pip-audit 实查出 6 漏洞（starlette+pyjwt）已当场修复→复扫 0** / 真机 :18501 + curl 验证过。
> 未达项均环境受限非缺陷（Electron 运行时未跑 / redocly 文档完整性告警）。**等人审核签核**。

## v3.1 设计包交付（2026-06-02 · plan-writing 工作流）

| 维度 | 数值 | 路径 |
|------|------|------|
| 项目代号 | AITutor V3.1 | — |
| 阶段状态 | ⏸️ 计划阶段交付 · 待 review | `doc/plan/v3.1-aitutor-design/` |
| 设计包大小 | ~120 份文件 | 7 子目录 + research/ + reports/ |
| 7 棒收敛指数 | CCI=0.988 / RCI=0.997 / CTI=0.97 / TDI=0.97 / ARI=0.99 / DDI=0.96 / FRI(avg)=0.995 | `convergence-summary.md` |
| 全部指数 vs 0.85 门禁 | 7/7 ✅ | — |
| 模块数 | 17 个 M-NNN（M-001~M-017）/ D7=100 全过 | `06-framework/` |
| 调研工具 | 18 个真实 run / 865+ 来源 / 57 S/A 级 | `doc/research/v3.1-aitutor-research/` |
| 端到端模拟 | 15 拍可走通（7.8s）+ 3 异常分支 | `doc/reports/v3.1-aitutor-simulation/` |
| PRD 迭代 | 4 轮（V1→V2→V3→V3.1）/ 22-22 RA 反馈全采纳 / 0 硬回退 | — |
| 关键决策 | HaluGate 三级级联 / LangGraph 1.0 / FastAPI 0.115 / Python 3.11 | `04-tech-architecture/` |
| 风险项 | 5 项（详见 `REVIEW-CHECKLIST.md` §关键风险）| — |

### v3.1 ↔ v2 关系
- v3.1 是 v2 的**细化升级 + 局部重整**——**不替代**，**并行保留**
- 17 模块 ↔ 11 功能点 完整映射见 `doc/plan/v3.1-aitutor-design/V3.1-vs-V2-桥接.md`
- 推荐策略：v2 主体推进 + v3.1 引入的 3 个新模块（事件总线 M-006 / 打包调度 M-015 / 红线编排 M-016）作为增量补充

### v3.1 review（2026-06-13 完成 ✅）
- [x] 7 段路线走完（真实结论非全✅：段七有条件通过）→ `worklogs/2026-06-13_v3.1-走向决议.md`
- [x] 走向 = **C'（修正版 C）**：v2 主体 + v3.1 增量（M-006/M-015/M-016 + #10 拆 6 模块）+ 6 项修正；A/B/D 否决理由见走向决议 §三
- [x] A4 交叉引用核对：10 条冲突/重复/缺口清单（最重要：v2 打包文档 PyInstaller 被 R-01 证伪须改 Nuitka onedir；backend/ vs src/aitutor 目录名 C1 首日决断）
- ⚠️ 元发现：设计包曾整体不在仓库（e7be6a0 声称抢救实未入库），已从 `日常-备份/MCP-v2/` 还原（bc82a7c，实测 403 份）；旧收束报告系交付当日工作流自评，已补复核更正段

## v3.1 之后需要完成的内容（2026-06-02 增）

> 范围：v3.1 review 通过后到正式开发结束期间的所有待办。按优先级排序，每项标 ☐ 未开始 / ◐ 进行中 / ✅ 已完成。

### 阶段 A · Review 收束（预计 1-2 天）
- ☐ **A1** 按 `REVIEW-CHECKLIST.md` 7 段 60min 路线 review 完（最关键 5 风险：R-16/R1/C2/pdf2zh AGPL/sqlite-vec）
- ☐ **A2** 决定 v3.1 走向（A/B/C/D 四选一，推荐 C），写入 `worklogs/YYYY-MM-DD_v3.1-走向决议.md`
- ☐ **A3** 写 v3.1 收束报告（按 07-汇报.md 二档）→ 落盘 `doc/reports/收束报告-v3.1.md`
- ☐ **A4** v2 现有 10 份 `doc/plan/design/` 与 v3.1 17 模块交叉引用，输出冲突/重复/补充清单

### 阶段 B · 开发准备 ✅ 全完成（2026-06-13）

> 执行记录：`worklogs/2026-06-13_B阶段收尾-precommit-版本锁定.md`。797 测试保持全绿。

- ✅ **B1** Git 仓库状态检查（main 干净）
- ✅ **B2** pre-commit 门禁落地：`.pre-commit-config.yaml`（全 local/system hook，规避死代理）
  = ruff lint（红线 T20/T100/B）+ import-linter（**2 契约 KEPT**：shared⊥servers / 四 server 独立）
  + gitleaks + redocly（无 spec 休眠，C1 激活，**替代休眠的 spectral**）。
  关键：`exclude doc/` 后 ruff 真实基线 787→246，清零（205 自动修 + 手工修 E402/B007/F821/UP038），
  `ruff check` All passed。**ruff-format 暂关**（188/203 文件待全仓格式化，C1 首日决定，见 worklog §四）
- ✅ **B3** 版本锁定 → `doc/reports/依赖版本锁定.md`；`uv lock` 折入 import-linter/pre-commit（0 漂移）；
  **锁定对象 pdf2zh→mineru 3.2.0**（上游 AGPL pdf2zh 包已移出依赖）；fastapi 0.115/sqlite-vec 0.1.x 留 C 波
- ✅ **B4** 历史快照 → git tag `v3.0-design-snapshot` + `v3.1-aitutor-design/历史快照/README.md`
  （遵 DEVELOPMENT-NORM 不物理复制 59 文件，git tag 冻结 C 波前设计状态）
- ✅ **B5** 风险处置成文（= 走向决议 §二 5 风险逐个处置，含本日 R-16 实测）

### 阶段 C · 开发启动（5 波推进，按 V3.1↔V2 桥接 §四）
- ✅ **C1 第一波**（2026-06-13）M-001 服务入口 + M-002 API 网关 + M-003 客户端入口（对应 v2 #1+#2[网关]+#4[入口]）
  → `worklogs/2026-06-13_C1第一波-后端骨架-API网关-客户端入口.md`。`backend/` 跑通 :18501。D1 已签核。
- ✅ **C2 第二波**（2026-06-13 完成 7/7）M-004 Session + M-005 Cache + M-006 事件总线 + M-007 Pipeline + M-017 File + M-014 数据管线（对应 v2 #3+#6+#7+#8）
  - ✅ 波前文档去 sys.path 化（pdf2zh 集成，走向决议 §五-6）
  - ✅ **M-005 CacheLayer**（SQLite L1 缓存，跨重启存活 + `/api/meta/cache/stats`）
    → `worklogs/2026-06-13_C2-pdf2zh文档去syspath-M005缓存层.md`
  - ✅ **M-004 SessionManager**（包 v1 SessionStore + session_summaries 表：列表/切换/摘要/token/过期 + `GET /api/tutoring/sessions`）
    → `worklogs/2026-06-13_C2-M004-会话管理器.md`
  - ✅ **M-007 TaskManager**（线程池后台任务 + tasks 表 + build_kg 异步：`POST /subjects/{id}/graphs`→202 task_id，`GET /api/tasks/{id}` 轮询进度）
    → `worklogs/2026-06-13_C2-M007-异步任务层-build_kg异步.md`
  - ✅ **M-006 EventBus**（进程内 pub/sub + EventRecorder + `GET /api/meta/events`，#7推送/#11监控地基）
    → `worklogs/2026-06-13_C2-M006-事件总线.md`
  - ✅ **M-017 FileManager**（`{user}/{subject}/{kind}/` 人类可读目录替 UUID + 路径穿越防护）
    → `worklogs/2026-06-13_C2-M017-文件管理器.md`
  - ✅ **M-014 数据管线**（NoiseGate 噪声<5% 红线 + DataPipeline 编排 + `GET /api/knowledge/graphs/{kg}/noise`，855 测试全绿）
    → `worklogs/2026-06-13_C2-M014-数据管线-噪声红线.md`
- ✅ **C3 第三波**（2026-06-15）M-008 RAG 引擎（词法检索+NLI风格验证+自主重检索状态机+REST，
  `backend/rag/` commit 88b8031）+ M-009 教学编排（v1 TeachingEngine→REST 会话驱动+M-004/M-006
  接线，`backend/teaching/` commit 1668490）（对应 v2 #9+#10 部分）。885 测试全绿，覆盖率 96%。
  务实落地（不引 ChromaDB/NLI 模型）见 ADR-0003。→ `worklogs/2026-06-15_C3第三波-M008-RAG-M009-教学编排.md`。
  **C3 完成触发 D2 收束节点**（四阶段已执行，待人签核）。
- ✅ **C4 第四波**（2026-06-15）M-010 费曼评分 + M-011 FSRS-5 + M-012 阶段校准 + M-013 长期记忆 +
  M-016 红线编排（对应 v2 #10 拆分）。`backend/strategy/` + `backend/memory/` + `backend/redline/`，
  36 测试，backend 124 全绿。重依赖纯 Python 替代（FSRS-5 自实现替 py-fsrs）。commit e1aa27d。
- ✅ **C5 第五波**（2026-06-15）M-015 打包调度（Nuitka onedir FSM：编译→UPX 软压缩→校验，
  硬红线禁 --onefile，R-01）+ M-001 收尾（`GET /api/meta/health` 聚合子系统就绪）（对应 v2 #11）。
  `backend/build/`，13 测试，backend 137 全绿。commit 1c2af16。**C5 完成触发 D3 收束节点
  → v2 11 功能点全部就位**。

### 阶段 D · 收束节点（按 03-第一步.md 1.6 预设 + 06-第三步_收束节点.md）
- ◐ **D1** 收束节点 1：C1 完成 → 四阶段已执行（整理/测试/审计/验证），收束报告落盘 + 2 ADR + 6 漏洞修复；**待人签核**（`doc/reports/收束报告-D1-C1.md`）
- ◐ **D2** 收束节点 2：C3 完成（核心引擎就位）→ 四阶段已执行（整理/885测试·覆盖率96%/审计4工具全过/真机8路由+curl验证），收束报告 + ADR-0003 落盘；**待人签核**（`doc/reports/收束报告-D2-C3.md`）
- ◐ **D3** 收束节点 3：C5 完成（v2 11 功能点全部就位）→ 四阶段已执行（整理/934测试·覆盖率96%/审计4工具全过+打包硬红线/真机25路由+聚合健康），收束报告 + ADR-0004 落盘；**待人签核**（`doc/reports/收束报告-D3-C5.md`）

### 阶段 E · 持续维护
- ☐ **E1** 每功能点完成后按 07-汇报.md 更新 STATUS + worklog + （如变）FILE_GRAPH
- ☐ **E2** 每收束节点完成后写收束报告（落盘 `doc/reports/`）
- ☐ **E3** 监控 5 项关键风险状态（季度复审）

## 外部依赖清单

| 项目 | 路径 | 用途 | 集成方式 |
|------|------|------|---------|
| research-tool | `../调研/research-tool/` | 采集/检索/KG构建 | Python import（本地路径依赖） |
| pdf2zh | `C:/Users/yhn/pdf2zh/` | PDF解析+翻译 | subprocess 隔离调用 |

---

## 模块级状态

### knowledge-mcp（L4 知识工程）— 9 tool — ✅ 全实现

| Tool | 状态 | 说明 |
|------|------|------|
| `acquire_subject` | ✅ file+web / 🔴 video | web 经 research-tool（含 deepen 拆面 + 去重）；video 未实现 |
| `build_knowledge_graph` | ✅ | depth ∈ {toc, concept, full} 全部实现 |
| `query_knowledge` | ✅ | concept / neighbors / path / subgraph |
| `review_kg` | ✅ | quick + full + Mermaid |
| `update_kg` | ✅ | 6 op + versioned 模式 |
| `diff_kg` | ✅ | base_id 对齐版间 diff |
| `rollback_kg` | ✅ | 版本树回滚 |
| `resolve_conflicts` | ✅ | 5 种结构冲突检测 |
| `health` | ✅ | |

### tutoring-mcp（L2/L3/L5/L6 教学）— 12 tool — ✅ 全实现

| Tool | 状态 | 说明 |
|------|------|------|
| `cold_start_probe` | ✅ | 10 道跨难度摸底 |
| `submit_cold_start` | ✅ | 判分 → 先验 + 画像初值 |
| `start_learning_session` | ✅ | Phase 化教学计划 |
| `resume_learning` | ✅ | 续学恢复 |
| `get_learning_progress` | ✅ | 跨 Session 进度 |
| `respond` | ✅ | 评分→诊断→反馈→策略→心流 |
| `next_action` | ✅ | 拓扑序 + BKT 推荐 |
| `interrupt` | ✅ | 5 类意图分类 + 分支响应 |
| `checkpoint` | ✅ | 保存/恢复断点 |
| `learning_insight` | ✅ | 画像洞察 |
| `generate_review_plan` | ✅ | 遗忘曲线复习排程 |
| `health` | ✅ | |

### digest-mcp（多模态产物）— 4 tool — ✅ 全实现

| Tool | 状态 | 说明 |
|------|------|------|
| `digest` | ✅ | 7 种 format（mindmap/notes/quiz/simulation/multi_agent/slides/audio） |
| `build_quiz_html` | ✅ | 独立测验入口 |
| `compile_slides` | ✅ | 独立幻灯片入口（有 pptx→.pptx，否则 HTML） |
| `health` | ✅ | |

### sync-mcp（Obsidian + git）— 6 tool — ✅ 全实现

| Tool | 状态 | 说明 |
|------|------|------|
| `push_to_obsidian` | ✅ | |
| `pull_homework_from_obsidian` | ✅ | |
| `init_subject_repo` | ✅ | git 初始化 |
| `push_artifacts` | ✅ | git 版本化 |
| `watch_obsidian` | ✅ | mtime 轮询 |
| `health` | ✅ | |

### 教学策略 — 7 策略

| 策略 | 状态 | 说明 |
|------|------|------|
| `reduction` | ✅ | 完整状态机 |
| `jiangjie`（降阶法） | ✅ | 完整状态机，消费 PaceConfig |
| `feynman` | 🟡 | 精简状态机 IDLE→PROMPT→EVALUATE→PASS |
| `socratic` | 🟡 | 精简状态机 |
| `pbl` | 🟡 | 精简状态机 |
| `analogy` | 🟡 | 精简状态机 |
| `spaced_repetition` | 🟡 | 精简状态机 |

> 🟡 = 接口完整可调用，状态机可推进，但缺少深度行为（自动评分、自适应、完整状态分支）。
> 这些策略在实际教学中可被 engine 选中并执行，但教学效果不如 reduction 和 jiangjie 充分。

### L5 学习者建模 — 4 模块尚未创建

| 模块 | 状态 | 说明 |
|------|------|------|
| `tracer.py` | 🔴 未创建 | BKT+DKT 双模型知识追踪 |
| `dkt_model.py` | 🔴 未创建 | PyTorch DKT（Phase 3+） |
| `error_diagnosis.py` | 🔴 未创建 | L5 错误诊断聚合 |
| `profiler.py` | 🔴 未创建 | ProfileEvolver |

---

## 代码结构速查

```
ai-tutor/
├── shared/                    L1 基础设施（所有 server 共用）
│   ├── schemas.py             60+ Pydantic 模型 ← 改数据结构先看这里
│   ├── models.py              14 个 SQLAlchemy ORM 表
│   ├── errors.py              TutorError + 错误码
│   ├── storage.py             持久化
│   ├── config.py / logging_config.py / plugins.py / slug.py
│   └── llm_client.py / llm_cache.py + providers/
│
├── servers/
│   ├── knowledge_mcp/         19 文件 · 9 tool
│   ├── tutoring_mcp/          27 文件 · 12 tool · 7 策略
│   ├── digest_mcp/            复习产物生成
│   └── sync_mcp/              Obsidian + git 同步
│
├── scripts/                   demo + 工具（13 文件）
├── doc/                       文档（15 文件）
├── ai-tutor-system-design/    设计历史（40+ 文件）
└── tests/ + BDD/              测试
```

---

## 开发规范化

见 [`DEVELOPMENT-NORM.md`](./DEVELOPMENT-NORM.md)，包含：
- 文件增长控制原则（能加进已有文件就不加新文件）
- 增量添加规范
- 文档同步规则
- 迭代结束清理清单

---

## 下一步做什么（2026-06-13 晚更新）

**当前阶段**：**C1 第一波完成**——`backend/` FastAPI 骨架跑通 :18501（M-001 服务入口 + M-002 API 网关
+ M-003 Electron 客户端入口），810 测试全绿。此前：阶段 B 收尾全完成 + v3.1 走向 C' + 第二批挑战 6/6。
**下一步 = D1 收束节点**（C1 完成触发）→ C2 第二波。

按顺序做：

1. ~~**B 阶段收尾**~~ ✅ 2026-06-13（B1-B5 全过）。
2. ~~**C1 第一波**~~ ✅ 2026-06-13（M-001/M-002/M-003，`backend/` :18501 跑通，810 测试全绿，
   目录名定 backend/，ruff-format 暂不开）。
3. ~~**D1 收束节点**~~ ✅ 2026-06-13 已审计签核（6 依赖漏洞修复，`收束报告-D1-C1.md`）。
4. ~~**C2 第二波**~~ ✅ 2026-06-13 完成 7/7（文档 + M-005/M-004/M-007/M-006/M-017/M-014）。
5. ~~**C3 第三波**~~ ✅ 2026-06-15（M-008 RAG 引擎 + M-009 教学编排，885 测试全绿，覆盖率 96%，
   ADR-0003 务实落地）。**D2 收束节点四阶段已执行，待人签核**。
6. ~~**C4 第四波**~~ ✅ 2026-06-15（M-010~M-013 + M-016，36 测试，backend 124 全绿，commit e1aa27d）。
7. ~~**C5 第五波**~~ ✅ 2026-06-15（M-015 + M-001 收尾，backend 137 全绿，commit 1c2af16）。
   **D3 收束节点四阶段已执行，待人签核** → v2 11 功能点全部就位。
8. ~~**前端补全**~~ ✅ 2026-06-15：#7 WebSocket（/ws/events，commit 69ad4c7）+ #4 五页面/向导/
   WS 客户端 + #5 三可视化（commit fdf3bae）。**Vite build 通过 + Playwright 真浏览器验证**：
   仪表盘拉真后端 5/5 子系统、WS 收 ws.connected、复习页 FSRS 评分往返（良好→S=3.2 下次3天）。
9. ~~**真编译 + 真跑 + 打包**~~ ✅ 2026-06-15：Electron 真跑 + 真 Nuitka 编译全后端（真 serving）
   + **NSIS 安装包 139MB** + 打包应用真跑（内置编译后端，无 .venv）。修 2 个真打包 bug 进 M-015。
   `worklogs/2026-06-15_真编译与真跑-Nuitka-Electron.md`。
10. **唯一剩余**：找不懂代码的人亲手双击 `AI-Tutor Setup 2.0.0.exe` → 走到学完第一课（#21 人工
    验收，AI 无法替代）；可选：真向量后端/NLI 模型（规模化）、前端页面打磨、D2/D3 人签核。
   ⚠️ "v2 第一波过堂"三机制已结构性通过（见挑战清单）。
   **首日决断**：目录名 backend/ vs src/aitutor/（走向决议 §四-5，建议 backend/
   保持与 PRD 验收命令一致）。
   ⚠️ M-014 数据管线（整理环节）仍提前到第一/第二波——换体裁攻击再添铁证：
   骨架节名是体裁性噪声（每换体裁出新形态），类别失衡跨体裁复现
   （98% method → 100% definition），枚举式过滤天花板已两次验证。
3. **C5 波前**：v2 打包发布文档改 Nuitka onedir（R-01 证伪 PyInstaller onefile）；
   C2 波前：pdf2zh集成/数据管线文档去 sys.path 化（走向决议 §五-5/6）。
4. **演示就绪**：FastAPI 科目（199 概念 KG + 75 份 study_pack + 活跃会话
   sess-c882f9cba045）零参数 `tutor_cli learn` 可续（cli_state 已校验恢复）；
   新增 AAAI 论文科目（16 概念，FIX-M 后 0 禁类）可作第二演示样本。
   ⚠️ 教学演示前确认代理活着或设 NO_PROXY（死代理会让判分降级，见持久记忆）。

## 接手挑战清单（谁接手谁过堂，过不了别说"做完了"）

> 来源：22 问题根因调查（`doc/reports/根因分析-22问题.md`）。每条都是可证伪的验收，
> 对应一个曾经真实发生的失败模式。

- [x] **裸手跑通** ✅ 2026-06-13：FastAPI 新科目全程 tutor_cli，0 临时脚本。
- [x] **噪声率过堂** ✅ 2026-06-13：全量扫描 199 概念禁类 1 例边缘（0.5%）<5%，
      裸文件名/代码注释/整句话 = 0（web 语料起点 ≈60%，经 FIX-K 六轮迭代）。
- [x] **答非所问攻击** ✅ 2026-06-13：3 题沾边不答题 → 3/3 判 incorrect（诊断
      reading_error/overgeneralization），correct = 0。
- [x] **死循环回归** ✅ 2026-06-13：21 步 give_exercise 占比 15% <50%，讲解类 55% 穿插。
- [x] **休息触发** ✅ 2026-06-13：FIX-F freezegun 测试——6 轮全对回答走表 50 分钟触发
      `study_streak` 休息建议，非答错驱动；间隔 >15 分钟正确重置。
- [x] **v2 第一波过堂** ✅ 2026-06-15（端到端真管线已沉成自动化测试 `test_e2e_pipeline.py`，
      牺牲品语料 mini_subject.md，不碰演示库）：
      ✅ build_kg 异步任务+进度可查（M-007：POST→202 task_id + GET /api/tasks 轮询）；
      ✅ 同一问题问两遍命中缓存（M-005 SQLite 缓存，跨重启）；
      ✅ 进程重启后会话可续（M-004 session_summaries + v1 SessionStore 落库）；
      ✅ **真建图端到端**：真采集→真 toc 建图(17 概念,纯规则)→图查看→RAG 检索→真 engine
      教学会话→真判分→进 list_sessions，全链一个测试跑通（无 fake/无网络/无真 LLM）。
- ◐ **终极验收（#21）**：把 Claude Desktop 从流程里完全删掉，让一个不懂代码的人从安装走到
      学完第一课。**技术链路 100% 打通实证**（2026-06-15，`worklogs/2026-06-15_真编译与真跑-*.md`）：
      ✅ **真 Nuitka onedir 编译**——全 FastAPI 后端编成原生 exe（184 C 文件）→ 真 serving 且功能
      正确（/health 五子系统 / FSRS / RAG 均由 exe 返回）；抓出并修 2 个真打包 bug（相对导入 /
      pypinyin 包数据）进 M-015；
      ✅ **Electron 运行时真跑**——spawn 真后端→WebSocket 连接→截图（`electron-runtime.png`）；
      ✅ **NSIS 安装包真产出**——`AI-Tutor Setup 2.0.0.exe`（139MB，含外壳+渲染层+编译后端）；
      ✅ **打包应用真跑**——`win-unpacked/AI-Tutor.exe`（isPackaged，**无 .venv**）spawn 内置编译
      后端→渲染 5/5 子系统（截图 `packaged-app.png`）。架构"人→AI→ai-tutor"三层已拆。
      **唯一剩余 = 一个真人**：找不懂代码的人亲手双击安装包走到学完第一课——AI 无法替代的人工
      验收，非技术阻塞。

### 第二批挑战（2026-06-13 复跑后新增 · 出题人：上一任接手者）

> 出题背景：第一批 5/7 已过堂（证据见 worklog 2026-06-12）。这批是本轮**真实踩过的坑**
> 和**没来得及测完的半边**。规则不变：可证伪、贴证据、过不了别说"做完了"。
>
> 出题原则（对出题人自己同样生效，抽签抽回我也照单全收）：
> **全部明牌，无隐藏条件；每题有诚实逃生通道；发现问题 = 得分，瞒报 = 唯一死法。**
> ⚠️ 资产保护红线：`fastapi-houduankaifa`（199 概念 KG + 75 份 study_pack + 活跃会话）
> 是用户的演示科目，任何挑战**不得以它为实验对象**——重建/重采集实验一律用牺牲品科目。

- [x] **v3.1 review 不许盖章式通过** ✅ 2026-06-13：走向决议含 5 风险逐个处置
      （R-16 带本日实测）/ A/B/D 各有否决理由 / §六核对 + 10 条冲突清单；外加
      元发现：设计包曾整体缺位仓库 → 还原入库 bc82a7c。
- [x] **换体裁攻击** ✅ 2026-06-13（①路线）：AAAI 英文论文 PDF（数学公式+学术骨架，
      mineru 8/8 页 + 17 块翻译）→ 禁类 3/19=15.8%（摘要/致谢/参考文献，超标如实贴出）
      → **FIX-M** 骨架节名过滤 + 回归测试 → 重建后 **0/16=0%**；新形态已回灌
      开发清单 M-014 验收红线（C2 波行）。
- [x] **全量扫描，不是抽样** ✅ 2026-06-13：两次审计均全量列名（19 个与 16 个），
      无抽样。
- [x] **判分反向攻击** ✅ 2026-06-13 双线过堂：LLM 主路径 3/3 极简正确判 correct
      0.90+（判分记录 data/scorer_attack_results.json，无冗长偏好）；回退启发式
      被抓现行（含名废话 correct 0.7/切题极简 0.4）→ **FIX-L** 启发式永不授
      correct + 4 条回归（含冷启动不再白拿 0.88 先验）。
- [x] **重建幂等回归** ✅ 2026-06-13：climaoyanceshi 同名复采 + build(full) →
      `kg.rebuild.replace_subject_kg` 自动替换，零手工删库；进度披露：id 漂移
      0/17、BKT 0 孤儿（同内容复采章节号稳定）；暗坑活体补证：论文 KG 滤掉骨架后
      章节号前移（1.5→1.4）——内容变化时漂移真实存在，v2 由 base_id 承接。
      未碰 fastapi-houduankaifa，演示指针备份恢复。
- [x] **不许删测试刷绿** ✅ 2026-06-13：**797 passed**（792 只涨不跌）；
      `git diff HEAD --stat -- '*test*'`：test_kg_toc +44/-0（FIX-K 回归零改动），
      test_research_adapter/test_study_pack 不在 diff；-12 行均为 FIX-L 行为变更
      的旧断言更新，红→绿过程见 worklog §二。

> 第二批挑战 **6/6 全过**（2026-06-13）。证据与红→绿过程：
> `worklogs/2026-06-13_第二批挑战过堂-FIX-L-FIX-M.md`。
> 首批余下 2 项（v2 第一波过堂 / 终极验收 #21）动工后适用，保持未勾。
