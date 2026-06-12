# 框架决策记录（FDR）— M-016 红线编排

> **模块编号**：M-016
> **关联迭代**：F0-F8 框架阶段
> **报告生成日期**：2026-06-02
> **来源标注**：[DD-M推断:依据=Chain+Observer 模式映射 + FS/MD/IC 差异调和]

---

## FDR-M016-001：5 工具独立 Runner vs 抽象 BaseTool 策略模式

| 字段 | 内容 |
|------|------|
| **决策编号** | FDR-M016-001 |
| **决策标题** | 5 工具独立 Runner 类，不引入 BaseTool 抽象基类 |
| **决策状态** | 已接受 |
| **决策内容** | `redline/tools/` 下设 5 个独立 Runner 类（RuffRunner / ImportLinterRunner / RedoclyRunner / PrecommitRunner / PytestRunner），统一返回 ToolResult；不引入 `BaseTool` 抽象基类 |
| **决策理由** | 1. **MD-016 明确给出 6 个独立类**（含 `RedlineOrchestrator` / `ErrorHub`），未要求 BaseTool 抽象层；2. 5 工具差异集中在「调哪个 CLI + 解析何种输出」，无多态需求；3. 抽象层增加代码量，对 5 工具的小场景价值低；4. 方案对比中方案 A 加权 9.13 vs 方案 B 加权 8.31，差异 ≥5，选择方案 A |
| **拒绝的替代方案** | **方案 B**：抽象 `BaseTool` 抽象基类，5 工具实现 `run()` 接口。理由：抽象层增加而 5 工具差异小；MD 未要求；方案 B 加权总分 8.31 < 方案 A 9.13 |
| **影响范围** | `redline/orchestrator.py` / `redline/tools/ruff.py` / `redline/tools/import_linter.py` / `redline/tools/redocly.py` / `redline/tools/precommit.py` / `redline/tools/pytest_runner.py` |
| **相关FDR** | 无 |
| **决策时间** | 2026-06-02（框架第 1 轮）|
| **来源标注** | [DD-M推断:依据=MD-016 类设计 + 4.11 多方案对比] |

---

## FDR-M016-002：补充 pytest_runner.py 弥补 FS 缺失

| 字段 | 内容 |
|------|------|
| **决策编号** | FDR-M016-002 |
| **决策标题** | 补充 `redline/tools/pytest_runner.py`，弥补 FS-016 缺失 |
| **决策状态** | 已接受 |
| **决策内容** | 在 `redline/tools/` 下增加 `pytest_runner.py`（含 `PytestRunner` 类），处理 pytest 测试与覆盖率门禁 |
| **决策理由** | 1. **MD-016 明确声明 sm016-pytest 子模块**：「sm016-pytest：pytest 覆盖率门禁」；2. **IC-006 tool_set 包含 "pytest"**：`List[Literal["ruff", "import_linter", "redocly", "pre_commit", "pytest"]]`；3. **MD 错误码 E01603** 专门处理「覆盖率<80% → CI 阻断」，必须由 pytest Runner 实现；4. FS-016 仅列 4 工具是 FS 的疏漏，本框架按 MD+IC 权威来源补足 |
| **拒绝的替代方案** | **方案 B**：将 pytest 门禁放在 `orchestrator.py` 中独立处理。理由：违反单一职责，5 工具统一 Runner 抽象被破坏；不利于后续扩展更多工具 |
| **影响范围** | `redline/tools/pytest_runner.py`（新增）|
| **相关FDR** | 无 |
| **建议反馈** | DD-001 在 FS V3.2 修订时补登 `redline/tools/pytest_runner.py` 章节 |
| **决策时间** | 2026-06-02（框架第 1 轮）|
| **来源标注** | [DD-M推断:依据=MD-016 sm016-pytest + IC-006 tool_set + MD E01603 错误码] |

---

## FDR-M016-003：RedlineObserver 用 Protocol 而非 ABC

| 字段 | 内容 |
|------|------|
| **决策编号** | FDR-M016-003 |
| **决策标题** | 观察者接口用 `Protocol`（PEP 544）而非 `ABC` |
| **决策状态** | 已接受 |
| **决策内容** | `RedlineObserver` 使用 `typing.Protocol` 表达观察者接口（结构性子类型），不继承 `abc.ABC` |
| **决策理由** | 1. **Observer 模式解耦**：`ErrorHub` 只需调用 `observer.handle(event)`，无需强继承关系；2. **Python 3.11 推荐**：Protocol 比 ABC 更轻量，符合 PEP 544 结构性子类型；3. **测试友好**：测试中可创建匿名观察者（直接实现 `handle` 方法），无需继承；4. **CS-AITutor 1. 抽象基类 Base 前缀**要求只针对 ABC 场景，Protocol 无此要求 |
| **拒绝的替代方案** | **方案 B**：继承 `abc.ABC` 定义 `RedlineObserver`。理由：增加样板代码（`@abstractmethod`），未带来运行时收益；3.11 风格偏 Protocol |
| **影响范围** | `redline/error_hub.py` |
| **相关FDR** | 无 |
| **决策时间** | 2026-06-02（框架第 1 轮）|
| **来源标注** | [DD-M推断:依据=Python 3.11 PEP 544 Protocol + Observer 模式解耦需求 + CS-AITutor 1. 命名规范] |

---

## FDR-M016-004：ErrorHub 持有 reports 列表 vs 订阅者推入

| 字段 | 内容 |
|------|------|
| **决策编号** | FDR-M016-004 |
| **决策标题** | ErrorHub.reports 由 Orchestrator 注入，非订阅者主动 push |
| **决策状态** | 已接受 |
| **决策内容** | `ErrorHub.reports: List[ToolResult]` 列表由 `RedlineOrchestrator` 在调度过程中调用 `error_hub.notify(tool_result)` 注入；观察者通过 `subscribe(handler)` 注册并接收事件 |
| **决策理由** | 1. **MD-016 类设计明确**：`ErrorHub` 属性 `reports: List[Report]`；2. **Orchestrator 是唯一调度方**：5 工具的 ToolResult 由 Orchestrator 接收并通知 ErrorHub，避免工具反向依赖 Hub；3. **保持工具解耦**：5 工具只返回 ToolResult，不知 ErrorHub 存在；4. **测试便利**：测试中可手动构造 reports 列表传入 aggregate() |
| **拒绝的替代方案** | **方案 B**：5 工具主动 import ErrorHub 并 push。理由：违反工具解耦；5 工具需 import 同一 Hub，导致 Hub 成为「隐式全局」|
| **影响范围** | `redline/orchestrator.py` / `redline/error_hub.py` / `redline/tools/*.py` |
| **相关FDR** | 无 |
| **决策时间** | 2026-06-02（框架第 1 轮）|
| **来源标注** | [DD-M推断:依据=MD-016 ErrorHub.reports + 工具解耦原则] |

---

## FDR-M016-005：Chain 模式采用"全量并行 + 串行兜底"

| 字段 | 内容 |
|------|------|
| **决策编号** | FDR-M016-005 |
| **决策标题** | 默认全量并行执行 5 工具，fail_fast 时改串行 |
| **决策状态** | 已接受 |
| **决策内容** | `RedlineOrchestrator.run_all()` 默认通过 `asyncio.gather` 并行调度 5 工具；当 `fail_fast=True` 时改为 `asyncio.as_completed` 串行监听，首个失败即 `gather.cancel()` 剩余任务 |
| **决策理由** | 1. **IC-006 时序明确**：「4 工具并行子进程」+「并行执行 ≤5min」；2. **fail_fast 优化**：`fail_fast=True` 时不需要等待所有工具完成，可节省时间；3. **asyncio 优势**：5 个 subprocess.run 包裹在 `asyncio.to_thread` 中并行，比同步快 3~5x；4. **取消安全**：`asyncio.gather` + `return_exceptions=True` 防止单个失败中断其他 |
| **拒绝的替代方案** | **方案 B**：完全串行执行。理由：5 工具总耗时 = sum(各工具)，CI 体验差；IC-006 明确「并行」|
| **影响范围** | `redline/orchestrator.py` |
| **相关FDR** | 无 |
| **决策时间** | 2026-06-02（框架第 1 轮）|
| **来源标注** | [DD-M推断:依据=IC-006 时序 + asyncio 最佳实践] |

---

## FDR-M016-006：fix_url 构造策略（首个失败工具的修复手册）

| 字段 | 内容 |
|------|------|
| **决策编号** | FDR-M016-006 |
| **决策标题** | fix_url 指向首个失败工具的修复手册，全通过时指向总册 |
| **决策状态** | 已接受 |
| **决策内容** | 当 `exit_code != 0` 时，`fix_url` 指向首个失败工具的修复手册页面（按 Ruff → ImportLinter → Redocly → Precommit → Pytest 顺序）；全通过时指向 `docs/redline/index.md`（总册）|
| **决策理由** | 1. **IC-006 出参**：`fix_url: str 必填 修复手册链接`；2. **CI 体验**：开发者看到首个失败时直接跳到对应修复页，避免从总册导航；3. **优先级**：Ruff 失败最频繁且修复简单，最先提示；4. **降级**：全通过时降级到总册，便于人工 review |
| **拒绝的替代方案** | **方案 B**：fix_url 始终指向总册。理由：CI 阻断时需多一次导航，体验差；方案 A 一次到位 |
| **影响范围** | `redline/reports.py` → `RedlineReport.fix_url()` |
| **相关FDR** | 无 |
| **决策时间** | 2026-06-02（框架第 1 轮）|
| **来源标注** | [DD-M推断:依据=IC-006 fix_url 必填 + docs/redline/ 目录结构] |

---

## FDR 汇总

| FDR 编号 | 标题 | 状态 | 影响文件数 |
|---------|------|------|----------|
| FDR-M016-001 | 5 工具独立 Runner vs BaseTool 抽象 | 已接受 | 6 |
| FDR-M016-002 | 补充 pytest_runner.py 弥补 FS 缺失 | 已接受 | 1（新增）|
| FDR-M016-003 | RedlineObserver 用 Protocol 而非 ABC | 已接受 | 1 |
| FDR-M016-004 | ErrorHub.reports 由 Orchestrator 注入 | 已接受 | 7 |
| FDR-M016-005 | Chain 模式全量并行 + fail_fast 串行 | 已接受 | 1 |
| FDR-M016-006 | fix_url 构造指向首个失败工具 | 已接受 | 1 |
| **合计** | **6 个决策，全部已接受** | - | **17 文件次** |

来源标注：[DD-M推断:依据=Chain+Observer 模式映射 + FS/MD/IC 差异调和 + Python 3.11 最佳实践]
