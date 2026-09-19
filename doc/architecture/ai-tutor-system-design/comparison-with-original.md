# 与原 v2.1 设计的对比

> v2.1 = 用户的原始 6-server MCP 套件设计  
> v3.0 = 本次重设计（7 层认知架构）

---

## 一、架构哲学差异

| | v2.1 | v3.0 |
|---|------|------|
| **隐喻** | 印刷厂：输入→加工→课件产出 | 认知教练：对学生认知状态有模型，动态调整 |
| **核心循环** | 单向流水线 | 闭环：学生反馈→更新模型→调整策略 |
| **对学生假设** | 白板，每次从头开始 | 有历史、有画像、有情感 |
| **教学法** | "降阶法"等关键词，未形式化 | 6 种策略原语的可执行状态机 |
| **知识模型** | 简单 KG + 3 种边 | 12 种语义关系 + 质量门 + 版本演化 |

---

## 二、组件映射

| v2.1 Server | v3.0 对应 | 变化 |
|-------------|----------|------|
| kb-acquire-mcp | L4 + knowledge-mcp | 合并，增加知识融合 + 版本管理 |
| kb-graph-mcp | L4 + knowledge-mcp | 同上；状态存储职责剥离到 L1 StateStore |
| pedagogy-mcp | L6 | 融入自适应教学引擎，作为策略原语 |
| tutoring-mcp | L2 + L6 + L7 | 核心扩展：从简单步骤推进→完整教学决策循环 |
| knowledge-digest-mcp | digest-mcp | 保留独立，但工具从 7 个合并为 1 个 digest() |
| sync-mcp | sync-mcp | 基本不变 |
| shared/ | L1 | 从薄抽象升级为 4 类存储 + 插件注册表 |
| — | L3 | **新增**：长期记忆引擎（个性化遗忘曲线） |
| — | L5 | **新增**：学习者建模（DKT+BKT+错误诊断+画像） |

---

## 三、工具数量对比

| v2.1 | 数量 | v3.0 | 数量 |
|------|------|------|------|
| fetch_textbook + pdf_to_markdown + transcribe_video + web_collect + normalize_corpus | 5 | acquire_subject | **1** |
| build_knowledge_graph + query_kg + add_kg_relation + 两个memory + summarize | 6 | build_knowledge_graph + query_knowledge + resolve_conflicts | **3** |
| design_curriculum + 5 个 design_* + schedule_review | 7 | (融入 L6 策略选择引擎) | **0** |
| build_quiz_html + render_mindmap + generate_slide_image + ... | 7 | digest (一个入口) | **1** |
| start_session + next_step + submit_answer + 6 个其他 | 9 | start_learning_session + next_action + respond + interrupt + 2 个其他 | **6** |
| 4 个 sync tool | 4 | 4 个 sync tool | **4** |
| **总计** | **~38** | **总计** | **~15** |

**变化原因**：不是减少功能，而是把编排逻辑内化到 engine 里，MCP tool 只暴露"智能入口"。

---

## 四、关键数据模型新增

| 模型 | v2.1 | v3.0 |
|------|------|------|
| 概念节点 | 6 个字段 | 20+ 字段（含分类学、难度向量、embedding） |
| 语义关系 | 3 种 | 12 种 |
| 知识状态 | mastery_scores (float) | DKT + BKT 双模型 + 错误诊断 |
| 学习者 | 无 | 21 维画像（认知+元认知+行为+情感+知识） |
| 长期记忆 | Redis + SQLite 键值 | 个性化遗忘曲线 + 知识网络 + 复习调度器 |
| 教学策略 | 字符串 | 可执行状态机 + 参数 |

---

## 五、用户体验差异

| 场景 | v2.1 | v3.0 |
|------|------|------|
| 学生答错 | "错了。答案是X。" | "你的错误类型是符号混淆，根本原因是量词不熟。我们先回顾一下∀和∃的含义。" |
| 学生打断 | 未设计 | 保存上下文→分类意图→不同处理→可恢复 |
| 学习太累 | 无感知 | 自动检测认知负荷→建议休息 |
| 复习 | "7天后复习" | 基于个人遗忘曲线 + 多因子优先级调度 |
| 跨科目 | 无 | 自动检测概念关联→联合复习 |
| 长期使用 | 每次从头 | 画像演化→越用越懂你 |

---

## 六、实施复杂度对比

| | v2.1 | v3.0 |
|---|------|------|
| MCP Server 数量 | 6 | 4 |
| 代码量估计 | ~15K lines | ~25K lines |
| 核心新增工作量 | — | L5 (3周) + L6 (2.5周) + L3 深度(2周) |
| 实施总时间 | ~9.5 周 | ~9.5 周（更深但server更少） |
| 需要训练数据的组件 | 0 | DKT (需要历史交互数据) |

---

## 七、v3.0 的风险与缓解

| 风险 | 缓解 |
|------|------|
| DKT 需要训练数据 | Phase 1 用 BKT 兜底，DKT 冷启动用相似用户初始化 |
| L6 状态机复杂度 | 先实现降阶法+费曼法，逐步增加其他策略 |
| 个性化遗忘曲线需要时间积累 | 用冷启动默认值，3~5 次复习后切换到个性化拟合 |
| LLM 调用成本（KG 抽取大量调用） | 分级处理：toc 模式免费（纯规则），concept 模式用 cheap model |
| L5 画像需要行为数据 | 先提供合理的 cold-start 默认值，随使用逐步演化 |

---

## 八、迁移路径（从现有 knowledge-digest）

```
当前状态:
  knowledge-digest/ (Skill v2.1, markdown 指令型)

Step 1: 迁移 → digest-mcp
  - 把 SKILL.md 的 7 个 format 指南提炼为 digest() tool 的内部逻辑
  - 把 references/format-*.md 注册为 MCP Resources
  - 把 assets/quiz-template.html 保留为 digest-mcp/assets/

Step 2: 扩展 → knowledge-mcp + tutoring-mcp + L1 基础设施
  - 按 README.md 的实施分组顺序推进

Step 3: 启用 L5 + L3 + L6
  - 当 knowledge-mcp 和 tutoring-mcp 骨架跑通后，
    逐步在 tutoring-mcp 内部引入学习者建模和教学决策引擎

原 knowledge-digest Skill 可以保留为"轻量版"（不做 MCP 化），
或完全废弃——由 digest-mcp 替代。
```
