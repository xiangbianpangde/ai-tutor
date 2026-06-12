# 文件框架结构 — M-001 服务入口

> 模块: M-001 服务入口（Builder + Singleton）
> 项目: AITutor V3.1
> 日期: 2026-06-02
> 来源标注: [DD-001:FS-001/MD-001/IC-001/CS-001]

---

## 一、模块文件框架

```
src/
└── aitutor/                       # 主包根（src layout）
    ├── __init__.py                ← [包初始化，导出公共入口符号]
    ├── main.py                    ← [M-001 启动入口: Uvicorn 装配 + CLI 入口]
    ├── config.py                  ← [M-001 配置加载: pydantic-settings + .env]
    └── app_factory.py             ← [M-001 FastAPI 工厂: 装配 5MW + 路由注册]
```

## 二、文件职责矩阵

| 文件路径 | 职责 | 依赖 | 行数预估 |
|---------|------|------|---------|
| `src/aitutor/__init__.py` | 包初始化，导出 `AppLauncher` / `ConfigLoader` / `build_app` 等公共符号 | main.py / app_factory.py / config.py | <30 |
| `src/aitutor/main.py` | Uvicorn 启动 + CLI 命令行入口（`aitutor` script 入口） | config.py / app_factory.py | <120 |
| `src/aitutor/config.py` | pydantic-settings 加载 `pyproject.toml` + `.env`，提供类型化配置 | (无内部依赖) | <150 |
| `src/aitutor/app_factory.py` | FastAPI 应用工厂（`build_app`），按 MD-001 装配 5MW（Session/Cache/Monitor/Pipeline/RAG） | config.py / shared/ | <250 |

## 三、文件间依赖关系

```
__init__.py  ←  re-export 来自 main / app_factory / config
   ↑
   ├── main.py  →  config.py  →  app_factory.py
   │                  ↓
   │            app_factory.py  →  config.py
   │                              ↓
   │                         (注: 5MW 装配通过延迟导入 + 注册表，遵循 M-006 事件总线)
   └── [外部调用: uvicorn / aitutor CLI / 单元测试]
```

**依赖约束（遵循 CS-001 .importlinter.toml）**:
- `main.py` → `app_factory.py` / `config.py`：允许
- `app_factory.py` → `config.py`：允许
- `app_factory.py` → `api/` 等其他模块：通过延迟导入 / 注册表，**不产生硬依赖**（避免 main 启动时拉起全部业务模块）
- 无循环依赖 ✓
- `main.py` 不依赖业务模块（api/、session/、cache/ 等），保证入口解耦

## 四、模块设计要点

| 设计模式 | 体现位置 | 来源 |
|---------|---------|------|
| Builder 模式 | `AppLauncher.build_app()` 链式装配 5MW | [DD-001:MD-001] |
| Singleton 模式 | `ConfigLoader` / `AppLauncher` 进程内单例（`__new__` 守卫 + 模块级缓存） | [DD-001:MD-001] |
| Factory 模式 | `build_app(config)` 函数式工厂返回 `FastAPI` 实例 | [DD-M推断:依据=FS-001 文件结构标注 app_factory] |
| Dependency Injection | FastAPI `Depends` + `lifespan` context | [DD-001:CS-001 FastAPI 最佳实践] |

## 五、与其他模块的交互边界

> **重要：M-001 是入口模块，**仅在装配阶段**引用其他模块的工厂/注册函数，运行时不反向依赖**。

| 交互模块 | 装配方式 | 文件位置 |
|---------|---------|---------|
| M-006 monitor | `EventBus` 初始化 → 注入到 FastAPI app.state | `app_factory.py` |
| M-002 api | `APIRouterRegistry.register_router()` 延迟装载 | `app_factory.py` |
| M-017 storage | `init_storage(config)` 在 lifespan startup 调用 | `app_factory.py` |
| M-016 redline | 通过 CLI 子命令 `aitutor redline` 触发 | `main.py` |

## 六、测试文件结构

```
tests/
├── __init__.py
├── conftest.py                          ← [共享 fixture: 临时 .env / 内存配置]
└── unit/
    └── test_api/                        ← (M-002 范围，不属 M-001)
    └── test_main/
        ├── __init__.py
        ├── test_config.py               ← [ConfigLoader 单测]
        ├── test_app_factory.py          ← [build_app + 5MW 装配单测]
        └── test_main.py                 ← [start_uvicorn + CLI 单测]
```

> M-001 单元测试预计 13 用例（核心 5 + 边界 5 + 异常 3），覆盖率 ≥85%。

## 七、文件结构合规检查（5 项）

| 检查项 | 检查标准 | 通过 | 说明 |
|--------|---------|-----|------|
| 目录层级 | ≥ 2 层 | ✓ | `src/aitutor/` = 3 层 |
| 文件命名 | snake_case | ✓ | `main.py` / `config.py` / `app_factory.py` 全部符合 |
| 文件职责 | 每文件单一职责 | ✓ | main=启动 / config=配置 / app_factory=工厂 |
| 依赖关系 | 无循环依赖 | ✓ | main → {config, app_factory}，app_factory → config |
| 最佳实践 | src layout + FastAPI 推荐 | ✓ | pyproject.toml `[tool.hatch.build.targets.wheel] packages = ["src/aitutor"]` |

**合规度判定：5/5 通过 = 高**

## 八、阶梯退出检查（L0/L1）

- [x] ① 分配模块 M-001 已分类到框架主题（接口入口型）
- [x] ② FS-001 文件结构已识别
- [x] ③ D1（设计规范转化完整度）= 100%（FS/MD/IC/CS 全部覆盖）
- [x] ④ 全部目录已规划：`src/aitutor/`
- [x] ⑤ 全部文件已规划：3 个生产文件 + 1 个 `__init__.py`
- [x] ⑥ 命名合规：snake_case
- [x] ⑦ D2（文件结构合规度）= 100%

## 九、来源标注

| 内容 | 来源 |
|------|------|
| 文件清单 `main.py` / `config.py` / `app_factory.py` | [DD-001:FS-001] |
| 4 个类（`AppLauncher`/`ConfigLoader`/`MiddlewareValidator`/`HealthEndpoint`） | [DD-001:MD-001] |
| 5 个公开函数签名 | [DD-001:MD-001] |
| 错误码 E00101/E00102/E00103/E00106 | [DD-001:IC-001] |
| 启动期 validate 健康检查 + /health 端点 | [DD-001:IC-001] |
| Google 风格 docstring + 4 空格缩进 + 类型注解强制 | [DD-001:CS-001] |
| 延迟导入 + 注册表避免 main 拉起全部模块 | [DD-M推断:依据=Import Linter Contract 1/2 + FastAPI best practice] |
| __init__.py re-export 模式 | [DD-M推断:依据=Python src layout 最佳实践] |
