# FDR-M014-AITutor-V3.1-20260602 — M-014 框架决策记录

> **模块**: M-014 数据管线
> **日期**: 2026-06-02
> **作者**: DD-M-014-20260602
> **来源**: [DD-001:MD-M014] + [DD-M推断:依据=DD-001:soul 3.7 FDR 模板]

---

## FDR-001 — 翻译子能力采用子目录命名空间隔离

| 字段 | 内容 |
|------|------|
| 决策编号 | FDR-001 |
| 决策标题 | 翻译 3 后端用 `translate/` 子目录而非平铺 |
| 决策状态 | 已接受 |
| 决策内容 | 在 `aitutor/ingest/` 下创建 `translate/` 子目录，包含 3 个翻译后端 + 工厂方法 |
| 决策理由 | 1) 与 M-008 RAG 引擎的 `rag/translation/adapter.py` 模式一致（DD-001:FS-M008 子能力命名空间隔离）<br>2) 翻译子能力后续可能新增更多后端（如 Azure Translator），子目录便于扩展<br>3) 平铺会与 `clean.py`/`chunk.py` 混在同一层，职责不清 |
| 拒绝的替代方案 | 平铺：`aitutor/ingest/pdf2zh.py + pdfplumber.py + lmstudio.py` — 与 Stage 文件（clean/chunk/ingester）混在一起，违反"子能力 vs 阶段"职责分离 |
| 影响范围 | `aitutor/ingest/translate/` 全部 5 个文件 |
| 相关 FDR | 无 |
| 来源标注 | [DD-001:MD-M014 sm014-translate] + [DD-M推断:依据=M-008 翻译子能力命名空间模式] |

---

## FDR-002 — DataPipeline 采用 Template Method 而非 Builder

| 字段 | 内容 |
|------|------|
| 决策编号 | FDR-002 |
| 决策标题 | DataPipeline 用 Template Method 模式（非 Builder） |
| 决策状态 | 已接受 |
| 决策内容 | DataPipeline 作为 Template Method 的模板类，固定 4 阶段流程（translate→clean→chunk→ingest），各 Stage 子能力通过依赖注入替换 |
| 决策理由 | 1) DD-001:MD-M014 明确指定设计模式为 **Template + ThreadPool**<br>2) Template Method 4 阶段顺序固定，与 FSM 状态机一一对应<br>3) Builder 模式适合多配置组合场景，此处 4 阶段顺序是强约束，不适用 |
| 拒绝的替代方案 | Builder 模式：允许阶段顺序自定义 — 与 FSM 状态机定义冲突 |
| 影响范围 | `aitutor/ingest/pipeline.py` + 4 个 Stage 文件 |
| 相关 FDR | 无 |
| 来源标注 | [DD-001:MD-M014 设计模式] |

---

## FDR-003 — 状态机独立文件而非内嵌 pipeline.py

| 字段 | 内容 |
|------|------|
| 决策编号 | FDR-003 |
| 决策标题 | PipelineStateMachine 独立成 `state_machine.py` |
| 决策状态 | 已接受 |
| 决策内容 | 将 FSM 状态机独立为 `aitutor/ingest/state_machine.py` |
| 决策理由 | 1) 与 M-004 Session/M-009 Teaching 一致（DD-001:FS-M004/M009 都独立 state_machine.py）<br>2) 状态机含 7 状态 + 转移表 + 历史记录，逻辑量足够独立<br>3) 便于单元测试隔离（test_state_machine.py 独立） |
| 拒绝的替代方案 | 内嵌在 pipeline.py：pipeline.py 已含 4 阶段逻辑，再嵌入 FSM 会导致单文件 > 20 函数（违反 DD-001:4.2 单文件 ≤20 函数约束） |
| 影响范围 | `aitutor/ingest/state_machine.py` + `tests/test_state_machine.py` |
| 相关 FDR | 无 |
| 来源标注 | [DD-001:FS-M004/M009 模式] + [DD-M推断:依据=DD-001:4.2 单文件函数上限] |

---

## FDR-004 — Ingester 跨模块依赖 M-017 通过 UnitOfWork 抽象

| 字段 | 内容 |
|------|------|
| 决策编号 | FDR-004 |
| 决策标题 | Ingester 通过 `storage.UnitOfWork` 抽象调用 M-017 存储 |
| 决策状态 | 已接受 |
| 决策内容 | Ingester 接受 `uow: Optional[object] = None` 参数，由 DI 容器注入 M-017 的 UnitOfWork 实例 |
| 决策理由 | 1) 避免 M-014 直接 import M-017 导致反向依赖<br>2) UnitOfWork 模式保证 ChromaDB + SQLite 原子写入<br>3) 依赖倒置（DIP）便于测试时 Mock |
| 拒绝的替代方案 | 直接 `from aitutor.storage.unit_of_work import UnitOfWork` — 违反 Import Linter 架构边界（DD-001:CS-AITutor-V3.1 §Import Linter） |
| 影响范围 | `aitutor/ingest/ingester.py` 构造器签名 |
| 相关 FDR | 无 |
| 来源标注 | [DD-001:MD-M014 跨模块依赖 M-017] + [DD-M推断:依据=DIP 模式] |

---

## FDR-005 — exceptions.py 依赖 shared 而非本地定义

| 字段 | 内容 |
|------|------|
| 决策编号 | FDR-005 |
| 决策标题 | M-014 异常继承 `aitutor.shared.exceptions` |
| 决策状态 | 已接受 |
| 决策内容 | M-014 全部异常继承 `aitutor.shared.exceptions.BusinessError`（或 SystemError）根类 |
| 决策理由 | 1) 统一异常体系便于全局捕获（DD-001:CS-AITutor-V3.1 §5.3）<br>2) shared 层不依赖任何业务模块，避免循环（DD-001:CS-AITutor-V3.1 §Import Linter contract 5）<br>3) 框架层兜底时按 BusinessError/SystemError 分流处理 |
| 拒绝的替代方案 | 全部继承 `Exception`：丢失业务/系统分类语义 |
| 影响范围 | `aitutor/ingest/exceptions.py` 全部 6 个异常类 |
| 相关 FDR | 无 |
| 来源标注 | [DD-001:CS-AITutor-V3.1 §5.3 异常体系] |

---

## 来源标注

[DD-001:MD-M014/FS-M014/CS-AITutor-V3.1] + [DD-M推断:依据=DD-001:soul 3.7 FDR 模板]
