# FF-M-015 文件框架结构 — AITutor V3.1（M-015 打包调度）

> 负责模块: **M-015 打包调度（Command + Factory）**
> 作者: DD-M-015 / 2026-06-02
> 上游来源: [DD-001:MD-M015] + [DD-001:FS-M015 line 514-526] + [DD-001:IC-005] + [DD-001:CS-001]

---

## 1. 模块边界（D7=100 硬约束）

- **唯一负责模块**: M-015
- **允许操作路径**: `产出物/07-文件框架/M-015/aitutor/build/**` + `产出物/07-文件框架/M-015/tests/unit/test_build/**`
- **跨模块文件操作数**: **0**（已校验，所有文件路径均在 M-015 根目录下）
- **跨模块依赖（仅注释引用，不操作其代码）**: M-006 monitor / M-017 storage / shared
- **遵守红线**: R28（禁止跨模块操作）/ R29（禁止职责扩散）/ R30（产物含 M-015 标识）✅

---

## 2. 文件框架（5 项合规检查全通过）

```
产出物/07-文件框架/M-015/
├── aitutor/
│   └── build/                       ← M-015 打包调度模块根
│       ├── __init__.py              ← [职责: 公共接口 re-export]
│       ├── orchestrator.py          ← [职责: Command + Factory 编排 FSM 三阶段]
│       │   ├─ BuildState (Enum)     ← FSM 状态
│       │   ├─ BuildCommand (Dataclass) ← Command 模式封装请求
│       │   ├─ NuitkaBuilderFactory  ← Factory 模式选择 builder
│       │   ├─ BuildOrchestrator     ← 主编排器
│       │   └─ build_artifact()      ← 公开函数（IC-005 入口）
│       ├── nuitka.py                ← [职责: Nuitka onedir 三平台构建]
│       │   └─ NuitkaBuilder         ← 平台化构建器
│       ├── upx.py                   ← [职责: UPX 压缩 + 软降级]
│       │   ├─ UPXCompressor
│       │   └─ compress_artifact()
│       └── verifier.py              ← [职责: sha256 + 体积门禁校验]
│           ├─ VerifyResult (Dataclass)
│           ├─ ArtifactVerifier
│           └─ verify_artifact()
└── tests/
    └── unit/
        └── test_build/              ← [职责: M-015 单元测试]
            ├── __init__.py
            ├── test_orchestrator.py ← 4 测试场景（核心 2 + 边界 1 + 异常 1）
            ├── test_nuitka.py       ← 3 测试场景（核心 1 + 平台差异 1 + 异常 1）
            ├── test_upx.py          ← 2 测试场景（正常 + 软降级）
            └── test_verifier.py     ← 3 测试场景（sha256 + 体积 + 不匹配）

合计: 9 个 Python 文件（5 源码 + 4 测试 + 2 init）
测试用例总数: 12（与 MD-M015 测试策略 line 456 一致）
```

---

## 3. 文件间依赖关系（无循环导入 ✅）

```
orchestrator.py
    ├─→ nuitka.py    (NuitkaBuilder)
    ├─→ upx.py       (UPXCompressor, compress_artifact)
    ├─→ verifier.py  (ArtifactVerifier, verify_artifact, VerifyResult)
    ├─→ [跨模块] monitor/bus.py     (publish_event)
    ├─→ [跨模块] monitor/trace.py   (new_trace_id)
    └─→ [跨模块] shared/exceptions.py (BuildError)

nuitka.py  ─→ [跨模块] shared/exceptions.py
upx.py     ─→ [跨模块] shared/exceptions.py
verifier.py─→ [跨模块] shared/exceptions.py

测试 → 对应被测文件（单向，无反向依赖）
```

**Import Linter 合规**: 本模块仅依赖 shared 与 monitor，未反向依赖 api/service 层（CS-001 contract:2/5）✅

---

## 4. 文件结构 5 项合规检查

| 检查项 | 标准 | 状态 |
|-------|------|------|
| 目录层级 | ≥2 层（aitutor/build/） | 通过 ✅（2-3 层）|
| 文件命名 | snake_case + PEP8 | 通过 ✅ |
| 文件职责 | 单一明确（orchestrator/nuitka/upx/verifier 四分离）| 通过 ✅ |
| 依赖关系 | 单向 + 无循环 | 通过 ✅ |
| 最佳实践 | Python src layout + Command/Factory 模式 | 通过 ✅ |

**5/5 全部通过**

---

## 5. 来源可追溯性

| 设计元素 | 来源 |
|---------|------|
| 模块编号 M-015 | [DD-001:MD-M015 line 428] |
| 设计模式 Command + Factory | [DD-001:MD-M015 line 428] |
| 子模块 sm015-nuitka/upx/verify | [DD-001:MD-M015 line 432-434] |
| 类 BuildOrchestrator/NuitkaBuilder/UPXCompressor/ArtifactVerifier | [DD-001:MD-M015 line 435-439] |
| 函数 build_artifact/compress_artifact/verify_artifact | [DD-001:MD-M015 line 440-444] |
| 状态机 PENDING→BUILDING→COMPRESSING→VERIFYING→READY/FAILED | [DD-001:MD-M015 line 445-450] |
| 错误码 E01501~E01504 | [DD-001:IC-005 line 183-187] + [DD-001:MD-M015 line 451-454] |
| 体积门禁 CLI 50MB / GUI 200MB | [DD-001:IC-005 E01501] + [DD-001:EX-020] |
| 文件结构 build/__init__/orchestrator/nuitka/upx/verifier | [DD-001:FS-M015 line 514-526] |
| 代码风格 PEP8 + Google Docstring | [DD-001:CS-001 §1-§3] |
| FSM Factory 选择 builder 的 _build_args 平台差异 | [DD-M推断:依据=Nuitka 官方文档三平台编译标志] |
| UPX macOS 兼容性软降级 | [DD-M推断:依据=UPX 4.x 已知问题] + [DD-001:ADR-009 软约束] |

**可追溯率: 100%**
