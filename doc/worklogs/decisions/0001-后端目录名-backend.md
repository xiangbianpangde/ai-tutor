# ADR-0001: v2 后端目录名定为 `backend/`

> 日期: 2026-06-13
> 状态: 已采纳

## 背景

走向决议（C'）确定 v2 主体推进后，C1 第一波动工首日须先定后端代码的根目录名。
存在两套并存写法：v3.1 框架骨架（06-framework/M-001/src/aitutor/）按 `src/aitutor/` 设计；
v2 设计文档与 BDD 规格按 `backend/`。两者不统一会导致 import 路径、验收命令、打包配置分叉。

## 决策

后端根目录用 **`backend/`**。`python -m backend.main` 为统一入口。

## 考虑的替代方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **backend/**（采纳）| BDD 01 验收命令即 `uv run python -m backend.main`；设计文档-后端API层 通篇 backend/；PRD S1 验收 grep backend/；与 servers/ 平级直观 | 与 v3.1 框架骨架的 src/aitutor/ 命名不一致（但骨架是桩，未入生产） |
| src/aitutor/ | 符合 src-layout 打包最佳实践；v3.1 框架骨架现成 | 推翻 BDD 验收命令 + 全部 v2 文档；骨架引用 `aitutor.shared.*` 等绕开 v1 现存资产（违背走向决议 C' 复用原则）|

## 后果

- 正面：与 BDD/PRD/v2 设计文档一致，验收命令可直接跑；新人按文档即得正确路径。
- 负面：v3.1 框架桩文件（doc/ 下）的 `aitutor.*` 引用与生产不一致——但它们是计划产物、已 exclude 出 lint，迁入生产时按 backend/ 重写。

## 相关

- 走向决议 §四-5（冲突清单 #5）/ 设计文档-后端API层 / BDD specs/01-基础骨架.md
- 实现：`backend/`（C1 提交 ef49a8d）
