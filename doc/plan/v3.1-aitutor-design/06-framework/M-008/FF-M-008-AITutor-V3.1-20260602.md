# 文件框架结构 — M-008 RAG 引擎（AITutor V3.1）

> 角色：DD-M-008 详细设计师（模块）
> 负责模块：M-008 RAG 引擎
> 上游：DDI = 0.96（DD-001 详细设计师总方案）
> 设计模式：Strategy + Template + Adapter
> 来源标注：[DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-001:IC-003]

---

## 〇、DD-001 方案接收门禁（4.10 强制）

| 校验项 | 校验规则 | 结果 | 依据 |
|--------|---------|------|------|
| 方案完整性 | 9 类产出物全在 | 通过 | DD/MD/IC/DS/FS/CS/EX/DDR/DH 全在 |
| 方案收敛度 | DDI ≥ 0.85 | 通过 | DDI = 0.96 |
| 模块覆盖 | M-008 有 FS | 通过 | FS-M-008 含 5 项检查 |
| 接口契约 | IC-003 完整 | 通过 | 入参/出参/错误码/时序/幂等/性能约束 全有 |
| 代码风格 | 有 CS 指南 | 通过 | CS-NNN（Ruff + Google Docstring + mypy） |
| 澄清请求 | ≤ 3 | 通过 | 0 条 |

**接收门禁：通过 → 进入框架构建**

---

## 一、文件框架结构

```
产出物/07-文件框架/M-008/
├── src/
│   └── aitutor/
│       └── rag/
│           ├── __init__.py           ← 模块初始化，导出 RAGEngine
│           ├── engine.py             ← RAGEngine 入口（编排 4 子能力）
│           ├── routing/
│           │   ├── __init__.py       ← 路由子能力命名空间
│           │   ├── keyword.py        ← KeywordRouter（默认策略）
│           │   └── adapter.py        ← RoutingAdapter + KeywordRoutingAdapter
│           ├── nli/
│           │   ├── __init__.py       ← NLI 子能力命名空间
│           │   ├── model.py          ← NLIModelLoader（DeBERTa-v3-large-mnli）
│           │   └── scorer.py         ← NLIScorer（含 LLM 法官降级）
│           ├── indexing/
│           │   ├── __init__.py       ← 索引子能力命名空间
│           │   ├── chroma.py         ← ChromaCollection（原生操作）
│           │   └── adapter.py        ← IndexAdapter + ChromaIndexAdapter
│           └── translation/
│               ├── __init__.py       ← 翻译子能力命名空间
│               └── adapter.py        ← TranslationAdapter + PDFTranslationAdapter
└── tests/
    └── unit/
        └── test_rag/
            ├── __init__.py           ← 测试包
            ├── test_engine.py        ← RAGEngine 测试
            ├── test_routing.py       ← 路由子能力测试
            ├── test_nli.py           ← NLI 子能力测试
            ├── test_indexing.py      ← 索引子能力测试
            └── test_translation.py   ← 翻译子能力测试
```

**目录层级**：3 层（rag/ → sub_ability/ → file.py）
**文件命名**：snake_case 全局一致
**文件职责**：每个文件单一职责
**依赖关系**：engine.py → 4 子能力适配器 → 原生封装
**最佳实践**：src layout + 子能力命名空间隔离（DD 洞察 001）

---

## 二、文件职责矩阵

| 文件路径 | 职责 | 依赖文件 | 被依赖文件 |
|---------|------|---------|-----------|
| `rag/__init__.py` | 模块初始化、模块边界标识 | 无 | 无 |
| `rag/engine.py` | RAGEngine 编排入口 | routing/adapter, nli/scorer, indexing/adapter, translation/adapter | pipeline/stages/retrieve.py (M-007) |
| `rag/routing/keyword.py` | 关键字路由策略 | shared/types | rag/routing/adapter |
| `rag/routing/adapter.py` | 路由策略抽象 | rag/routing/keyword | rag/engine |
| `rag/nli/model.py` | NLI 模型加载 + CPU 亲和性 | shared/exceptions | rag/nli/scorer |
| `rag/nli/scorer.py` | NLI 评分 + LLM 法官降级 | rag/nli/model, shared/exceptions | rag/engine |
| `rag/indexing/chroma.py` | ChromaDB 原生操作 | shared/types | rag/indexing/adapter |
| `rag/indexing/adapter.py` | 索引策略抽象 | rag/indexing/chroma, shared/types | rag/engine, ingest/ingester.py (M-014) |
| `rag/translation/adapter.py` | 翻译抽象（跨模块 M-014 委派） | shared/exceptions | rag/engine |
| `tests/unit/test_rag/*` | 各子能力单元测试 | 对应被测文件 | 无 |

---

## 三、文件间依赖关系

```
pipeline/stages/retrieve.py (M-007)
    ↓
RAGEngine (engine.py)
    ↓
    ├── RoutingAdapter (routing/adapter.py)
    │       ↓
    │   KeywordRouter (routing/keyword.py)
    │
    ├── NLIScorer (nli/scorer.py)
    │       ↓
    │   NLIModelLoader (nli/model.py)
    │
    ├── IndexAdapter (indexing/adapter.py)
    │       ↓
    │   ChromaCollection (indexing/chroma.py)
    │
    └── TranslationAdapter (translation/adapter.py)
            ↓ (跨模块)
        M-014 翻译管线客户端
```

**依赖约束**（Import Linter 强制）：
- `rag.engine` 不直接依赖 `rag.indexing.chroma`（必须经 adapter）
- `rag.nli.scorer` 不直接依赖 `transformers` 库（必须经 model.py 封装）
- `rag.translation.adapter` 不直接 import M-014 内部模块（仅依赖注入）

**循环依赖检查**：无循环依赖 ✅

---

## 四、文件命名合规报告（4.7 五项检查）

| 检查项 | 检查标准 | 通过情况 | 证据 |
|--------|---------|---------|------|
| 目录层级 | ≥ 2 层 | ✅ | rag/ → sub_ability/ → file.py（3 层）|
| 文件命名 | snake_case | ✅ | engine.py, keyword.py, adapter.py 等 |
| 文件职责 | 单一职责 | ✅ | 每个文件一个明确职责 |
| 依赖关系 | 无循环 | ✅ | engine → 4 adapter → 原生封装 |
| 最佳实践 | Python src layout | ✅ | src/aitutor/rag/ + 子能力命名空间 |

**合规度 = 高（5/5 通过）**

---

## 五、文件来源标注

| 文件 | 来源 |
|------|------|
| `rag/__init__.py` | [DD-001:FS-M-008] |
| `rag/engine.py` | [DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-001:IC-003] |
| `rag/routing/keyword.py` | [DD-001:MD-M-008 KeywordRouter] + [DD-001:IC-003 route_decision] |
| `rag/routing/adapter.py` | [DD-001:FS-M-008] + [DD推断:依据=Template Method 抽象] |
| `rag/nli/model.py` | [DD-001:MD-M-008] + [AR:INSIGHT-AR-001 CPU 亲和性] |
| `rag/nli/scorer.py` | [DD-001:MD-M-008 NLIScorer] + [DD-001:IC-003 E00802] |
| `rag/indexing/chroma.py` | [DD-001:MD-M-008 ChromaIndexAdapter 拆解] + [DD推断:依据=封装粒度] |
| `rag/indexing/adapter.py` | [DD-001:MD-M-008 ChromaIndexAdapter] + [DD推断:依据=Adapter 抽象] |
| `rag/translation/adapter.py` | [DD-001:MD-M-008 TranslationAdapter] + [DD-001:IC-004 E01401] |
| `tests/unit/test_rag/*` | [DD-001:FS-M-008] + [DD推断:依据=pytest 测试规范] |

---

## 六、DD-M 洞察注入

### [DD-M洞察-M008-001] 子能力命名空间隔离缓解内聚度过低
- **类型**：模块边界 + 设计模式
- **描述**：M-008 内聚度 3/6（MD-M-008 最低），通过 `routing/` / `nli/` / `indexing/` / `translation/` 4 子能力目录隔离副作用
- **风险**：未来模块膨胀触发 100 用户时需物理拆分
- **缓解**：Import Litter contract 6（.importlinter.toml）独立声明 4 子能力
- **来源**：[DD-001:DD洞察-001] + [DD-001:FS-M-008 特殊说明]

### [DD-M洞察-M008-002] 跨模块调用 M-014 必须经适配器
- **类型**：模块边界 + R28/R29 红线
- **描述**：M-008 翻译子能力需调用 M-014 PDF 翻译链
- **风险**：直接 import M-014 内部模块触发 R28 跨模块操作
- **缓解**：TranslationAdapter 仅持有 M-014 客户端对象（依赖注入），不直接 import
- **来源**：[DD-001:MD-M-008 TranslationAdapter] + [soul R28/R29]

### [DD-M洞察-M008-003] ChromaIndexAdapter 拆分为 chroma + adapter 双层
- **类型**：文件职责单一性 + OCP
- **描述**：MD-M-008 定义的 ChromaIndexAdapter 同时承担原生操作 + 适配器职责（违反 4.7 单一职责）
- **缓解**：本框架拆分为 `chroma.py`（原生封装）+ `adapter.py`（抽象基类 + ChromaIndexAdapter）
- **影响**：未来新增 Qdrant / Milvus 索引后端时不影响 engine.py
- **来源**：[DD-M推断:依据=4.7 文件职责单一性 + OCP 原则]

### [DD-M洞察-M008-004] NLI 评分结果需写入 M-005 缓存
- **类型**：跨模块集成 + 性能优化
- **描述**：IC-003 后置条件规定 NLI 评分写入缓存（TTL 1h）
- **风险**：若 NLI 评分不缓存，每次重检索都重新计算，3 轮重检索耗时翻 3 倍
- **缓解**：NLIScorer.score() 需在注释中标注「调用 M-005 CacheProxy.semantic_set」
- **来源**：[DD-001:IC-003 后置条件] + [DD推断:依据=性能约束]

### [DD-M洞察-M008-005] NLI 模型启动期 CPU 亲和性绑定
- **类型**：性能优化 + 资源争抢
- **描述**：AR INSIGHT-AR-001 记录 M-008 NLI 与 M-014 PDF 翻译存在 CPU 争抢
- **缓解**：NLIModelLoader.bind_cpu_affinity(0) 在启动期调用
- **来源**：[AR:INSIGHT-AR-001] + [DD-001:DD洞察-002]

---

## 七、模块边界合规检查（R28/R29/R30）

| 检查项 | 标准 | 状态 |
|--------|------|------|
| 仅操作 M-008 内文件 | 跨模块文件数 = 0 | ✅ 合规 |
| 未实现其他模块业务逻辑 | M-008 不含 M-014 翻译业务 | ✅ 合规 |
| 产出物含 M-008 标识 | 所有文件带 `_MODULE_ID = "M-008"` | ✅ 合规 |
| 文件命名带模块编号 | 路径含 M-008 目录 | ✅ 合规 |

**模块边界状态：合规（跨模块文件数 = 0）**

---

## 八、文件框架交付清单

| 序号 | 文件 | 注释状态 |
|------|------|---------|
| 1 | `src/aitutor/rag/__init__.py` | 完整（文件头+模块标识）|
| 2 | `src/aitutor/rag/engine.py` | 完整（文件头+类+4 函数）|
| 3 | `src/aitutor/rag/routing/__init__.py` | 完整 |
| 4 | `src/aitutor/rag/routing/keyword.py` | 完整（文件头+类+1 函数）|
| 5 | `src/aitutor/rag/routing/adapter.py` | 完整（文件头+2 类+5 方法）|
| 6 | `src/aitutor/rag/nli/__init__.py` | 完整 |
| 7 | `src/aitutor/rag/nli/model.py` | 完整（文件头+类+3 方法）|
| 8 | `src/aitutor/rag/nli/scorer.py` | 完整（文件头+类+2 方法）|
| 9 | `src/aitutor/rag/indexing/__init__.py` | 完整 |
| 10 | `src/aitutor/rag/indexing/chroma.py` | 完整（文件头+类+2 方法）|
| 11 | `src/aitutor/rag/indexing/adapter.py` | 完整（文件头+2 类+4 方法）|
| 12 | `src/aitutor/rag/translation/__init__.py` | 完整 |
| 13 | `src/aitutor/rag/translation/adapter.py` | 完整（文件头+2 类+2 方法）|
| 14 | `tests/unit/test_rag/__init__.py` | 完整 |
| 15 | `tests/unit/test_rag/test_engine.py` | 完整（6 测试场景）|
| 16 | `tests/unit/test_rag/test_routing.py` | 完整（6 测试场景）|
| 17 | `tests/unit/test_rag/test_nli.py` | 完整（6 测试场景）|
| 18 | `tests/unit/test_rag/test_indexing.py` | 完整（7 测试场景）|
| 19 | `tests/unit/test_rag/test_translation.py` | 完整（6 测试场景）|

**总文件数：19 个**（含 5 个测试文件）

---

## 九、FRI 计算

| 维度 | 当前值 | 最优值 | 达成率 | 权重 | 加权 |
|------|--------|--------|--------|------|------|
| D1 设计规范转化 | 100% | 100% | 100% | 0.22 | 0.220 |
| D2 文件结构合规 | 100% | 100% | 100% | 0.20 | 0.200 |
| D3 注释完整度 | 100% | 100% | 100% | 0.18 | 0.180 |
| D4 接口契约注释化 | 100% | 100% | 100% | 0.16 | 0.160 |
| D5 代码风格合规 | 100% | 100% | 100% | 0.14 | 0.140 |
| D6 文件框架可追溯 | 100% | 100% | 100% | 0.10 | 0.100 |
| **D7 模块边界** | **100%** | **100%** | **100%** | **0.00** | **硬约束** |

**FRI = 1.00**（远高于 0.90 阈值）

---

## 十、框架判定

- D7 = 100%（模块边界合规）
- FRI = 1.00（≥ 0.90 已收敛）
- 4.7 五项检查全通过
- 4.9 12 项自评审清单全通过
- 跨模块文件数 = 0

**最终判定：可交付 DD-S（结构设计师）**

来源标注：[DD-001:FS-M-008] + [DD-001:MD-M-008] + [DD-001:IC-003] + [AR:INSIGHT-AR-001] + [DD-M推断:依据=4.7/4.9 验收]
