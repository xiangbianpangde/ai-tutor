# ai-tutor 开发规范

> 目的：防止持续迭代带来的结构和文档膨胀，让每次回来的导航成本不增长。

---

## 一、代码增量原则

### 1.1 能加进已有文件的，不加新文件

加新文件前先问三个问题：

1. **这个逻辑能不能放进已有文件？** 比如给 `engine.py` 加一个方法，而不是新建 `xxx_handler.py`
2. **现有文件超过 500 行了吗？** 超过了才考虑拆分；没超过说明空间够
3. **这个文件里有多少代码是这个包公用的？** 如果只有一个调用方，就不该是独立文件

**违反示例**（来自当前代码库）：
- `non_judgment_firewall.py`（~80 行）→ 应放进 `engine.py` 或 `teaching_actions.py`
- `pace_controller.py`（~60 行）→ 应放进 `flow.py`
- `gain_loop_monitor.py`（~100 行）→ 应放进 `flow.py`

### 1.2 合并优于拆分

倾向 | 理由
---|---
一个文件装 1-2 个相关类 | 减少 `import` 链和文件导航
不拆工具性辅助函数 | 除非有 3 个以上不同的调用方
一组版本管理操作放一个文件 | `kg_update.py` + `kg_diff.py` + `kg_rollback.py` → `kg_lifecycle.py`

### 1.3 新文件创建检查清单

加一个新 `.py` 文件前，确认：

- [ ] 已有文件中确实没有合适的位置
- [ ] 这个文件预计有 ≥150 行有价值的逻辑（不是配置/常量/接口声明）
- [ ] 测试文件也跟着更新了

---

## 二、迭代结束时清理清单

每个功能点/阶段完成时，做以下 5 件事（5 分钟）：

- [ ] **STATUS.md**：把对应项从"待办/进行中"移到"已完成"
- [ ] **临时笔记**：开发过程中写的 `.md` scratch note、验证记录 → 删掉
- [ ] **注释清理**：把 `# TODO: ...` 变成 `# DONE: ...` 或直接删掉
- [ ] **测试确认**：`pytest` 全绿
- [ ] **git commit**：`git add . && git commit -m "作用域: 做了什么事"`

---

## 三、设计文档同步规则

### 3.1 文档状态标记

每个 `doc/` 和 `ai-tutor-system-design/specs/` 下的 `.md` 文件，**文件第一行或第二行**加状态标记：

```markdown
> 实现状态: ✅ 已实现 | 🟡 部分实现 | 🔴 待实现
```

这样你打开任何设计文档，3 秒就知道它是指南还是历史。

### 3.2 哪些文档需要标记

- `ai-tutor-system-design/specs/*.md` — 全部标记
- `ai-tutor-system-design/L*.md` — 标记（L1-L7 各层）
- `doc/*.md` — 已在 ROADMAP.md 里有状态的可跳过，其余标记

### 3.3 什么时候更新

- 实现完成时 → 把标记从 🟡/🔴 改成 ✅
- 设计变更时 → 更新文档内容 + 保持标记准确
- 确定不再实施时 → 在标记后加 `（已冻结）`

### 3.4 ROADMAP.md 状态同步

ROADMAP.md 的切片表（§1）和维护清单（§5）保持为真实来源，但不要在 ROADMAP 里列举不存在的文件（如 `tracer.py`、`dkt_model.py`）。如果要列计划中的文件，加 `[planned]` 前缀。

---

## 四、STATUS.md 维护规则

`STATUS.md` 是会话级单一入口，维护规则：

- **功能完成时**：更新对应项状态
- **功能新增时**：加入对应模块下
- **功能删除时**：从 STATUS.md 移除
- **"下一步做什么"段**：每次回来写当时的目标

不需要把 ROADMAP 的全部细节搬进 STATUS，STATUS 只要回答：
1. 现在项目处于什么阶段
2. 哪些是完整的 / 哪些是 stub / 哪些没开始
3. 下一步准备做什么

---

## 五、提交信息规范

```
<scope>: <简短描述>

允许的作用域：
kg        — knowledge-mcp 相关
tutor     — tutoring-mcp 相关（含 engine/策略/心流）
digest    — digest-mcp 相关
sync      — sync-mcp 相关
shared    — shared/ 基础设施
doc       — 文档/规范
norm      — 开发规范本身
test      — 测试相关
fix       — bug 修复
chore     — 杂项（依赖/配置/清理）
```

示例：
- `tutor: 完善 feynman 策略完整状态机`
- `kg: resolve_conflicts 添加语义对立检测`
- `doc: 更新 ROADMAP §5 测试清单`
- `fix: intent_classifier 空输入崩溃`
- `chore: 删除开发临时验证笔记`

---

## 六、AI 提示词规范（给 AI 开发者的前置说明）

当用 AI 进行开发时，在 prompt 中包含：

> 本仓库规范：少加新文件。能加进已有的就不创建新的。保持 STATUS.md 和文档状态标记同步。

这能让 AI 助手的行为与项目规范对齐，而不是每次都生成一个新文件。
