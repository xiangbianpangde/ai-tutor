# 历史快照（B4）

> 目的：在 C 波动工开始**迁移/改写**旧设计文档之前，冻结一个可回溯的基线，避免 C-phase
> 的改动覆盖掉 v3.0/v2 的原始设计意图。

## 冻结对象

| 基线 | 现位置（仍是活文档）| 内容 |
|------|------------------|------|
| v3.0 七层认知架构设计 | `ai-tutor-system-design/`（仓库根，59 文件）| L1-L7 分层设计 + data-flow-48h + specs + comparison |
| v2 十份设计文档 | `doc/plan/design/` | 总体架构/中间件/数据管线/research-tool/pdf2zh… |
| v3.1 设计包 | `doc/plan/v3.1-aitutor-design/`（本目录的父级）| 17 模块 M-001~M-017 / 7 ADR / 框架 |

## 冻结方式（为何不是 59 份物理拷贝）

遵循 `DEVELOPMENT-NORM.md §一「不轻易加新文件」`：**不复制 59 份 md 到本目录**——git 历史本身
即完整快照，物理副本只会随时间变陈旧、且双倍占用。改用：

- **git 标签 `v3.0-design-snapshot`**：指向本日（2026-06-13）B 阶段收尾提交，精确冻结上述三套
  设计在 C 波动工**前**的状态。
  - 看快照：`git show v3.0-design-snapshot`　/　`git checkout v3.0-design-snapshot -- ai-tutor-system-design/`
  - 列差异（C 波改了哪些设计）：`git diff v3.0-design-snapshot..HEAD -- ai-tutor-system-design/ doc/plan/`
- **本 README**：让快照从 v3.1 设计包内部可被发现（否则只有知道 tag 名的人能找到）。

## C 波迁移时的用法

走向决议 A4 要求「v2 现有 10 份 design/ 与 v3.1 17 模块交叉引用」。迁移/改写任一旧设计文档前，
对照 `v3.0-design-snapshot` 确认改了什么、为什么改；§五 待落地的两处文档改写
（C5 前 Nuitka onedir / C2 前去 sys.path 化）尤其要留下 before/after 可回溯。
