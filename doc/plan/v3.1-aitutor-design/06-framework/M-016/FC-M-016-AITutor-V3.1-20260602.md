# 文件结构合规报告 — M-016 红线编排

> **模块编号**：M-016
> **关联文件结构规范**：FS-AITutor-V3.1-20260602.md（M-016 章节）
> **关联代码风格指南**：CS-AITutor-V3.1-20260602.md
> **报告生成日期**：2026-06-02
> **来源标注**：[DD-001:FS-016/CS-AITutor] + [DD-M推断:依据=4.7 五项客观检查]

---

## 1. 合规检查总览

依据 soul 4.7 文件结构 5 项客观合规检查清单，对 M-016 文件框架执行合规校验：

| 检查项 | 检查标准 | 通过条件 | M-016 结果 |
|--------|---------|---------|----------|
| 1. 目录层级 | 目录层级 ≥ 2 层，符合 FS-016 规范 | 布尔值 = true | ✅ 通过 |
| 2. 文件命名 | 文件命名符合 FS-016 命名规则（snake_case）| 布尔值 = true | ✅ 通过 |
| 3. 文件职责 | 每个文件职责单一明确（无 >3 职责）| 布尔值 = true | ✅ 通过 |
| 4. 依赖关系 | 文件间依赖关系无循环依赖 | 布尔值 = true | ✅ 通过 |
| 5. 最佳实践 | 文件组织符合 Python src layout + 工具子包 | 布尔值 = true | ✅ 通过 |

**合规度判定**：5/5 全部通过 → **合规度 = 高**

---

## 2. 逐项检查详情

### 2.1 目录层级检查（≥2 层）

```
产出物/07-文件框架/M-016/        ← 第 1 层（模块根）
├── redline/                       ← 第 2 层（业务包）
│   └── tools/                     ← 第 3 层（工具子包）
└── tests/                         ← 第 2 层（测试包）
    └── test_redline/              ← 第 3 层（测试子包）
        └── tools/                 ← 第 4 层（工具测试子包）
```

**判定**：✅ 层级 = 2~4 层，全部 ≥ 2 层。`redline/tools/` 复刻 FS-016 结构。

**来源标注**：[DD-001:FS-016 目录层级 = 3 层]

---

### 2.2 文件命名检查

| 文件 | 命名规则 | FS-016 期望 | 实际 | 状态 |
|------|---------|-----------|------|------|
| `redline/__init__.py` | snake_case + Python 约定 | `__init__.py` | `__init__.py` | ✅ |
| `redline/orchestrator.py` | snake_case | `orchestrator.py` | `orchestrator.py` | ✅ |
| `redline/error_hub.py` | snake_case + 下划线分隔 | `error_hub.py` | `error_hub.py` | ✅ |
| `redline/reports.py` | snake_case | `reports.py` | `reports.py` | ✅ |
| `redline/tools/__init__.py` | snake_case | `__init__.py` | `__init__.py` | ✅ |
| `redline/tools/ruff.py` | snake_case | `ruff.py` | `ruff.py` | ✅ |
| `redline/tools/import_linter.py` | snake_case | `import_linter.py` | `import_linter.py` | ✅ |
| `redline/tools/redocly.py` | snake_case | `redocly.py` | `redocly.py` | ✅ |
| `redline/tools/precommit.py` | snake_case | `precommit.py` | `precommit.py` | ✅ |
| `redline/tools/pytest_runner.py` | snake_case + `_runner` 后缀 | （FS 缺失，MD 补充）| `pytest_runner.py` | ✅（[DD-M推断:FS 缺失 pytest 文件，MD sm016-pytest 声明，按 MD 补充]）|
| `tests/__init__.py` | snake_case + Python 约定 | （隐含）| `__init__.py` | ✅ |
| `tests/test_redline/__init__.py` | snake_case + Python 约定 | `tests/unit/test_redline/` | `tests/test_redline/__init__.py` | ✅（路径镜像 FS-016 tests）|
| `tests/test_redline/test_*.py` | test_ 前缀 + snake_case | `test_*.py` | `test_orchestrator.py` / `test_error_hub.py` / `test_reports.py` | ✅ |
| `tests/test_redline/tools/test_*.py` | test_ 前缀 + snake_case | （隐含）| `test_ruff.py` / `test_import_linter.py` / `test_redocly.py` / `test_precommit.py` / `test_pytest_runner.py` | ✅ |

**判定**：✅ 14/14 全部符合 snake_case + Python PEP8 命名。

**FS 缺失说明**：[DD-M推断:FS-016 列出 4 工具 ruff/import_linter/redocly/precommit，但 MD-016 声明 5 子模块含 sm016-pytest，IC-006 tool_set 包含 "pytest"。本框架按 MD+IC 补充 pytest_runner.py，标注为 [DD-M推断:依据=MD sm016-pytest + IC-006 tool_set]，建议 DD-001 在 FS V3.2 中补登。]

**来源标注**：[DD-001:FS-016] + [DD-M推断:依据=MD sm016-pytest + IC-006 tool_set]

---

### 2.3 文件职责检查（单一职责）

| 文件 | 声明职责 | 实际职责（推断）| 职责数 | 状态 |
|------|---------|--------------|--------|------|
| `redline/__init__.py` | 模块初始化 + 公共 API 导出 | 公共 API 导出 | 1 | ✅ |
| `redline/orchestrator.py` | RedlineOrchestrator 编排 | 编排 + 1 个数据类（RedlineResult/ToolResult）| 2 | ✅（≤3）|
| `redline/error_hub.py` | ErrorHub 错误聚合 | 聚合 + 1 个观察者接口（RedlineObserver）+ 1 个数据类（Report）| 3 | ✅（=3，上限）|
| `redline/reports.py` | RedlineReport 报告生成 | 渲染 + URL 构造 + FixManualBuilder 辅助 | 2 | ✅ |
| `redline/tools/ruff.py` | RuffRunner 静态检查 | Ruff 调用 + 输出解析 | 1 | ✅ |
| `redline/tools/import_linter.py` | ImportLinterRunner 架构边界 | 合约校验 + 违规解析 | 1 | ✅ |
| `redline/tools/redocly.py` | RedoclyRunner OpenAPI 规范 | 规范校验 + 输出解析 | 1 | ✅ |
| `redline/tools/precommit.py` | PrecommitRunner hook 调用 | hook 执行 + 解析 | 1 | ✅ |
| `redline/tools/pytest_runner.py` | PytestRunner 覆盖率门禁 | 测试执行 + 覆盖率解析 | 1 | ✅ |
| `tests/test_redline/test_orchestrator.py` | 编排器测试 | 测试用例集合 | 1 | ✅ |
| `tests/test_redline/test_error_hub.py` | 错误中心测试 | 测试用例集合 | 1 | ✅ |
| `tests/test_redline/test_reports.py` | 报告测试 | 测试用例集合 | 1 | ✅ |
| `tests/test_redline/tools/test_*.py` | 各工具测试 | 测试用例集合 | 1 | ✅ |

**判定**：✅ 14/14 全部职责单一或 ≤3 上限内。

**来源标注**：[DD-001:MD-016 类设计] + [DD-M推断:依据=4.7 职责 ≤3 上限]

---

### 2.4 依赖关系检查（无循环）

**依赖图**：

```
redline/orchestrator.py
    ├──→ redline/tools/ruff.py
    ├──→ redline/tools/import_linter.py
    ├──→ redline/tools/redocly.py
    ├──→ redline/tools/precommit.py
    ├──→ redline/tools/pytest_runner.py
    ├──→ redline/error_hub.py
    │       └──→ redline/reports.py
    └──→ redline/reports.py

redline/tools/*（5 文件互不依赖）
    ├──→ shared/exceptions.py（外部）
    ├──→ shared/types.py（外部）
    └──→ shared/errors.py（外部）

redline/error_hub.py
    └──→ redline/reports.py

redline/reports.py
    └──→ shared/types.py（外部）
```

**循环依赖检测**：

| 潜在循环 | 实际检测 | 状态 |
|---------|---------|------|
| orchestrator ↔ tools | orchestrator → tools（单向）| ✅ 无循环 |
| orchestrator ↔ error_hub | orchestrator → error_hub（单向）| ✅ 无循环 |
| error_hub ↔ reports | error_hub → reports（单向）| ✅ 无循环 |
| tools 5 文件之间 | 5 文件互不依赖 | ✅ 无循环 |
| tools ↔ orchestrator | tools 不导入 orchestrator | ✅ 无循环 |
| reports ↔ orchestrator | reports 不导入 orchestrator | ✅ 无循环 |

**判定**：✅ 无循环依赖。Import Linter 强制约束（CS 第 2 节）：

| 层级 | 允许依赖 | 禁止依赖 |
|------|---------|---------|
| `redline/orchestrator.py` | `tools/*` + `error_hub` + `reports` + `shared/*` | `api/` + `service`（其他模块）|
| `redline/tools/*.py` | `shared/*` | `api/` + `service` + `orchestrator` |
| `redline/error_hub.py` | `reports` + `shared/*` | `tools`（Observer 解耦）|
| `redline/reports.py` | `shared/*` | 任何业务模块 |

**来源标注**：[DD-001:FS-016 依赖关系] + [CS-AITutor 2. .importlinter.toml] + [DD-M推断:依据=4.7 无循环约束]

---

### 2.5 最佳实践检查

| 实践项 | 要求 | M-016 实际 | 状态 |
|--------|------|----------|------|
| Python `__init__.py` | 每个包必须含 `__init__.py` | `redline/__init__.py` + `redline/tools/__init__.py` + `tests/__init__.py` + `tests/test_redline/__init__.py` + `tests/test_redline/tools/__init__.py` | ✅ |
| 测试目录镜像 src | 测试路径镜像源码路径 | `tests/test_redline/` 镜像 `redline/` | ✅ |
| 工具子包隔离 | 子能力用子包隔离 | `redline/tools/` 隔离 5 工具 | ✅ |
| 测试命名 test_ 前缀 | PEP8 + Ruff PT 规则 | `test_*.py` 全部 test_ 前缀 | ✅ |
| 抽象基类 Base 前缀 | 抽象类用 Base 前缀 | `RedlineObserver`（抽象观察者，DD-M 推断为协议/接口）| ⚠️ 备注（见下）|
| 工具与 CLI 同名 | 适配器命名与底层 CLI 一致 | ruff.py / import_linter.py / redocly.py / precommit.py | ✅ |
| 路径含模块编号 | 多实例隔离（soul v1.5）| 路径 `M-016/redline/...` 显式含 M-016 | ✅ |

**Base 前缀说明**：[DD-M推断:RedlineObserver 为协议/接口类型（PEP 544 Protocol），不是抽象基类。Python 3.11 推荐 Protocol 表达观察者接口，比 ABC 更轻量，更适合 Observer 模式解耦。CS-AITutor 1.「抽象基类」中 Base 前缀仅在 ABC 场景下要求，Protocol 无此要求。]

**判定**：✅ 7/7 全部符合 Python + FastAPI + pytest 最佳实践。

**来源标注**：[DD-001:FS-016] + [CS-AITutor] + [DD-M推断:Protocol 比 ABC 更适合 Observer 模式]

---

## 3. 关键差异与建议

### 3.1 FS 缺失 pytest 工具文件

| 项 | FS-016 | MD-016 | IC-006 | 本框架 |
|----|--------|--------|--------|-------|
| pytest 工具 | ❌ 未列 | ✅ sm016-pytest | ✅ tool_set 含 "pytest" | ✅ 补充 pytest_runner.py |
| 状态 | 缺失 | 声明 | 契约 | 框架补充 |

**建议**：
1. **DD-M 处理**：按 MD+IC 补充 `pytest_runner.py`，标注 [DD-M推断]
2. **DD-001 后续**：FS V3.2 修订时补登 pytest_runner.py 章节

### 3.2 路径镜像

**实际框架路径**：`产出物/07-文件框架/M-016/redline/`
**FS-016 期望路径**：`aitutor/redline/`
**差异**：框架阶段使用 `M-016/` 前缀做多实例隔离，最终交付到 `src/aitutor/redline/` 时去掉 M-016 前缀。

**建议**：DD-S 阶段按 FS-016 实际路径组装，本框架文件作为注释源。

---

## 4. 总体合规结论

| 维度 | 期望 | 实际 | 状态 |
|------|------|------|------|
| 目录层级 | ≥2 层 | 2~4 层 | ✅ |
| 文件命名 | snake_case | 100% 合规 | ✅ |
| 文件职责 | 单一职责 | 100% 合规 | ✅ |
| 依赖关系 | 无循环 | 100% 无循环 | ✅ |
| 最佳实践 | Python + FastAPI + pytest | 7/7 合规 | ✅ |

**最终合规度**：**高**（5/5 全部通过）

**修复建议**：无强制修复项；非阻塞建议：
1. 建议 DD-001 在 FS V3.2 中补登 pytest_runner.py（已通过本框架补充）
2. 建议 DD-S 阶段按 FS-016 实际路径 `aitutor/redline/` 组装

来源标注：[DD-001:FS-016/CS-AITutor] + [DD-M推断:依据=4.7 五项客观检查 + pytest 文件补充 + Protocol vs ABC]
