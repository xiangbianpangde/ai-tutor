# 代码风格指南 — AITutor V3.1

> 覆盖 4 工具链（Ruff / Import Linter / Redocly / pre-commit）+ pytest，含完整自动化工具配置。
> 来源：[AR:TS-013~017] + [AR:ADR-010] + [调研报告:RI-004/REDOC-12/25/30~53] + [DD推断:依据]

---

## CS-NNN 代码风格总则

### 1. 命名规范

| 类别 | 规则 | 示例 |
|------|------|------|
| 类名 | PascalCase | `SessionRepository`, `CacheProxy` |
| 函数名 | snake_case | `create_session`, `nli_score` |
| 变量名 | snake_case | `user_id`, `trace_id` |
| 常量名 | UPPER_SNAKE_CASE | `MAX_CONNECTIONS = 1000` |
| 私有成员 | _leading_underscore | `_internal_helper` |
| 抽象基类 | Base 前缀 | `BaseRepository`, `BaseAdapter` |
| 异常类 | Error / Exception 后缀 | `CacheMissError`, `PipelineTimeoutError` |
| 类型变量 | PascalCase + Type 后缀 | `ChunkType`, `SessionType` |
| 模块名 | snake_case（≤3 词）| `state_machine`, `cache_proxy` |
| 包名 | lowercase（无下划线）| `aitutor`, `redline` |
| 测试文件 | test_ 前缀 | `test_session.py`, `test_models.py` |
| 测试函数 | test_<func>_<scenario> | `test_create_session_duplicate` |

### 2. 格式规范

- **缩进**：4 空格（PEP8）
- **行宽**：120 字符（Ruff line-length=120）
- **换行**：Unix 风格（LF）
- **尾换行**：每文件末尾保留 1 个空行
- **字符串引号**：双引号（`"`）优先
- **导入顺序**：标准库 → 第三方库 → 本地模块（isort 强制）
- **导入长度**：单行 ≤120 字符
- **括号风格**：外层括号不省略
  ```python
  # Good
  result = some_function(
      arg1,
      arg2,
      arg3,
  )
  # Bad
  result = some_function(arg1,
      arg2,
      arg3)
  ```

### 3. 注释规范

#### 3.1 文件头注释（强制）
```python
"""<模块名> - <职责一句话>

> 对应模块: M-NNN
> 关联接口: IC-NNN（可选）
> 关联选型: TS-NNN
> 来源标注: [AR:TS-NNN/API-NNN] 或 [DD推断:依据]
"""
```

#### 3.2 函数/方法注释（Google 风格）
```python
def create_session(user_id: str) -> Session:
    """创建新会话。

    Args:
        user_id: 用户 ID，32hex 字符串

    Returns:
        Session: 创建的会话对象

    Raises:
        UserNotFoundError: 用户不存在
        StorageError: 存储失败

    Note:
        该操作幂等，重复调用返回已有 session
    """
```

#### 3.3 行内注释
- 复杂逻辑必须注释（解释「为什么」而非「是什么」）
- 避免冗余（不注释显而易见的代码）
- TODO 格式：`# TODO(<author>): <description>`

#### 3.4 类型注解（强制，mypy --strict）
```python
from typing import Optional, List, Dict, Literal

def process_chunks(
    chunks: List[Chunk],
    *,
    batch_size: int = 32,
) -> Dict[str, List[Chunk]]:
    ...
```

### 4. 导入规范

#### 4.1 顺序（isort 强制）
```python
# 1. 标准库
import asyncio
import json
from pathlib import Path

# 2. 第三方库
import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

# 3. 本地模块
from aitutor.session.service import SessionService
from aitutor.shared.exceptions import CacheMissError
```

#### 4.2 禁止项
- ❌ 通配符导入（`from module import *`）
- ❌ 循环导入
- ❌ 隐式导入（不写 import 直接使用）
- ❌ `from module import long_name as another_long_name`（除 type 别名外）

### 5. 异常处理规范

#### 5.1 捕获粒度
- ✅ 捕获具体异常类，禁止裸 `except:`
- ✅ 多个异常用元组
- ❌ 不捕获 `Exception` / `BaseException`（除非顶层兜底）
```python
# Good
try:
    result = await db.fetch_one(query)
except (sqlalchemy.OperationalError, asyncio.TimeoutError) as e:
    logger.error("db_fetch_failed", error=str(e))
    raise StorageError("fetch failed") from e

# Bad
try:
    result = await db.fetch_one(query)
except:
    pass
```

#### 5.2 日志记录
- 异常必须记录（`logger.exception` / `logger.error`）
- 包含 trace_id、错误码、上下文
- 不在 except 块内静默吞掉

#### 5.3 异常转换
- 自定义异常继承 `BaseException` 根
- 业务异常 → `BusinessError`
- 系统异常 → `SystemError`
- 异常链保留 `raise ... from e`

### 6. 测试规范

- **测试范围**：单元测试（每模块）+ 集成测试（跨模块）+ E2E（关键路径）
- **测试命名**：`test_<函数名>_<场景>`
- **覆盖率要求**：≥ 80%（pytest-cov fail-under=80）
- **Mock 策略**：
  - 外部依赖用 `unittest.mock` / `pytest-mock`
  - httpx 用 `respx`
  - 数据库用内存 SQLite 或 test fixture
- **断言**：每个测试至少 1 个明确断言
- **Fixture**：共享 fixture 放 `conftest.py`
- **参数化**：多场景用 `@pytest.mark.parametrize`

### 7. 性能与并发

- 异步函数名不加 `async_` 前缀（已有 `async def` 标识）
- I/O 操作必须 `await`
- CPU 密集走 `ThreadPoolExecutor`
- 锁粒度最小化（不用全局锁）
- 不在循环内创建 asyncio Task

### 8. 安全规范

- 禁止 `eval` / `exec` 动态执行
- SQL 必须用参数化（SQLAlchemy ORM / 参数化查询）
- 用户输入必须 Pydantic 校验
- 敏感字段日志脱敏（API key / token）
- 路径操作必须白名单校验

---

## 自动化工具配置（强制）

### 1. `.ruff.toml`（Ruff 0.7.4）

```toml
# ================================
# Ruff 配置 - 替代 flake8 + isort + black
# 来源：[调研报告:REDOC-12/25/30~53]
# ================================

target-version = "py311"
line-length = 120
extend-exclude = [
    ".venv",
    "build",
    "dist",
    "*.egg-info",
]

[lint]
# 启用的规则集
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "PT",   # flake8-pytest-style
    "RET",  # flake8-return
    "ARG",  # flake8-unused-arguments
    "PTH",  # flake8-use-pathlib
    "ERA",  # eradicate (commented-out code)
    "PL",   # pylint
    "TRY",  # tryceratops
    "RUF",  # ruff-specific
]

ignore = [
    "E501",   # line-too-long (handled by formatter)
    "B008",   # function call in default argument (FastAPI Depends)
    "PLR0913", # too many arguments (allowed for adapters)
]

# 允许自动修复
fixable = ["ALL"]
unfixable = ["F401"]  # 禁止自动删除未使用导入（人工 review）

[lint.per-file-ignores]
"tests/**/*.py" = ["PLR2004", "S101"]  # 测试中允许魔术值/assert
"__init__.py" = ["F401"]  # __init__ 允许 re-export

[lint.isort]
known-first-party = ["aitutor"]
combine-as-imports = true

[lint.mccabe]
max-complexity = 10

[format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true
```

### 2. `.importlinter.toml`（Import Linter 2.1.0）

```toml
# ================================
# Import Linter 配置 - 强制架构边界
# 来源：[调研报告:RI-004]
# ================================

[importlinter:contract:1]
name = "API 层不直接访问 Repository"
type = "forbidden"
source_modules = ["aitutor.api"]
forbidden_modules = ["aitutor.session.repository", "aitutor.cache.backend", "aitutor.storage"]

[importlinter:contract:2]
name = "Service 层不反向依赖 API"
type = "forbidden"
source_modules = ["aitutor.session.service", "aitutor.cache.proxy", "aitutor.pipeline.orchestrator"]
forbidden_modules = ["aitutor.api"]

[importlinter:contract:3]
name = "Repository 不依赖 Service / API"
type = "forbidden"
source_modules = ["aitutor.session.repository", "aitutor.memory.repository", "aitutor.storage.sqlite_repo"]
forbidden_modules = ["aitutor.api", "aitutor.session.service", "aitutor.memory.service"]

[importlinter:contract:4]
name = "Models 不依赖任何业务模块"
type = "forbidden"
source_modules = ["aitutor.session.models", "aitutor.memory.models", "aitutor.feynman.models"]
forbidden_modules = [
    "aitutor.api",
    "aitutor.session.service",
    "aitutor.session.repository",
    "aitutor.cache",
    "aitutor.pipeline",
    "aitutor.rag",
    "aitutor.storage",
]

[importlinter:contract:5]
name = "Shared 不依赖任何业务模块"
type = "forbidden"
source_modules = ["aitutor.shared"]
forbidden_modules = [
    "aitutor.api",
    "aitutor.session",
    "aitutor.cache",
    "aitutor.pipeline",
    "aitutor.rag",
    "aitutor.teaching",
    "aitutor.memory",
    "aitutor.storage",
    "aitutor.redline",
]

[importlinter:contract:6]
name = "RAG 子能力命名空间隔离"
type = "independence"
modules = [
    "aitutor.rag.routing",
    "aitutor.rag.nli",
    "aitutor.rag.indexing",
    "aitutor.rag.translation",
]
```

### 3. `.redocly.yaml`（Redocly CLI 1.25.11）

```yaml
# ================================
# Redocly 配置 - OpenAPI 规范
# 来源：[调研报告:REDOC-30~53]
# ================================

apis:
  aitutor@v1:
    root: docs/api/openapi.yaml
    decorators:
      - remove-x-internal
    rules:
      operation-operationId: error
      operation-summary: error
      operation-description: warn
      operation-tag-defined: error
      no-path-trailing-slash: error
      no-ambiguous-paths: error
      tag-description: warn
      info-license: error
      info-contact: error
      info-description: error
      openapi-tags: error
      operation-4xx-problem-details-rfc7807: warn
      operation-4xx-response: warn
      operation-5xx-response: error
      spec-components-invalid-map-name: error

lint:
  extends:
    - recommended
  rules:
    no-unused-components: warn
    no-server-example.com: error
    no-server-trailing-slash: error
    no-invalid-schema-examples: warn
    no-identical-paths: error
    no-path-parameter-collision: error
    no-extra-properties: off
```

### 4. `.pre-commit-config.yaml`（pre-commit 4.0.1）

```yaml
# ================================
# pre-commit 配置 - 本地 hook
# 来源：[AR:INSIGHT-AR-002]（断网 fallback）
# ================================

default_install_hook_types: [pre-commit, commit-msg]
default_stages: [pre-commit]
default_language_version:
  python: python3.11

# 本地缓存（断网 fallback）
repo: local

repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: Ruff Lint
        entry: uv run ruff check --fix
        language: system
        types: [python]
        stages: [pre-commit]
        require_serial: false

      - id: ruff-format
        name: Ruff Format
        entry: uv run ruff format
        language: system
        types: [python]
        stages: [pre-commit]

      - id: import-linter
        name: Import Linter
        entry: uv run lint-imports
        language: system
        types: [python]
        stages: [pre-commit]
        pass_filenames: false

      - id: redocly-lint
        name: Redocly Lint
        entry: uv run redocly lint docs/api/openapi.yaml
        language: system
        files: 'docs/api/.*\.ya?ml$'
        stages: [pre-commit]

      - id: pytest-fast
        name: pytest (fast)
        entry: uv run pytest -x -q --no-cov
        language: system
        types: [python]
        stages: [pre-commit]
        pass_filenames: false

# 远端 repo（在线时使用，离线 fallback 到 local）
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.4
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
```

### 5. `pyproject.toml`（项目元数据 + pytest）

```toml
# ================================
# pyproject.toml
# 来源：[AR:BP-001] + [AR:TS-018]
# ================================

[project]
name = "aitutor"
version = "3.1.0"
description = "AITutor - 智能教学辅助系统"
readme = "README.md"
requires-python = ">=3.11,<3.13"
license = {text = "MIT"}
authors = [
    {name = "AITutor Team", email = "team@aitutor.local"},
]
dependencies = [
    "fastapi==0.115.0",
    "uvicorn[standard]==0.32.0",
    "pydantic==2.9.0",
    "pydantic-settings==2.6.1",
    "python-dotenv==1.0.1",
    "httpx==0.27.2",
    "sqlalchemy[asyncio]==2.0.36",
    "aiosqlite==0.20.0",
    "alembic==1.13.3",
    "chromadb==0.5.20",
    "redis==5.2.0",
    "py-fsrs==1.0.0",
    "pdf2zh==1.9.6",
    "structlog==24.4.0",
    "opentelemetry-api==1.28.0",
    "opentelemetry-sdk==1.28.0",
    "prometheus-client==0.21.0",
    "orjson==3.10.12",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.3",
    "pytest-cov==5.0.0",
    "pytest-asyncio==0.24.0",
    "pytest-mock==3.14.0",
    "respx==0.21.1",
    "ruff==0.7.4",
    "import-linter==2.1.0",
    "redocly-cli==1.25.11",
    "pre-commit==4.0.1",
    "mypy==1.13.0",
    "types-passlib==1.7.7.20240819",
]

[project.scripts]
aitutor = "aitutor.main:cli_main"
aitutor-web = "aitutor.clients.web:serve"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/aitutor"]

# ========== pytest 配置 ==========
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = [
    "-ra",
    "--strict-markers",
    "--strict-config",
    "--cov=aitutor",
    "--cov-report=term-missing",
    "--cov-report=xml",
    "--cov-fail-under=80",
]
asyncio_mode = "auto"
markers = [
    "unit: unit tests",
    "integration: integration tests",
    "e2e: end-to-end tests",
    "slow: slow tests",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:chromadb.*",
    "ignore::DeprecationWarning:pydantic.*",
]

# ========== mypy 配置 ==========
[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_ignores = true
warn_return_any = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["chromadb.*", "pdf2zh.*", "fsrs.*"]
ignore_missing_imports = true
```

---

## 风格指南覆盖率

| 技术栈 | 工具 | 配置 | 状态 |
|--------|------|------|------|
| Python 代码 | Ruff 0.7.4 | `.ruff.toml` | ✅ |
| 架构边界 | Import Linter 2.1.0 | `.importlinter.toml` | ✅ |
| OpenAPI | Redocly CLI 1.25.11 | `.redocly.yaml` | ✅ |
| Git Hooks | pre-commit 4.0.1 | `.pre-commit-config.yaml` | ✅ |
| 测试 | pytest 8.3.3 + pytest-cov 5.0.0 | `pyproject.toml [tool.pytest.*]` | ✅ |
| 类型检查 | mypy 1.13.0 | `pyproject.toml [tool.mypy]` | ✅ |

**覆盖率：6/6 = 100%**（含 4 工具链 + 测试 + 类型检查）

来源标注：[AR:TS-013~017] + [AR:ADR-010] + [调研报告:REDOC-12/25/30~53] + [DD推断:依据=Python 生态最佳实践]
