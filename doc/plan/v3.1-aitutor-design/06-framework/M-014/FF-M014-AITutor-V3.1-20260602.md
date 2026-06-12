# FF-M014-AITutor-V3.1-20260602 — M-014 数据管线文件框架结构

> **模块**: M-014 数据管线（Data Pipeline）
> **设计模式**: Template Method + ThreadPool
> **版本**: AITutor V3.1
> **日期**: 2026-06-02
> **作者**: DD-M-014-20260602
> **来源**: [DD-001:FS-M014/MD-M014] + [DD-M推断:依据=DD-001:CS-AITutor-V3.1]

---

## 一、文件框架总览

### 1.1 目录结构

```
产出物/07-文件框架/M-014/
├── aitutor/
│   └── ingest/                    ← M-014 模块根目录
│       ├── __init__.py            ← [公共接口 re-export]
│       ├── models.py              ← [领域模型：ProcessResult/Chunk/PipelineStage/...]
│       ├── exceptions.py          ← [自定义异常：IngestError/TranslationFailedError/...]
│       ├── state_machine.py       ← [FSM：PipelineStateMachine 7 状态 + 转移规则]
│       ├── pipeline.py            ← [主调度器：DataPipeline（Template Method）]
│       ├── clean.py               ← [Stage 1：TextCleaner 文本清洗]
│       ├── chunk.py               ← [Stage 2：Chunker 文本分块]
│       ├── ingester.py            ← [Stage 3：Ingester 入库 ChromaDB+SQLite]
│       └── translate/             ← [子能力命名空间：3 翻译后端 + 工厂]
│           ├── __init__.py        ← [工厂方法 create_translator / FALLBACK_ORDER]
│           ├── base.py            ← [BaseTranslator 抽象基类]
│           ├── pdf2zh.py          ← [PDF2ZhTranslator — 1 级默认]
│           ├── pdfplumber.py      ← [PDFPlumberTranslator — 2 级降级]
│           └── lmstudio.py        ← [LMStudioTranslator — 3 级降级]
└── tests/
    └── unit/
        └── test_ingest/           ← M-014 单元测试目录
            ├── __init__.py        ← [测试包入口]
            ├── test_pipeline.py   ← [DataPipeline 16 用例]
            ├── test_state_machine.py ← [FSM 7 用例]
            ├── test_clean.py      ← [TextCleaner 4 用例]
            ├── test_chunk.py      ← [Chunker 5 用例]
            ├── test_ingester.py   ← [Ingester 4 用例]
            └── test_translate.py  ← [3 后端+工厂 8 用例]
```

### 1.2 文件清单与职责矩阵

| 文件 | 职责 | 依赖 | 被依赖 |
|------|------|------|--------|
| `__init__.py` | 公共接口 re-export | 全部 | `aitutor/api/v1/ingest.py` |
| `models.py` | 领域模型（ProcessResult/Chunk/...） | 无（叶节点） | 全部 |
| `exceptions.py` | 自定义异常（6 类） | shared.exceptions | 全部 |
| `state_machine.py` | FSM 7 状态机 | models | pipeline |
| `pipeline.py` | DataPipeline 主调度 | 全部内部模块 | API 层 |
| `clean.py` | 文本清洗 Stage | models + exceptions | pipeline |
| `chunk.py` | 文本分块 Stage | models | pipeline |
| `ingester.py` | 入库 Stage（ChromaDB+SQLite） | models + storage/M-017 | pipeline |
| `translate/__init__.py` | 工厂方法 + 降级链常量 | 3 后端 | pipeline |
| `translate/base.py` | 翻译器抽象基类 | exceptions | 3 后端 |
| `translate/pdf2zh.py` | 1 级翻译后端 | base | translate/__init__ |
| `translate/pdfplumber.py` | 2 级降级后端 | base | translate/__init__ |
| `translate/lmstudio.py` | 3 级降级后端 | base + pdfplumber | translate/__init__ |
| `tests/...` | 单元测试（44 用例） | M-014 全部 | CI |

### 1.3 文件间依赖图

```
api/v1/ingest.py (M-002)
    ↓
aitutor/ingest/__init__.py
    ↓
aitutor/ingest/pipeline.py (DataPipeline)
    ↓       ↓       ↓        ↓
clean.py  chunk.py  ingester.py  translate/__init__.py
    ↓       ↓       ↓        ↓
    models.py (Chunk/ProcessResult/...) ← exceptions.py
                  ↓
              shared/exceptions (M-006/M-017 跨模块)

注：ingester.py 跨模块依赖 M-017 storage.UnitOfWork（DD-001:MD-M014 标注）
```

---

## 二、文件结构 5 项合规检查（DD-001 4.7）

| 检查项 | 检查标准 | 通过情况 |
|--------|---------|---------|
| **目录层级** | 目录层级 ≥ 2 层 | ✅ 3 层（`aitutor/ingest/...`） |
| **文件命名** | snake_case 符合 PEP8 | ✅ 全部 snake_case |
| **文件职责** | 每个文件单一明确职责 | ✅ 13 个文件职责互不重叠 |
| **依赖关系** | 无循环依赖 | ✅ 单向依赖：models ← exceptions ← 子能力 ← pipeline ← __init__ |
| **最佳实践** | Python src layout + __init__.py | ✅ 标准 src layout |

**合规度判定**：5/5 全部通过 → **合规度 = 高**

---

## 三、模块边界守护（D7=100）

| 检查项 | 结果 |
|--------|------|
| 本 DD-M 负责模块 | M-014 |
| 操作文件数 | 20 个（13 业务文件 + 7 测试文件 + 5 框架元文件） |
| 跨模块文件数 | **0** |
| 状态 | ✅ **合规（D7=100）** |
| 跨模块依赖声明 | M-006 事件总线（trace_id）+ M-017 存储（UnitOfWork）— 已在文件头注释中标注 |

---

## 四、文件命名规范

| 文件类型 | 命名 | M-014 实例 |
|---------|------|-----------|
| 模块入口 | `__init__.py` | `aitutor/ingest/__init__.py` |
| 模型定义 | `models.py` | `aitutor/ingest/models.py` |
| 业务逻辑 | `pipeline.py` | `aitutor/ingest/pipeline.py` |
| 状态机 | `state_machine.py` | `aitutor/ingest/state_machine.py` |
| 异常 | `exceptions.py` | `aitutor/ingest/exceptions.py` |
| 适配器 | `<backend>.py` | `translate/pdf2zh.py` 等 |
| 测试 | `test_<module>.py` | `tests/unit/test_ingest/test_*.py` |
| Fixture | `__init__.py` | `tests/unit/test_ingest/__init__.py` |

---

## 五、产出物清单

| 编号 | 文件 | 类型 | 状态 |
|------|------|------|------|
| FF-M014 | `FF-M014-AITutor-V3.1-20260602.md` | 文件框架结构 | ✅ |
| API-M014 | `API-M014-AITutor-V3.1-20260602.md` | 接口注释清单 | ✅ |
| FC-M014 | `FC-M014-AITutor-V3.1-20260602.md` | 文件结构合规报告 | ✅ |
| FDR-M014 | `FDR-M014-AITutor-V3.1-20260602.md` | 框架决策记录 | ✅ |
| FH-M014 | `FH-M014-AITutor-V3.1-20260602.md` | 文件框架健康度仪表盘 | ✅ |

**所有产出物均含 M-014 模块编号标识（DD-001:soul 6.1 R30 红线）**

---

## 来源标注

[DD-001:FS-M014/MD-M014/IC-004/CS-AITutor-V3.1] + [DD-M推断:依据=DD-001:soul 04-soul-详细设计师（模块）v1.8 模板]
