# 代码风格指南 — AITutor V2.0

> 角色：DD-001 | 日期：2026-06-01 | 覆盖技术栈：Python 3.11 / FastAPI / Pydantic v2 / Vue 3/React + TypeScript

---

## CS-001 Python 3.11+ 风格指南

### 命名规范
- **类名**：PascalCase（`HaluGateOrchestrator`）
- **函数/方法名**：snake_case（`schedule_card`）
- **变量名**：snake_case（`user_id`）
- **常量名**：UPPER_SNAKE_CASE（`MAX_TOTAL_ROUNDS = 5`）
- **私有成员**：前缀单下划线（`_internal_state`）
- **模块名**：snake_case 全小写（`halugate_orchestrator.py`）
- **包名**：全小写（`aitutor`）

### 格式规范
- **缩进**：4 空格（禁用 Tab）
- **行宽**：120 字符
- **换行**：LF（Unix）
- **引号**：双引号 `"string"` 优先；含双引号时用单引号 `'has "double" quotes'`
- **导入顺序**（自动由 ruff isort 强制）：标准库 → 第三方 → 本地（`from aitutor.xxx`）
- **空行**：类内方法间 1 空行；模块级函数间 2 空行

### 注释规范
- **文件头注释**：
  ```python
  """模块名 - 简短描述
  
  详细职责说明（1-3 行）
  
  关联 AR 规范：[AR:TS-NNN/API-NNN/SEC-NNN] 或 [DD推断:依据]
  """
  ```
- **类注释**：必须含职责说明
  ```python
  class HaluGateOrchestrator:
      """三级级联抗幻觉裁决器
      
      责任链：NLI → SLM → LLM；任一级通过则终止
      """
  ```
- **函数注释**（PEP 257 + 类型注解）：
  ```python
  def verify(claims: list[Claim], response_text: str) -> HaluReport:
      """验证声明列表的事实性
      
      Args:
          claims: 待验证的声明列表
          response_text: 原始回答文本
          
      Returns:
          HaluReport: 评分报告
          
      Raises:
          AllJudgesFailedError: 三级全部失败
      """
  ```
- **行内注释**：使用 `#` 后 1 空格

### 导入规范
- ✅ 允许：`from __future__ import annotations`（PEP 563）
- ✅ 允许：`from typing import ...` 显式导入
- ❌ 禁止：通配符导入 `from x import *`
- ❌ 禁止：循环导入（用 Protocol 隔离或延迟导入）
- ❌ 禁止：隐式重新导出（用 `__all__` 显式）

### 异常处理规范
- ✅ 捕获粒度：尽量精确（小异常类优先）
- ✅ 日志记录：捕获后必须记录（structlog logger.exception）
- ✅ 异常转换：底层异常 → 业务异常（如 `aiosqlite.IntegrityError` → `DuplicateUserError`）
- ❌ 禁止：`except Exception: pass`（裸吞）
- ❌ 禁止：`raise Exception("...")`（用具体异常类）

### 测试规范
- **测试文件命名**：`test_<module>_<scenario>.py`（如 `test_fsrs_again_storm.py`）
- **测试函数命名**：`test_<func>_<scenario>_<expected>`（如 `test_schedule_card_grade1_returns_5min_retry`）
- **覆盖率要求**：行 ≥ 80%，分支 ≥ 75%（CI 强制）
- **Mock 规范**：`unittest.mock.patch` 显式作用域
- **断言**：使用 `pytest.raises` / `assert` 配合明确消息

### 工具配置
- **.ruff.toml**：
  ```toml
  line-length = 120
  target-version = "py311"
  
  [lint]
  select = ["E", "F", "W", "I", "N", "UP", "B", "C4", "SIM", "RUF"]
  ignore = ["E501"]  # 已被 line-length 控制
  
  [format]
  quote-style = "double"
  indent-style = "space"
  line-ending = "lf"
  ```
- **.import-linter.ini**：
  ```ini
  [importlinter:contract:1]
  type = layers
  layers = 
      aitutor.bootstrap
      aitutor.middleware
      aitutor.modules
      aitutor.integrations
  
  [importlinter:contract:2]
  type = forbidden
  source_modules = aitutor.modules
  forbidden_modules = aitutor.bootstrap
  ```
- **.pre-commit-config.yaml**：
  ```yaml
  repos:
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.6.9
      hooks:
        - id: ruff
        - id: ruff-format
    - repo: https://github.com/PyCQA/import-linter
      rev: v2.0
      hooks:
        - id: import-linter
  ```

### 来源标注
[AR:TS-001/TS-022] + [调研报告:RI-004] + [SA:BR-038]（uv 锁定 + ruff 强制）

---

## CS-002 FastAPI 0.115 风格指南

### Router 组织
- **每模块一个 Router**：`router = APIRouter(prefix="/v1/<module>", tags=["<module>"])`
- **依赖注入**：使用 `Depends()` 注入服务（如 `Depends(get_session_service)`）
- **统一响应模型**：`response_model=BaseResp[DataT]`
- **统一错误处理**：注册 `app.exception_handler(BusinessError)(handler)`

### Endpoint 命名
- 资源用复数名词（`/v1/sessions`）
- 动作用 POST（`/v1/sessions/{id}/switch`）
- 查询用 GET
- 幂等操作用 PUT/PATCH

### 类型注解
- **路径参数**：`session_id: str`（FastAPI 自动校验 UUID）
- **查询参数**：`limit: int = Query(20, ge=1, le=100)`
- **请求体**：`payload: FeynmanRequest = Body(...)`
- **响应**：`response_model=FeynmanResponse`

### 中间件
- **顺序固定**（AR §三）：`Session → Cache → Monitor → Pipeline → RAG`
- 注册顺序在 `app.py` 中显式列出 + 注释

### 文档
- 每个 endpoint 必须有 docstring（OpenAPI 自动生成）
- 错误码必须在 docstring 中枚举

### 工具配置
- **OpenAPI lint**：`.redocly.yaml` 强制 OAS 3.1 + naming 规范

### 来源标注
[AR:TS-002/TS-004] + [AR:BR-008] + [调研报告:RI-007]

---

## CS-003 Pydantic v2 风格指南

### 模型定义
- **BaseModel 优先**：所有数据类继承 `BaseModel`
- **BaseSettings 用于配置**：`Settings(BaseSettings)` 加载 .env
- **ConfigDict**：
  ```python
  class FeynmanRequest(BaseModel):
      model_config = ConfigDict(
          extra="forbid",        # 禁止未知字段
          str_strip_whitespace=True,
          validate_assignment=True,
      )
      
      user_answer: str = Field(..., min_length=1, max_length=10000)
      question_id: UUID
      user_id: str = Field(..., pattern=r"^u[0-9a-f]{8}$")
  ```

### 字段约束
- 字符串：`min_length` / `max_length` / `pattern`
- 数值：`ge` / `le` / `multiple_of`
- 列表：`min_length` / `max_length`
- 时间：`AwareDatetime`（强制带时区）

### 序列化
- `model_dump()` 替代 `dict()`
- `model_dump_json()` 替代 `json()`
- `model_copy(update={...})` 替代 `copy()`

### 验证器
- 优先使用 `Field` 约束
- 复杂校验用 `@field_validator` / `@model_validator(mode="after")`
- 自定义错误用 `PydanticCustomError`

### 来源标注
[AR:TS-004] + [调研报告:RI-007]

---

## CS-004 Vue 3 + TypeScript 风格指南（前端）

### 命名规范
- **组件文件**：PascalCase（`StatusBar.vue`）
- **组合式函数**：camelUseXxx（`useWebSocket.ts`）
- **变量/函数**：camelCase
- **常量**：UPPER_SNAKE_CASE
- **类型/接口**：PascalCase 前缀 I（`IApiResponse`）

### 格式规范
- **缩进**：2 空格
- **行宽**：100 字符
- **引号**：单引号 `'string'`
- **分号**：必须
- **换行**：LF

### 组件风格
- 优先 `<script setup lang="ts">` + Composition API
- Props 用 `defineProps<{}>()` 类型化
- Emits 用 `defineEmits<{}>()`
- 模板中表达式简洁，复杂逻辑抽到 computed

### 状态管理（Pinia）
- Store 文件：`stores/<domain>.ts`
- Composition API 风格：`defineStore('xxx', () => { ... })`
- 状态/计算/动作分明

### API 客户端
- 集中在 `src/api/` 用 axios + 拦截器
- 类型定义与后端 Pydantic 模型对齐
- 错误处理统一拦截

### 工具配置
- **.prettierrc**：
  ```json
  {
    "semi": true,
    "singleQuote": true,
    "tabWidth": 2,
    "printWidth": 100,
    "endOfLine": "lf"
  }
  ```
- **eslint.config.js**：typescript-eslint + vue plugin

### 来源标注
[AR:TS-002 前端] + [DD推断:基于 Vite + Vue 3 最佳实践]
