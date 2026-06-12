# 文件结构合规报告 — M-001 服务入口

> 模块: M-001 服务入口
> 项目: AITutor V3.1
> 日期: 2026-06-02
> 来源标注: [DD-001:FS-001] + [soul §4.7 5 项客观检查清单]

---

## 一、5 项合规检查清单

| # | 检查项 | 检查标准 | 通过情况 | 证据 |
|---|--------|---------|---------|------|
| 1 | 目录层级 | 目录层级 ≥ 2 层 | ✅ 通过 | `src/aitutor/` = 3 层（src → aitutor → 文件） |
| 2 | 文件命名 | snake_case + 模块前缀避免冲突 | ✅ 通过 | `main.py` / `config.py` / `app_factory.py` 全部 snake_case |
| 3 | 文件职责 | 每个文件职责单一明确 | ✅ 通过 | main=启动 / config=配置 / app_factory=工厂，三分离 |
| 4 | 依赖关系 | 无循环依赖 + 关系清晰 | ✅ 通过 | main → {config, app_factory}，app_factory → config，无环 |
| 5 | 最佳实践 | src layout + FastAPI 推荐 | ✅ 通过 | pyproject.toml `[tool.hatch.build.targets.wheel] packages = ["src/aitutor"]` |

**5/5 全部通过 → 合规度 = 高**

---

## 二、文件清单

### 生产文件（src/aitutor/）

| 文件路径 | 行数 | 注释覆盖 | 风格合规 | 状态 |
|---------|------|---------|---------|------|
| `src/aitutor/__init__.py` | 注释 + 占位 | 100% | ✅ | 完成 |
| `src/aitutor/main.py` | 注释 + 占位 | 100% | ✅ | 完成 |
| `src/aitutor/config.py` | 注释 + 占位 | 100% | ✅ | 完成 |
| `src/aitutor/app_factory.py` | 注释 + 占位 | 100% | ✅ | 完成 |

### 测试文件（tests/test_main/）

| 文件路径 | 测试用例数 | 注释覆盖 | 状态 |
|---------|----------|---------|------|
| `tests/test_main/test_config.py` | 13（核心5+边界5+异常3） | 100% | 完成 |
| `tests/test_main/test_app_factory.py` | 13（核心5+边界5+异常3） | 100% | 完成 |
| `tests/test_main/test_main.py` | 13（核心5+边界5+异常3） | 100% | 完成 |

---

## 三、跨模块边界检查

| 检查项 | 结果 |
|--------|------|
| 操作的文件数 | 7 个文件（4 生产 + 3 测试） |
| 是否仅 M-001 模块内 | ✅ 是 |
| 跨模块文件数 | **0** |
| 模块边界状态 | **合规** |

**D7 模块边界遵守度 = 100%**

---

## 四、命名一致性

| 文件 | snake_case | 模块前缀 | 无冲突 |
|------|------------|---------|--------|
| `__init__.py` | N/A | - | ✅ |
| `main.py` | ✅ | aitutor 包内 | ✅ |
| `config.py` | ✅ | aitutor 包内 | ✅ |
| `app_factory.py` | ✅ | aitutor 包内 | ✅ |

> **DD-M 洞察 001**：M-001 文件均在 `aitutor` 顶层包下，与其他模块（session/、cache/、rag/ 等）无路径冲突。如果未来 M-001 拆分为多个子包（如 `aitutor.launcher/`），必须重新审视文件命名。

---

## 五、依赖关系图

```
[aitutor/__init__.py]
    ↓ re-export
[aitutor/main.py] ──import──→ [aitutor/app_factory.py]
    │                                │
    │                                ↓ import
    └──import──→ [aitutor/config.py] ←┘
```

- **无循环依赖** ✅
- **延迟导入原则**：app_factory.py 在装配 5MW 时使用 `importlib.import_module` 延迟导入业务模块，避免 main 启动时拉起全部模块
- **Singleton 单向依赖**：ConfigLoader 是被依赖方，无反向依赖

---

## 六、修复建议

无需修复，5 项检查全部通过。

---

## 七、来源标注

| 内容 | 来源 |
|------|------|
| 文件清单与目录结构 | [DD-001:FS-001] |
| 5 项检查标准 | [soul §4.7] |
| 模块边界守护 | [soul §2.2 D7 + 策略16] |
| src layout 最佳实践 | [DD-001:CS-001 pyproject.toml] |
| 延迟导入原则 | [DD-M推断:依据=Import Linter Contract 1/2 + FastAPI best practice] |
