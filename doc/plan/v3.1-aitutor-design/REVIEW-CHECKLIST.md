# AITutor V3.1 设计包 · 1 小时 Review 清单

> 实现状态: ⏸️ 计划阶段交付 · 待 review
> 来源：plan-writing 工作流 `wzf39yqb8` · 生成于 2026-06-02
> 全包：~120 份文件 / 7 棒收敛指数全 ≥ 0.96 / 0 硬回退
> 本清单聚焦**关键决策**与**风险点**，不重复已有内容。

---

## 60 分钟 7 段 Review 路线

### 段一 5 min · 全局判断
读 `01-requirement/PRD-AITutor-V3-V3.1-20260602.md` 全文 + `V3.1-vs-V2-桥接.md`
- [ ] 21 个原问题（`doc/发现问题.txt`）是否全部有对应解法？
- [ ] V3.1 PRD 是否吸收了 v2 现有 10 份设计文档的关键决策？
- [ ] 4 轮 PRD 迭代（V1→V2→V3→V3.1）22/22 RA 反馈采纳是否合理？
- [ ] v3.1 与 v2 关系（替代 / 并列 / 局部采纳）是否明确？

### 段二 10 min · 调研结论
读 `doc/research/v3.1-aitutor-research/RESEARCH-AITutor-V3.1-20260602.md` 关键章节
- [ ] 18 个调研 run 是否覆盖了 4 大主题（MCP 迁移 / 教学系统 / 打包 / 红线检测）？
- [ ] **HaluGate 三级级联抗幻觉**（DeBERTa + Haiku + GPT-4 / 400× TCO 降低）是否接受？
- [ ] LangGraph 1.0 RAG 编排是否接受？
- [ ] FastAPI 0.115 + Python 3.11 + uv 技术栈是否接受？

### 段三 10 min · 业务梳理
读 `02-business/` 5 份核心文件（BP/BR/DD/EX/AR）
- [ ] 21 业务流程 / 50 业务规则 / 48 数据实体 / 24 异常场景是否完备？
- [ ] 18 条歧义消除记录是否有遗漏？OC-1（GUI 形态保留为 PM 决策项）是否仍阻塞？
- [ ] 5 个红线专项异常（EX-021/029~033）是否覆盖开发规范全部红线？

### 段四 10 min · 架构与模块
读 `03-architecture/MP-AITutor-V3.1-20260602.md` + `04-tech-architecture/TA-AITutor-V3.1-20260602.md`
- [ ] **17 个模块 M-001~M-017** 的划分是否合理（v2 是 11 功能点）？对照 `V3.1-vs-V2-桥接.md` 看映射
- [ ] 4 视图（逻辑/物理/数据/部署）+ 7 ADR 决策是否接受？
- [ ] 12 条结构风险（5 高 + 4 中 + 3 低）是否需要补充风险预案？

### 段五 10 min · 详细设计
读 `05-detailed-design/DD-AITutor-V3.1-20260602.md` + `MD-AITutor-V3.1-20260602.md`
- [ ] 8.8 验收标准的接口契约是否完整？
- [ ] 17 模块细化方案是否可实施？（含 24 异常处理策略 + DDR/DH 决策/假设）

### 段六 10 min · 文件框架
读 `06-framework/M-001~M-010` 抽样 3-5 个文件（每个模块下有 5 份：FF/API/FC/FDR/FH）
- [ ] 17 模块文件框架的注释完整度（FRI=0.95~1.00）是否满足开发需要？
- [ ] 85 份框架文档是否过多/可裁剪？
- [ ] 命名规范 / 接口签名 / 异常处理 / 测试场景是否覆盖？

### 段七 5 min · 模拟与闭环
读 `doc/reports/v3.1-aitutor-simulation/`
- [ ] 端到端 15 拍轨迹是否自洽？（模拟命令 `ai-tutor research run "技术大会 talk 调研" --video-url "..."`）
- [ ] 3 个异常分支演练（EX-007/008/012）是否覆盖关键故障？
- [ ] 三层闭环（PRD 迭代 / 下游反馈 / 终局）判定是否成立？

---

## ⚠️ 关键风险点（必看）

| # | 风险 | 来源 | 优先级 |
|---|------|------|--------|
| 1 | R-16 LLM 法官自恋偏差 | 调研报告 V3.1 | 🟡 中（建议 DD 阶段补充去偏策略）|
| 2 | R1 M-008 RAG 引擎内聚度模糊 | 00-索引.md | 🟡 中（建议 DD-M 阶段进一步拆分）|
| 3 | C2 EX-013 异常审计策略待审 | 00-索引.md | 🟡 中（建议与 SOC2 / GDPR 合规对一下）|
| 4 | pdf2zh AGPL 法务风险 | AR-001 选型债务 | 🔴 高（商业化前必走法务）|
| 5 | sqlite-vec 0.1.x API 稳定性 | AR-001 选型债务 | 🟡 中（锁定版本 / 监控上游）|

---

## ✅ Review 完成后建议（按 07-汇报.md 流程）

- [ ] **更新 `STATUS.md`**（按 DEVELOPMENT-NORM §四 回答 3 问题：项目阶段 / 完整度 / 下一步）
- [ ] **写 1 份收束报告**（落盘 `doc/reports/收束报告-v3.1.md`）—— **本步骤是"收束节点"必做**（按 03-第一步.md 1.6 预设收束节点）
- [ ] **更新 `meta/FILE_GRAPH.md`** 把 v3.1 归类写完整
- [ ] **跟 v2 现有 10 份设计文档做交叉引用**（找出冲突 / 重复 / 补充）—— 见 `V3.1-vs-V2-桥接.md`
- [ ] **决定 V3.1 走向**（推荐：作为 v2 升级参考，**并行保留**，v2 现有 10 份 design/ 不动）

---

## 📁 设计包结构速查

```
doc/plan/v3.1-aitutor-design/
├── README.md                                    ← 设计包入口（00-索引.md 改名）
├── REVIEW-CHECKLIST.md                          ← 本清单
├── V3.1-vs-V2-桥接.md                           ← 17 模块 ↔ 11 功能点映射
├── 01-requirement/                              ← PRD V3.1 + 追溯矩阵 + 待确认项 (11 份)
├── 02-business/                                 ← BP/BR/DD/EX/AR 5 类 (7 份)
├── 03-architecture/                             ← 4 视图/模块/边界/ADR (13 份)
├── 04-tech-architecture/                        ← 选型/API/部署/安全 (10 份)
├── 05-detailed-design/                          ← DD/MD/IC/DS/FS/CS/EX/DDR/DH (9 份)
└── 06-framework/                                ← 17 模块 M-001~M-017 / 85 份框架文档

doc/research/v3.1-aitutor-research/              ← 调研报告 V3.1 + 18 runs + 57 来源 (16 份)
doc/reports/v3.1-aitutor-simulation/             ← 端到端轨迹 / 异常演练 / 闭环 (6 份)
```

---

来源标注：[00-索引.md] + [V3.1 PRD §11 附录] + [convergence-summary.md] + [closure-verdict.md]
