# 项目树状结构图与设计合理性检查

> 生成时间：2026-05-19 | 范围：全部 55 个文件/目录
> 方法：节点-边图分析 → 识别孤儿、缺失链接、不一致 → 优化命令

---

## 一、完整节点-边图

```
ai-tutor-system-design/ (根)
│
├── README.md ───────────────── 入口，引用全部节点
│
├── 概念设计层 (7个L层文档)
│   ├── L1 <── specs/project-structure.md
│   ├── L2 <── L6, L7
│   ├── L3 ──→ L5;  <── L6
│   ├── L4 ──→ L7;  <── L6, L5, data-flow, adopted-fixes
│   ├── L5 ──→ L6;  <── L6, L3, pgfga, adopted-fixes
│   ├── L6 ──→ L5,L4,L3,L2
│   └── L7 ──→ L6,L4,L5,L2
│
├── specs/ (15个工程规格)
│   ├── shared-schemas.md ──── 定义所有模型 (被5+文件引用)
│   ├── database-schema.md ─── 引用 shared-schemas
│   ├── server-api-spec.md ─── 引用 shared-schemas
│   ├── dkt-implementation.md ─ 引用 L5
│   ├── llm-cost-control.md ─── 引用 L4, L6
│   ├── testing-strategy.md ─── 引用全部server
│   ├── project-structure.md ── 映射全部文件到layer
│   ├── dependency-list.md ──── 外部依赖清单
│   ├── knowledge-triple-schema.md ─→ L4
│   ├── learner-profile-schema.md ──→ L5
│   ├── teaching-strategy-formalism.md → L6
│   ├── tutoring-state-machine.md ──→ L6, L2
│   ├── plugin-registry.md ───→ L1
│   ├── pgfga-integration.md ──→ L5, L6, L2, L7 ⚠ 模型未入schema
│   └── adopted-fixes.md ──────→ L4, L5, L7, server-api, testing ⚠ 5处未执行
│
├── 验证 (2文件)
│   ├── data-flow-48h.md ──────→ L4, L5, L6, L7
│   └── comparison-with-original.md → 全部L层
│
├── research_raw/ (9文件) ───── ⚠ 无README
├── research_clean/ (9文件) ─── ⚠ 无README
└── research_knowledge/ (2文件) ─ ✓ 来源索引完整
    ├── 00-主表.md → research_clean/
    └── 补充参考-*.md → research_clean/ + L4-L7
```

---

## 二、发现的五类结构问题

### 问题1：5处已确认但未执行的文档更新 (adopted-fixes遗留)

| 目标文件 | 待新增 | 严重度 |
|---------|--------|--------|
| L4-knowledge-engineering.md | §7 KG人工确认 + §8 时间校准 | **高** |
| L5-learner-modeling.md | cold-start assessment方法 | **高** |
| L7-interaction-layer.md | review_kg / update_kg tool | 中 |
| specs/server-api-spec.md | 同上 | 中 |
| specs/testing-strategy.md | 48h验证实验E2E | 低 |

### 问题2：PGFGA数据模型孤悬——定义在集成文档但未入schema

| 模型 | 定义位置 | 应在位置 |
|------|---------|---------|
| FlowLevel (IntEnum) | pgfga-integration.md | shared-schemas.md §五 |
| FlowSignals (BaseModel) | pgfga-integration.md | shared-schemas.md §五 |
| NonJudgmentFirewall (类) | pgfga-integration.md | shared-schemas.md §六 |
| GainLoopMonitor (类) | pgfga-integration.md | shared-schemas.md §六 |
| PGFGARespondTemplate (类) | pgfga-integration.md | shared-schemas.md §六 |

风险：开发工程师只看 `shared-schemas.md` 作为接口合同。

### 问题3：research目录无索引——知识可追溯链断裂

research_raw/ 和 research_clean/ 各含9个裸文件，无README说明来源URL和清洗方法。

### 问题4：L7与server-api-spec覆盖同一内容但粒度不同，无交叉引用

L7描述"是什么"，server-api-spec描述"怎么实现"。不矛盾，但无互相引用。

### 问题5：Concept.id 格式未被Pydantic validator强制约束

data-flow和schema注释写了格式约定，但无regex validator。

---

## 三、合理性评估

| 检查项 | 状态 |
|--------|------|
| 无循环文档引用 | ✓ 全部单向 |
| 概念层依赖方向正确 | ✓ L7→L6→L5/L4/L3→L2→L1 |
| MCP Server无循环import | ✓ 通过共享存储通信 |
| 每个spec映射到至少一个L层 | ✓ 15→15 |
| README覆盖全部节点 | ✓ 55个节点全部可导航 |
| 调研方法论流程完整 | ✓ raw→clean→knowledge三阶段 |

---

## 四、优化命令 (按优先级)

**优1**: 执行adopted-fixes的5处更新 (30min)
→ 编辑L4、L5、L7、server-api-spec、testing-strategy

**优2**: PGFGA模型同步到shared-schemas (10min)
→ FlowLevel、FlowSignals入L5段；NonJudgmentFirewall入L6段

**优3**: research目录加README (5min)
→ raw: 来源URL列表+日期 | clean: 清洗说明

**优4**: 补全交叉引用+validator (5min)
→ L7加一行指向server-api-spec | Concept.id加regex
