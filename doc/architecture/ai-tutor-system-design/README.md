# AI Tutor System Design — 7 层认知学习架构

> 版本：v3.0（架构重设计）  
> 日期：2026-05-19  
> 目标：48 小时系统学完一个大学科目，私人 AI 辅导系统

---

## 快速导航

### 概念设计（7 层架构）

| 文件 | 内容 | 重要度 |
|------|------|--------|
| [L4-knowledge-engineering.md](./L4-knowledge-engineering.md) | 知识工程引擎：多源采集→抽取→融合→推理→演化 | ★★★★★ |
| [L5-learner-modeling.md](./L5-learner-modeling.md) | 学习者建模：DKT+BKT 知识追踪、错误诊断、认知负荷、画像 | ★★★★★ |
| [L6-adaptive-teaching-engine.md](./L6-adaptive-teaching-engine.md) | 自适应教学引擎：6 种策略原语状态机、实时干预、决策循环 | ★★★★★ |
| [L3-long-memory-engine.md](./L3-long-memory-engine.md) | 长期记忆引擎：个性化遗忘曲线、知识互联、多因子复习调度 | ★★★★ |
| [L7-interaction-layer.md](./L7-interaction-layer.md) | 交互层：4 个 MCP server 的 Tool 签名、打断机制、进度可视化 | ★★★★ |
| [L2-short-memory.md](./L2-short-memory.md) | 短期记忆：三层缓存、聚焦管理、中断/恢复协议 | ★★★ |
| [L1-infrastructure.md](./L1-infrastructure.md) | 基础设施：4 类存储抽象、插件注册表、错误模型、项目结构 | ★★★ |

### 工程实施规格（`specs/`）

| 文件 | 内容 | 用途 |
|------|------|------|
| [shared-schemas.md](./specs/shared-schemas.md) | 所有跨层 Pydantic 模型完整定义 | 接口合同 |
| [database-schema.md](./specs/database-schema.md) | 完整 DDL + Alembic migration 策略 | 数据库实现 |
| [server-api-spec.md](./specs/server-api-spec.md) | 4 个 MCP server 的完整 API 规格 + 实现模板 | 接口合同 |
| [dkt-implementation.md](./specs/dkt-implementation.md) | DKT 模型架构、训练、冷启动方案 | Phase 3 参考 |
| [llm-cost-control.md](./specs/llm-cost-control.md) | LLM 调用分级、批处理、缓存、预算 | 成本控制 |
| [testing-strategy.md](./specs/testing-strategy.md) | 分层测试、mock 边界、CI 配置、验收标准 | 质量保证 |
| [project-structure.md](./specs/project-structure.md) | 完整文件树 + 每个文件的职责 | 项目搭建 |
| [dependency-list.md](./specs/dependency-list.md) | Python 包 + Docker 镜像 + 外部服务清单 | 环境搭建 |
| [knowledge-triple-schema.md](./specs/knowledge-triple-schema.md) | KG 三元组 + 概念节点 + Manifest 格式 | L4 开发参考 |
| [learner-profile-schema.md](./specs/learner-profile-schema.md) | 学习者画像 JSON Schema + 更新语义 | L5 开发参考 |
| [teaching-strategy-formalism.md](./specs/teaching-strategy-formalism.md) | 6 种策略原语完整状态机定义 | L6 开发参考 |
| [tutoring-state-machine.md](./specs/tutoring-state-machine.md) | 教学会话顶级状态机 + 中断协议 | L6/L7 开发参考 |
| [plugin-registry.md](./specs/plugin-registry.md) | 插件注册表 + 健康检查 + 降级链 | L1 开发参考 |
| [pgfga-integration.md](./specs/pgfga-integration.md) | PGFGA 集成：心流、防火墙、SDT 支持、增益回路 | 动机层 |
| [adopted-fixes.md](./specs/adopted-fixes.md) | 采纳修正：KG确认、摸底测验、时间校准、48h实验 | 实施计划 |
| [architecture-audit.md](./specs/architecture-audit.md) | 树状结构图 + 设计合理性检查 + 优化命令 | 质量审计 |
| [补充参考-OpenMAIC-NotebookLM.md](./research_knowledge/补充参考-OpenMAIC-NotebookLM.md) | OpenMAIC/NotebookLM 调研：能力矩阵、可采纳建议、必须避免的陷阱 | 参考 |

### 调研资料

| 目录 | 内容 |
|------|------|
| [research_raw/](./research_raw/) | 阶段1：原始爬取（9个文件） |
| [research_clean/](./research_clean/) | 阶段2：第一次清洗（去噪） |
| [research_knowledge/](./research_knowledge/) | 阶段3+5：知识树主表 + 补充参考产出 |

### 验证与对比

| 文件 | 内容 |
|------|------|
| [data-flow-48h.md](./data-flow-48h.md) | 48 小时完整数据流：从"我要学高数"到学习报告 |
| [comparison-with-original.md](./comparison-with-original.md) | 与原始 v2.1 6-server 设计的全面对比 |

---

## 七层架构

```
┌──────────────────────────────────────────────────────────────┐
│  L7  交互层 — 多模态对话、随时打断、进度可视化                     │
├──────────────────────────────────────────────────────────────┤
│  L6  自适应教学引擎 — 策略库、策略选择、实时调整、干预时机           │
├──────────────────────────────────────────────────────────────┤
│  L5  学习者建模 — 知识状态追踪、认知负荷检测、错误类型诊断            │
├──────────────────────────────────────────────────────────────┤
│  L4  知识工程 — 多源采集→抽取→融合→推理→演化（知识生命周期）          │
├──────────────────────────────────────────────────────────────┤
│  L3  长期记忆 — 遗忘曲线建模、复习调度、跨科目知识关联               │
├──────────────────────────────────────────────────────────────┤
│  L2  短期记忆 — 会话上下文、当前聚焦、中断恢复                       │
├──────────────────────────────────────────────────────────────┤
│  L1  基础设施 — 存储、插件、认证、日志、监控、多模态工具链            │
└──────────────────────────────────────────────────────────────┘
```

## 设计哲学

- **认知教练而非课件工厂**：系统必须对学生认知状态有模型，动态调整策略
- **每一层都可独立验证**：L4 生成 KG 时不需要 L5，L5 建模时不需要 L6
- **模型驱动的教学**：DKT（深度学习知识追踪）+ BKT（贝叶斯）双模型互补
- **闭环进化**：学生反馈 → 更新模型 → 调整策略 → 产生新数据
- **策略形式化**：每种教学方法不是 prompt，是可执行的有限状态机 + 参数

## 核心差异（vs 原 design）

| 维度 | 原设计 | 本设计 |
|------|--------|--------|
| 学生模型 | 无 | L5 知识状态 + 错误诊断 + 画像 |
| 教学策略 | "降阶法"是一句话 | L6 6 种策略原语 + 自动选取 |
| 知识管理 | 简单 KG + 3 种边 | L4 12 种语义关系 + 质量门 + 版本演化 |
| 记忆系统 | Redis + SQLite | L3 个性化遗忘曲线 + 知识互联网络 |
| 闭环 | 无 | 学生反馈 → 更新模型 → 策略调整 |
| 工具数量 | 30+ | 精简 10+ 个智能 tool |

---

## 实施分组

| 分组 | 层 | 工作范围 | 预估 |
|------|-----|----------|------|
| **根基** | L1, L2 | 基础设施 + 短期记忆 | 1 周 |
| **知识底座** | L4 | 知识工程全链路（采集→抽取→融合→KG） | 3 周 |
| → Phase 0.5 | L4, L5 | KG 人工确认节点 + 摸底测验 + 校准准备 | 0.5 周 |
| **学生模型** | L5, L3 | 学习者建模 + 长期记忆引擎 + 心流追踪（PGFGA） | 2 周 |
| **教学引擎** | L6, L7 | 自适应教学 + 交互层 + 非评判防火墙 + SDT 支持 | 2.5 周 |
| **集成验收** | 全部 | 48h 端到端演示 + 全链路测试 | 1 周 |
| → Phase 4.5 | 验证 | 48h 验证实验（真实学生 + 简化教材） | 1 周 |

总计：约 11 周

### 最近更新

- 2026-05-19: 新增 PGFGA 集成层——心流追踪、非评判防火墙、SDT 三大需求支持、正向增益回路（见 `specs/pgfga-integration.md`）
- 2026-05-19: 采纳架构审查修正——KG人工确认、摸底测验、时间校准、48h验证实验（见 `specs/adopted-fixes.md`）
