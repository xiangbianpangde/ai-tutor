# ADR-0002: `backend.core` 桥接 `shared/`（复用而非重写）

> 日期: 2026-06-13
> 状态: 已采纳

## 背景

走向决议 C' 定调"迁移而非重写"：v1 的 `shared/`（60+ Pydantic 模型、ORM、storage、errors）
与 `servers/`（4 引擎 32 tool、797 测试）是经实战校准的资产，不作废重写。但 BDD 01 场景2
又要求 `backend/core/` 存在且 import-linter 无违规。如何让 backend 复用 shared 又不立刻物理搬迁、
还能守住架构边界？

## 决策

建 **`backend.core` 薄桥接层**：re-export `shared` 的 storage/errors/logger 等基础设施。
backend 其余层（routers/app）**只从 `backend.core` 取基础设施**，不直接 import `shared`。
未来 `shared/` 物理迁入 `backend/core/` 时，上层 import 一行不改。

并加 import-linter 契约固化边界：`backend.core` 禁依赖 `backend.routers/app/main` 与 `servers`。

## 考虑的替代方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **backend.core 桥接 re-export**（采纳）| 零搬迁即复用；上层与 shared 解耦；未来迁移无痛；契约可验 | 多一层间接 |
| 立刻把 shared/ 物理迁进 backend/core/ | 目录即终态 | 797 测试全部改 import，高风险大改，违背 C1 范围 |
| backend 直接 import shared | 最省事 | 边界糊掉；shared 将来迁移要改所有上层；BDD 场景2 的 backend/core/ 落空 |

## 后果

- 正面：C1 即复用全部 v1 引擎能力，797 测试不动；边界由契约（import-linter 3 kept）守住。
- 负面：`backend.core` 当前只是 re-export 门面，真正的物理迁移延后（C2+ 按需）。

## 相关

- 走向决议 §三（选 C' 的复用原则）/ BDD specs/01 场景2
- 实现：`backend/core/__init__.py` + pyproject [tool.importlinter] 第 3 契约（C1 提交 ef49a8d）
