"""aitutor - AITutor 智能教学辅助系统主包.

> 对应模块: M-001 服务入口
> 关联接口: IC-001（服务启动）
> 关联选型: TS-001 Python / TS-002 FastAPI / TS-018 pydantic-settings
> 来源标注: [DD-001:FS-001/MD-001/IC-001/CS-001] + [DD-M推断:依据=src layout 最佳实践]

[文件职责]
    主包 `__init__`：聚合 M-001 公开符号（ConfigLoader / AppLauncher / build_app /
    start_uvicorn / validate_mw），使外部可通过 `from aitutor import ...` 直接调用。

[所属模块]
    M-001（来自 DD-001 模块分配）

[关联设计规范]
    FS-001（文件结构规范）/ MD-001（模块细化方案）/ IC-001（接口契约）

[功能描述]
    功能1: re-export M-001 公开类与函数，统一入口
    功能2: 暴露 `__version__` 供运行时探针使用
    功能3: 提供 `__all__` 白名单，约束 `from aitutor import *` 输出

[输入输出]
    输入: 无（纯聚合文件）
    输出: 包级符号（ConfigLoader / AppLauncher / build_app / ...）

[依赖关系]
    依赖文件: .main / .app_factory / .config
    被依赖文件: 所有外部入口（CLI / Web / 库调用方）

[注意事项]
    注意1: 此文件不包含任何运行时初始化逻辑，遵循"零副作用"原则
    注意2: re-export 必须保持与子模块同义，避免循环导入
    注意3: `__all__` 必须显式声明，遵循 Ruff 规则 F401 与 isort 约束

[代码风格]
    遵循 CS-001（Google docstring + 4 空格缩进 + type hint 强制）

[创建日期]
    2026-06-02

[修改历史]
    2026-06-02: DD-M-001 - 初始创建（依据 DD-001 FS-001/MD-001）

[作者]
    DD-M-001-20260602

[来源标注]
    [DD-001:FS-001/MD-001] + [DD-M推断:依据=Python src layout 最佳实践]
"""

# 注意：本文件遵循 CS-001 §3.1 文件头注释强制规范
# 实际业务代码由 DD-S（结构设计师）/ Dev（开发工程师）补全，本框架仅含注释与符号声明占位

from __future__ import annotations

# 标准库
# (无)

# 第三方库
# (无)

# 本地模块 - 来自 M-001 三个子文件
# [DD-001:FS-001] 明确 main.py / config.py / app_factory.py 为 M-001 文件清单
# re-export 占位 - 实际符号在子模块中实现后由 DD-S 接线
from aitutor.app_factory import (  # noqa: F401  # [DD-001:FS-001]
    AppLauncher,  # [DD-001:MD-001] 类 AppLauncher
    build_app,  # [DD-001:MD-001] 函数 build_app(config: ConfigLoader) -> FastAPI
    start_uvicorn,  # [DD-001:MD-001] 函数 start_uvicorn(app, host, port)
    validate_mw,  # [DD-001:MD-001] 函数 validate_mw(app) -> MiddlewareStatus
)
from aitutor.config import (  # noqa: F401  # [DD-001:FS-001]
    ConfigLoader,  # [DD-001:MD-001] 类 ConfigLoader
)
from aitutor.main import (  # noqa: F401  # [DD-001:FS-001]
    cli_main,  # [DD-001:MD-001] CLI 入口（pyproject.toml [project.scripts] aitutor = "aitutor.main:cli_main"）
)

# 版本与元数据
__version__: str = "3.1.0"  # [DD-001:CS-001] pyproject.toml project.version
__author__: str = "AITutor Team"  # [DD-001:CS-001] pyproject.toml authors

# 公开符号白名单（isort + Ruff F401 合规）
__all__: list[str] = [
    "AppLauncher",  # Builder 模式入口
    "ConfigLoader",  # Singleton 配置加载器
    "build_app",  # FastAPI 工厂函数
    "cli_main",  # CLI 入口
    "start_uvicorn",  # Uvicorn 启动封装
    "validate_mw",  # 中间件注册校验
    "__version__",
    "__author__",
]


# ================================
# 类注释占位（DD-S 落地时实现）
# ================================

# [类名] AppLauncher
# [职责] Builder 模式：链式装配 5MW + Uvicorn 启动
# [关联设计规范] MD-001
# [属性]
#   属性1: app FastAPI 构造中的 FastAPI 实例
#   属性2: mw_status Dict[str, bool] 5MW 装配状态（Session/Cache/Monitor/Pipeline/RAG）
# [方法列表]
#   方法1: build_app(config: ConfigLoader) -> FastAPI - 构造 FastAPI 实例
#   方法2: validate_mw() -> MiddlewareStatus - 校验 5MW 注册
#   方法3: start_uvicorn(host: str = "127.0.0.1", port: int = 8000) -> None - 启动 Uvicorn
# [状态机] N/A（无状态服务入口，[DD-001:MD-001] 明确）
# [异常处理]
#   异常1: DependencyMissingError(E00101) - 5MW 任一未注册
#   异常2: PortInUseError(E00102) - 端口被占用
#   异常3: SchemaIncompatibleError(E00103) - 旧库 schema 不匹配
#   异常4: MiddlewareInitError(E00106) - MW 装配过程异常
# [来源标注] [DD-001:MD-001]

# [类名] ConfigLoader
# [职责] Singleton 模式：加载 pyproject.toml + .env
# [关联设计规范] MD-001
# [属性]
#   属性1: pyproject Dict 解析后的 pyproject.toml 内容
#   属性2: env Dict 解析后的 .env 环境变量
# [方法列表]
#   方法1: load_pyproject() -> Dict - 加载 pyproject.toml
#   方法2: load_env() -> Dict - 加载 .env
#   方法3: validate_required() -> None - 校验必填项
# [状态机] N/A
# [异常处理]
#   异常1: FileNotFoundError - pyproject.toml/.env 缺失
#   异常2: ValidationError - 配置项校验失败
# [来源标注] [DD-001:MD-001]
