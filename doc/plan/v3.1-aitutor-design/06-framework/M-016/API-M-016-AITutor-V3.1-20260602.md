# 接口注释清单 — M-016 红线编排

> **模块编号**：M-016
> **关联接口契约**：IC-006（红线检测 API-006 / IF-006）
> **关联模块细化方案**：MD-016
> **关联技术选型**：TS-013 Ruff / TS-014 Import Linter / TS-015 Redocly / TS-016 pre-commit / TS-017 pytest
> **关联错误码**：E01601 / E01602 / E01603 / E01604
> **来源标注**：[DD-001:IC-006/MD-016] + [DD-M推断:依据=Chain+Observer 模式分解]

---

## API-016-001 run_redlines（主入口 → IC-006）

| 项 | 内容 |
|----|------|
| **接口编号** | API-016-001 |
| **接口名称** | run_redlines（红线检测主入口）|
| **关联契约** | IC-006（红线检测 API-006 / IF-006）|
| **关联函数签名** | `run_redlines(tool_set: List[str]) -> RedlineResult`（来自 MD-016）|
| **实现文件** | `redline/orchestrator.py` → `RedlineOrchestrator.run_all()` / `run_specific()` |
| **接口描述** | CI 进程 / pre-commit hook 调用入口，按 tool_set 串行/并行执行 4 工具 + pytest，聚合违规事件，返回统一退出码与修复手册链接 |
| **入参** | `tool_set: List[Literal["ruff", "import_linter", "redocly", "pre_commit", "pytest"]]` 必填 默认全量 5 工具 |
| **出参** | `RedlineResult`：exit_code / violation_count / raw_output / fix_url / duration_ms |
| **错误码** | E01601（退出码非 0）、E01604（工具链版本破坏）|
| **幂等键** | `commit_sha + tool_set`（来自 IC-006）|
| **并发** | 4 工具并行子进程（来自 IC-006 时序）|
| **性能** | 5 工具并行 ≤5min（来自 IC-006）|

**函数签名注释**（仅注释，代码由 DD-S 编写）：
```python
def run_redlines(
    tool_set: List[str],  # 工具集；默认全量 ["ruff", "import_linter", "redocly", "pre_commit", "pytest"]
    *,
    changed_files: Optional[List[str]] = None,  # 增量模式：变更文件列表
    fail_fast: bool = False,  # 任一失败即停止
) -> RedlineResult:
    """
    执行红线检测（Chain 模式主入口）。

    [职责] ≤ 30字：按工具集执行 4 工具 + pytest 门禁，聚合违规与退出码
    [关联接口契约] IC-006
    [关联设计规范] MD-016 / TS-013~017

    Args:
        tool_set: 工具集子集，如 ["ruff", "pytest"]；None/空则全量
        changed_files: 增量模式下的变更文件列表；None 则全量扫描
        fail_fast: True 时首个失败工具后立即停止

    Returns:
        RedlineResult: 包含 exit_code/violation_count/raw_output/fix_url/duration_ms

    Raises:
        RedlineVersionError(E01604): 工具链版本破坏

    Note:
        - 4 工具并行子进程执行
        - 失败事件通过 ErrorHub (Observer) 聚合
        - 修复手册 URL 来自 docs/redline/<tool>.md
    """
```

---

## API-016-002 run_ruff（Ruff 子工具 → IC-006）

| 项 | 内容 |
|----|------|
| **接口编号** | API-016-002 |
| **接口名称** | run_ruff |
| **关联契约** | IC-006（tool_set 元素 ruff）|
| **关联函数签名** | `run_ruff() -> ToolResult`（来自 MD-016）|
| **实现文件** | `redline/tools/ruff.py` → `RuffRunner.run()` |
| **接口描述** | 调用 `uv run ruff check --fix`（来自 CS pre-commit），解析 JSON 输出，统计违规数 |
| **入参** | 无（配置由 .ruff.toml 决定）|
| **出参** | `ToolResult`：tool="ruff" / exit_code / violation_count / raw_output / duration_ms |
| **错误码** | E01601（exit_code ≠ 0）|
| **CLI 调用** | `uv run ruff check --output-format=json` |
| **并发** | 子进程调用，subprocess.run |
| **性能** | 单次 ≤30s |

**函数签名注释**：
```python
def run_ruff(
    *,
    changed_files: Optional[List[str]] = None,  # 增量文件列表
) -> ToolResult:
    """
    执行 Ruff 静态检查。

    [职责] ≤ 30字：调 Ruff CLI 解析违规数与退出码
    [关联接口契约] IC-006
    [关联技术选型] TS-013 Ruff 0.7.4

    Args:
        changed_files: 增量模式下的 Python 文件路径列表

    Returns:
        ToolResult: 含 ruff 工具的退出码、违规数、原始 JSON 输出

    Note:
        - 配置：.ruff.toml（行宽 120、规则 E/W/F/I/N/UP/B 等）
        - 输出：JSON 格式，解析 violation_count = sum(每个文件的诊断数)
    """
```

---

## API-016-003 run_import_linter（Import Linter 子工具 → IC-006）

| 项 | 内容 |
|----|------|
| **接口编号** | API-016-003 |
| **接口名称** | run_import_linter |
| **关联契约** | IC-006（tool_set 元素 import_linter）|
| **关联函数签名** | `run_import_linter() -> ToolResult`（来自 MD-016）|
| **实现文件** | `redline/tools/import_linter.py` → `ImportLinterRunner.run()` |
| **接口描述** | 调用 `uv run lint-imports` 校验 6 条架构边界合约，解析违规路径 |
| **入参** | 无（配置由 .importlinter.toml 决定）|
| **出参** | `ToolResult`：tool="import_linter" / exit_code / violation_count / raw_output |
| **错误码** | E01602（合约违反，来自 MD-016）|
| **CLI 调用** | `uv run lint-imports` |
| **配置** | .importlinter.toml（6 contracts：API/Service/Repository/Models/Shared/RAG 命名空间）|
| **性能** | 单次 ≤60s |

**函数签名注释**：
```python
def run_import_linter() -> ToolResult:
    """
    执行 Import Linter 架构边界校验。

    [职责] ≤ 30字：调 lint-imports 校验 6 条合约并解析违规路径
    [关联接口契约] IC-006
    [关联技术选型] TS-014 Import Linter 2.1.0

    Returns:
        ToolResult: 含 import_linter 工具的退出码、违规数（合约违反数）、原始输出

    Raises:
        ConfigNotFoundError: .importlinter.toml 不存在

    Note:
        - 6 条合约：API→Repo 禁止、Service→API 禁止、Repo→Service 禁止、
                   Models→业务模块禁止、Shared→业务模块禁止、RAG 子能力隔离
        - 违规解析：从 raw_output 提取 violating_module 与 forbidden_module
    """
```

---

## API-016-004 run_redocly（Redocly 子工具 → IC-006）

| 项 | 内容 |
|----|------|
| **接口编号** | API-016-004 |
| **接口名称** | run_redocly |
| **关联契约** | IC-006（tool_set 元素 redocly）|
| **关联函数签名** | `run_redocly() -> ToolResult`（来自 MD-016）|
| **实现文件** | `redline/tools/redocly.py` → `RedoclyRunner.run()` |
| **接口描述** | 调用 `redocly lint docs/api/openapi.yaml` 校验 OpenAPI 规范，解析违规数 |
| **入参** | 无（配置由 .redocly.yaml 决定）|
| **出参** | `ToolResult`：tool="redocly" / exit_code / violation_count / raw_output |
| **错误码** | E01601（exit_code ≠ 0）|
| **CLI 调用** | `uv run redocly lint docs/api/openapi.yaml` |
| **配置** | .redocly.yaml（apis.aitutor@v1 + lint rules）|
| **性能** | 单次 ≤30s |

**函数签名注释**：
```python
def run_redocly(
    *,
    spec_path: str = "docs/api/openapi.yaml",  # OpenAPI 规范文件路径
) -> ToolResult:
    """
    执行 Redocly OpenAPI 规范校验。

    [职责] ≤ 30字：调 redocly lint 校验 OpenAPI 规范并解析违规
    [关联接口契约] IC-006
    [关联技术选型] TS-015 Redocly CLI 1.25.11

    Args:
        spec_path: OpenAPI 规范文件路径；默认 docs/api/openapi.yaml

    Returns:
        ToolResult: 含 redocly 工具的退出码、违规数、原始输出

    Note:
        - 规则：operation-operationId/summary/error、no-path-trailing-slash 等
        - 违规解析：JSON 输出含 rule/severity/message/location
    """
```

---

## API-016-005 run_pytest（pytest 子工具 → IC-006）

| 项 | 内容 |
|----|------|
| **接口编号** | API-016-005 |
| **接口名称** | run_pytest |
| **关联契约** | IC-006（tool_set 元素 pytest）|
| **关联函数签名** | `run_pytest() -> ToolResult`（来自 MD-016）|
| **实现文件** | `redline/tools/pytest_runner.py` → `PytestRunner.run()` |
| **接口描述** | 调用 `pytest --cov=aitutor --cov-fail-under=80` 校验测试用例与覆盖率门禁 |
| **入参** | 无（配置由 pyproject.toml [tool.pytest.*] 决定）|
| **出参** | `ToolResult`：tool="pytest" / exit_code / violation_count / raw_output |
| **错误码** | E01601（用例失败）、E01603（覆盖率<80%，来自 MD-016）|
| **CLI 调用** | `uv run pytest --cov=aitutor --cov-fail-under=80 --cov-report=json` |
| **配置** | pyproject.toml [tool.pytest.ini_options]：cov-fail-under=80 |
| **性能** | 单次 ≤5min（含 5 模块测试）|

**函数签名注释**：
```python
def run_pytest(
    *,
    target: str = "tests/",  # 测试目录或文件
    fail_under: int = 80,    # 覆盖率门禁百分比
) -> ToolResult:
    """
    执行 pytest 测试与覆盖率门禁。

    [职责] ≤ 30字：调 pytest 校验用例通过与覆盖率 ≥80%
    [关联接口契约] IC-006
    [关联技术选型] TS-017 pytest 8.3.3 + pytest-cov 5.0.0

    Args:
        target: 测试目录或文件；默认 tests/
        fail_under: 覆盖率门禁（百分比），低于则 exit_code=1

    Returns:
        ToolResult: 含 pytest 工具的退出码、违规数（失败用例数+覆盖率不达标）、覆盖率百分比

    Note:
        - violation_count = 失败用例数 + (覆盖率 < fail_under ? 1 : 0)
        - 报告路径：coverage.json
    """
```

---

## API-016-006 run_precommit（pre-commit 子工具 → IC-016 补充）

| 项 | 内容 |
|----|------|
| **接口编号** | API-016-006 |
| **接口名称** | run_precommit |
| **关联契约** | IC-006（tool_set 元素 pre_commit）|
| **关联函数签名** | MD-016 sm016-precommit 声明，本框架补充 |
| **实现文件** | `redline/tools/precommit.py` → `PrecommitRunner.run()` |
| **接口描述** | 调用 `pre-commit run --all-files` 执行本地 hooks（含 ruff/import-linter/redocly-lint/pytest-fast）|
| **入参** | 无（配置由 .pre-commit-config.yaml 决定）|
| **出参** | `ToolResult`：tool="pre_commit" / exit_code / violation_count / raw_output |
| **错误码** | E01601（hook 失败）、E01604（hook 版本破坏）|
| **CLI 调用** | `uv run pre-commit run --all-files` |
| **配置** | .pre-commit-config.yaml（5 hooks：ruff-check/ruff-format/import-linter/redocly-lint/pytest-fast）|
| **性能** | 单次 ≤3min |

**函数签名注释**：
```python
def run_precommit(
    *,
    hook_ids: Optional[List[str]] = None,  # 指定 hook 子集；None 则全量
    all_files: bool = True,                  # 是否扫描所有文件
) -> ToolResult:
    """
    执行 pre-commit hooks。

    [职责] ≤ 30字：调 pre-commit run 执行本地 hooks 并解析违规
    [关联接口契约] IC-006
    [关联技术选型] TS-016 pre-commit 4.0.1

    Args:
        hook_ids: 执行的 hook ID 列表；None 则全量（ruff-check/ruff-format/
                 import-linter/redocly-lint/pytest-fast）
        all_files: True 时扫描所有文件；False 时仅暂存区

    Returns:
        ToolResult: 含 pre_commit 工具的退出码、违规数、原始输出

    Note:
        - pre-commit run 输出含 [hook id] 段落，解析 PASS/FAIL
        - 离线 fallback：.pre-commit-config.yaml 配 repo: local
    """
```

---

## API-016-007 aggregate_reports（错误聚合 → IC-006）

| 项 | 内容 |
|----|------|
| **接口编号** | API-016-007 |
| **接口名称** | aggregate_reports |
| **关联契约** | IC-006（聚合出参 fix_url、violation_count）|
| **关联函数签名** | `aggregate_reports() -> RedlineReport`（来自 MD-016）|
| **实现文件** | `redline/error_hub.py` → `ErrorHub.aggregate()` + `redline/reports.py` → `RedlineReport.render()` |
| **接口描述** | 订阅各工具的 ToolResult 事件（Observer 模式），聚合成 RedlineReport，构造修复手册 URL |
| **入参** | 隐式：ErrorHub.reports 列表（被各 Runner 通过 `notify(tool_result)` 注入）|
| **出参** | `RedlineReport`：total_violation_count / exit_code / per_tool_results / fix_url |
| **错误码** | 无（聚合阶段）|
| **观察者接口** | `RedlineObserver.handle(event: RedlineEvent)` |
| **事件类型** | `tool_started` / `tool_finished` / `tool_failed` |

**函数签名注释**：
```python
def aggregate_reports(
    self,  # ErrorHub 实例
) -> RedlineReport:
    """
    聚合所有工具的 ToolResult 为 RedlineReport。

    [职责] ≤ 30字：收集订阅事件汇总违规数与修复手册 URL
    [关联接口契约] IC-006
    [关联设计模式] Observer（订阅各工具事件）

    Returns:
        RedlineReport: 包含 total_violation_count / exit_code / per_tool_results / fix_url

    Note:
        - exit_code = max(tool.exit_code for tool in reports) 任一失败即非 0
        - total_violation_count = sum(tool.violation_count for tool in reports)
        - fix_url = "https://docs.aitutor.local/redline/{tool_name}.md"（首个失败工具）
    """
```

---

## 接口-工具映射汇总

| IC-006 元素 | MD-016 函数 | 本框架 API 编号 | 实现类 | 实现文件 |
|------------|-----------|--------------|--------|---------|
| `tool_set=[ruff]` | `run_ruff()` | API-016-002 | `RuffRunner` | `redline/tools/ruff.py` |
| `tool_set=[import_linter]` | `run_import_linter()` | API-016-003 | `ImportLinterRunner` | `redline/tools/import_linter.py` |
| `tool_set=[redocly]` | `run_redocly()` | API-016-004 | `RedoclyRunner` | `redline/tools/redocly.py` |
| `tool_set=[pytest]` | `run_pytest()` | API-016-005 | `PytestRunner` | `redline/tools/pytest_runner.py` |
| `tool_set=[pre_commit]` | （MD sm016-precommit）| API-016-006 | `PrecommitRunner` | `redline/tools/precommit.py` |
| （主入口）| `run_redlines(tool_set)` | API-016-001 | `RedlineOrchestrator` | `redline/orchestrator.py` |
| `fix_url` / `violation_count` 聚合 | `aggregate_reports()` | API-016-007 | `ErrorHub` + `RedlineReport` | `redline/error_hub.py` + `redline/reports.py` |

---

## 错误码映射

| 错误码 | 含义 | 触发位置 | 处理方式 | 来源 |
|--------|------|---------|---------|------|
| E01601 | 退出码非 0 | 任一 Runner.run() 返回非 0 | CI 红 + 修复手册 URL | [DD-001:IC-006] |
| E01602 | 合约违反 | ImportLinterRunner 解析出合约违反 | 显示违规路径 | [DD-001:IC-006/MD-016] |
| E01603 | 覆盖率 < 80% | PytestRunner 解析 cov < 80% | CI 阻断 | [DD-001:IC-006/MD-016] |
| E01604 | 工具链版本破坏 | 任一 Runner 启动异常 | 锁版本恢复 | [DD-001:IC-006/MD-016] |

---

## 接口契约验收

| 验收项 | 状态 |
|--------|------|
| 入参完整 | ✅（tool_set / changed_files / fail_fast 全部覆盖）|
| 出参完整 | ✅（exit_code / violation_count / raw_output / fix_url / duration_ms 全部覆盖）|
| 错误码覆盖 | ✅（E01601~E01604 全部映射）|
| 时序明确 | ✅（4 工具并行 → 聚合 → 退出）|
| 前置后置 | ✅（工具链锁版本 / DE-046 写入）|
| 幂等性 | ✅（commit_sha + tool_set）|
| 性能约束 | ✅（≤5min 总耗时）|

**8/8 全部通过 4.12 验收标准**

来源标注：[DD-001:IC-006/MD-016] + [DD-M推断:依据=Chain 模式映射 5 Runner + Observer 映射 ErrorHub]
