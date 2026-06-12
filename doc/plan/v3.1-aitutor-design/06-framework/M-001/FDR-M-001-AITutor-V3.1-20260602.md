# 框架决策记录（FDR）— M-001 服务入口

> 模块: M-001 服务入口
> 项目: AITutor V3.1
> 日期: 2026-06-02
> 来源标注: [DD-M推断:依据=M-001 模块特性 + FastAPI 最佳实践]

---

## FDR-M001-001 M-001 文件清单保持 3 个生产文件（不拆分）

| 项 | 内容 |
|----|------|
| **决策编号** | FDR-M001-001 |
| **决策标题** | M-001 维持 FS-001 的 3 文件清单（main.py / config.py / app_factory.py） |
| **决策状态** | 已接受 |
| **决策内容** | 不将 main.py 拆分为 cli.py + serve.py；不将 app_factory.py 拆分为 per-MW 工厂文件 |
| **决策理由** | 1. [DD-001:FS-001] 明确 3 文件清单为标准结构，模块复杂度评分中（M-001 简化为入口型） 2. M-001 仅负责启动 + 装配，业务逻辑在各模块内 3. 过度拆分会导致 3 个文件各含 30 行代码，单文件函数数远低于 20 上限，违反 R14（禁止过度拆分） |
| **拒绝的替代方案** | 方案 B：拆分为 `cli.py`（argparse）+ `serve.py`（Uvicorn 封装）+ `factory.py`（FastAPI 工厂）。拒绝理由：M-001 模块复杂度低（FS-001 标注简单入口），3 个文件总计预估 < 500 行，拆分后单文件 < 150 行，违反「最小充分原则」（策略 5） |
| **影响范围** | M-001 全部生产文件 + 测试文件 |
| **相关 FDR** | FDR-M001-002（延迟导入） |
| **来源标注** | [DD-001:FS-001] + [soul 策略 5 最小充分原则] |

---

## FDR-M001-002 5MW 装配采用延迟导入（importlib.import_module）

| 项 | 内容 |
|----|------|
| **决策编号** | FDR-M001-002 |
| **决策标题** | 5MW 装配使用 importlib 延迟导入，不在 app_factory 顶部硬导入 |
| **决策状态** | 已接受 |
| **决策内容** | app_factory.py 使用 `importlib.import_module("aitutor.session.service")` 延迟加载业务模块，而非 `from aitutor.session import service` |
| **决策理由** | 1. 避免 main 启动时拉起全部业务模块（session/cache/monitor/pipeline/rag），降低冷启动时间 2. 满足 [DD-001:CS-001] Import Linter Contract 1：api 层不直接访问 repository，service 层不反向依赖 api——M-001 作为入口应保持「零业务依赖」 3. 5MW 任一缺失时可在装配期优雅降级（E00101 依赖缺失），而非模块加载期崩溃 |
| **拒绝的替代方案** | 方案 B：硬导入（`from aitutor.session import service`）。拒绝理由：违反 Import Linter 架构边界；冷启动性能下降；单点失败扩散到模块加载期 |
| **影响范围** | app_factory.py 装配逻辑、启动期错误处理 |
| **相关 FDR** | FDR-M001-001 |
| **来源标注** | [DD-M推断:依据=Import Linter Contract 1/2 + FastAPI lifespan best practice] |

---

## FDR-M001-003 ConfigLoader 双重 Singleton 守卫

| 项 | 内容 |
|----|------|
| **决策编号** | FDR-M001-003 |
| **决策标题** | ConfigLoader 使用 `__new__` + 模块级缓存双重 Singleton 守卫 |
| **决策状态** | 已接受 |
| **决策内容** | ConfigLoader 在 `__new__` 中检查 `_instance` 缓存，同时提供类级 `_initialized` 标志防重复初始化 |
| **决策理由** | 1. [DD-001:MD-001] 明确 Singleton 模式 2. 双重守卫避免子类化或反射攻击破坏 Singleton 3. `_initialized` 标志确保 `__init__` 不被重复调用，配置不被覆盖 |
| **拒绝的替代方案** | 方案 B：使用 `functools.lru_cache` 装饰器。拒绝理由：lru_cache 不支持显式参数（config_path / env_file），无法支持多环境配置切换 方案 C：使用 metaclass SingletonMeta。拒绝理由：过度工程，标准 Singleton 模式足以 |
| **影响范围** | config.py 全部逻辑 |
| **相关 FDR** | - |
| **来源标注** | [DD-001:MD-001 Singleton 模式] + [DD-M推断:依据=Python Singleton 最佳实践] |

---

## FDR-M001-004 /health 端点拆分 liveness / readiness 两态

| 项 | 内容 |
|----|------|
| **决策编号** | FDR-M001-004 |
| **决策标题** | /health 端点拆分为 /health/liveness 与 /health/readiness |
| **决策状态** | 已接受 |
| **决策内容** | 存活探针（liveness）仅检查进程存活；就绪探针（readiness）检查 5MW 全部就绪 |
| **决策理由** | 1. 符合 K8s liveness/readiness 探针语义 2. liveness 失败时 K8s 重启 Pod；readiness 失败时仅从 Service 负载均衡中摘除——两者职责必须分离 3. [DD-001:IC-001] 后置条件「/health 返回 200」在 build_app 完成后即满足，但 5MW 全部就绪需要 lifespan startup 完成后 |
| **拒绝的替代方案** | 方案 B：单一 /health 端点返回聚合状态。拒绝理由：无法区分进程存活与业务就绪，K8s 探针语义不清晰 |
| **影响范围** | app_factory.py HealthEndpoint 类、FastAPI 路由注册 |
| **相关 FDR** | - |
| **来源标注** | [DD-001:IC-001 后置条件] + [DD-001:MD-001 HealthEndpoint 类] + [DD-M推断:依据=K8s probe best practice] |

---

## FDR-M001-005 测试文件命名采用 test_<file>.py 三分离

| 项 | 内容 |
|----|------|
| **决策编号** | FDR-M001-005 |
| **决策标题** | 测试文件按被测文件命名（test_config / test_app_factory / test_main），不合并为单 test_m001.py |
| **决策状态** | 已接受 |
| **决策内容** | tests/test_main/ 下三个测试文件分别对应 config.py / app_factory.py / main.py |
| **决策理由** | 1. 1:1 映射便于追溯（[CS-001] §6 测试命名规范） 2. 失败定位更精确（pytest 输出直接指向具体文件） 3. 并行测试时减少单文件 IO 竞争 |
| **拒绝的替代方案** | 方案 B：合并为 test_m001.py。拒绝理由：单文件函数数易超 20 上限，违反 R14（禁止过度拆分）；追溯性下降 |
| **影响范围** | tests/test_main/ 目录结构 |
| **相关 FDR** | - |
| **来源标注** | [DD-001:CS-001 §6 测试命名] + [soul §4.2 单文件函数数上限 20] |

---

## FDR-M001-006 Builder 模式 vs Factory 模式并存

| 项 | 内容 |
|----|------|
| **决策编号** | FDR-M001-006 |
| **决策标题** | M-001 同时使用 Builder 模式（AppLauncher）与 Factory 模式（build_app 函数） |
| **决策状态** | 已接受 |
| **决策内容** | 类风格 Builder（AppLauncher）+ 函数风格 Factory（build_app）并存，AppLauncher 是 build_app 的 OO 包装 |
| **决策理由** | 1. [DD-001:MD-001] 标注设计模式为「Builder + Singleton」 2. build_app 函数式入口便于测试和导入；AppLauncher 类便于链式调用和状态保持 3. 两者并非冲突，Factory 负责「构造对象」，Builder 负责「配置对象」 |
| **拒绝的替代方案** | 方案 B：仅保留 Factory 函数。拒绝理由：丢失 OO 链式 API，不符合 [DD-001:MD-001] 设计模式标注 方案 C：仅保留 Builder 类。拒绝理由：测试与导入繁琐 |
| **影响范围** | app_factory.py 类与函数设计 |
| **相关 FDR** | - |
| **来源标注** | [DD-001:MD-001 Builder + Singleton] + [DD-M推断:依据=Factory 与 Builder 协同] |

---

## FDR 状态汇总

| 决策编号 | 状态 | 决策标题 |
|---------|------|---------|
| FDR-M001-001 | 已接受 | 维持 3 文件清单 |
| FDR-M001-002 | 已接受 | 延迟导入 5MW |
| FDR-M001-003 | 已接受 | 双重 Singleton 守卫 |
| FDR-M001-004 | 已接受 | liveness/readiness 拆分 |
| FDR-M001-005 | 已接受 | 测试文件三分离 |
| FDR-M001-006 | 已接受 | Builder + Factory 并存 |

**6/6 全部已接受，无拒绝/取代决策。**
