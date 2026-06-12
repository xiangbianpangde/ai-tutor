# 文件框架结构 — M-010 费曼评分

> 模块: M-010 费曼评分（Strategy）
> 关联设计规范: FS-010 / MD-010 / IC-002
> 作者: DD-M-010-20260602
> 来源标注: [DD-001:FS-010] + [DD-001:MD-010] + [DD-001:IC-002] + [DD-001:CS]

---

## 1. 模块概览

| 项 | 值 |
|----|----|
| 模块编号 | M-010 |
| 模块名称 | 费曼评分 |
| 设计模式 | Strategy |
| 关联技术选型 | TS-001 Python 3.11 / TS-006 httpx |
| 关联接口契约 | IC-002（学习回合 — action=learn 触发评分；E00901 → 兜底） |
| 测试策略 | 8 用例 / 覆盖率 ≥75% |
| 跨模块依赖 | aitutor.shared.exceptions（DD-001 共享层）/ aitutor.monitor.logger（M-006） |
| 被依赖模块 | aitutor.teaching.orchestrator（M-009 仅通过包入口调用） |

---

## 2. 文件框架（绝对路径以 src/ 为根）

```
src/aitutor/feynman/
├── __init__.py        ← 模块入口；导出 FeynmanScorer / FeynmanPromptBuilder / ScoreParser；工厂 build_feynman_scorer
├── scorer.py          ← 评分器主类（Strategy 入口）；FeynmanScorer + FeynmanScore（dataclass）
├── prompt.py          ← Prompt 构造器；FeynmanPromptBuilder + 默认模板常量
└── parser.py          ← 响应解析器；ScoreParser + ParsedScore（dataclass）

tests/unit/test_feynman/
├── __init__.py        ← 测试包入口
├── test_scorer.py     ← 4 用例（正常 + 钳制 + LLM 不可用 + 解析重试）
├── test_prompt.py     ← 2 用例（渲染正确 + 注入防御）
└── test_parser.py     ← 2 用例（多格式解析 + fallback 兜底）
```

**文件计数：** 源文件 4 个 + 测试文件 4 个 = 8 个（满足 MD-010 子模块复杂度 × 2~5 范围）。

---

## 3. 文件职责矩阵

| 文件 | 职责（≤50字） | 子模块映射 |
|------|----------------|-----------|
| `feynman/__init__.py` | 公共接口 re-export + 工厂函数 `build_feynman_scorer` | — |
| `feynman/scorer.py` | FeynmanScorer 编排 Prompt→LLM→解析；E01001/E01002 兜底 | sm010-score |
| `feynman/prompt.py` | Prompt 模板构造 + 注入防御 | sm010-prompt |
| `feynman/parser.py` | LLM 响应多层容错解析（JSON→Regex→fallback） | sm010-score 解析子任务 |
| `tests/unit/test_feynman/test_scorer.py` | 验证 score_feynman 主流程 + 越界钳制 + 兜底 + 重试 | — |
| `tests/unit/test_feynman/test_prompt.py` | 验证 build 渲染 + injection 防御 | — |
| `tests/unit/test_feynman/test_parser.py` | 验证多格式解析 + fallback | — |

---

## 4. 文件间依赖关系（含 Import Linter contracts 校验）

### 4.1 内部依赖（M-010 内）

```
scorer.py
  ├─→ prompt.py（FeynmanPromptBuilder）
  ├─→ parser.py（ScoreParser, ParsedScore）
  └─→ __init__.py（仅 re-export，不反向依赖）

__init__.py
  └─→ scorer.py / prompt.py / parser.py（TYPE_CHECKING 守卫，运行期不导入避免循环）
```

### 4.2 外部依赖（跨模块）

| 方向 | 依赖目标 | 用途 | 合规性 |
|------|---------|------|--------|
| M-010 → aitutor.shared.exceptions | LLMUnavailableError / ScoreParseError | 异常基类 | ✅（shared 层允许被业务模块依赖） |
| M-010 → aitutor.monitor.logger（M-006） | 结构化日志 + trace_id | 日志注入 | ✅（monitor 提供横切关注点） |
| M-010 ← aitutor.teaching.orchestrator（M-009） | M-009 调用本模块 | 教学编排触发评分 | ✅（仅通过 `__init__` 暴露的公共接口） |

**Import Linter 合规：**
- contract:4（Models 不依赖业务模块）— 本模块 dataclass 仅依赖 shared，✅
- 无循环依赖（scorer→prompt+parser 单向），✅

---

## 5. 设计要点（来自 MD-010 + DD-M 补充）

1. **Strategy 落点：** 三类（Scorer/Prompt/Parser）均设计为可替换实现，构造时通过 `__init__` 注入，便于单元测试 Mock 与未来替换为规则评分 / 混合评分。
2. **Score 钳制：** `_clamp_score` 兜底将越界值钳到 [0, 5]，避免 LLM "幻觉" 分数破坏下游教学状态机。
3. **解析容错三层：** JSON → Regex → fallback，每层失败不抛异常而是返回 None，最外层 `parse` 统一决策是否抛 `ScoreParseError`。
4. **降级语义：** `FeynmanScore.degraded=True` 显式标记走兜底，下游 M-009 可据此触发 FSM 兜底（IC-002 E00901）。
5. **Prompt 注入防御：** `_sanitize` 转义用户输入，包裹分隔符，避免 user_answer 篡改 system 指令（CS 8 安全规范）。
6. **类型不可变：** FeynmanScore / ParsedScore 均为 `@dataclass(frozen=True, slots=True)`，并发安全 + 性能优化。

---

## 6. 跨模块协议（与 M-009 / M-006 / shared 的接触面）

| 接触面 | 方向 | 接口 | 备注 |
|--------|------|------|------|
| M-010 → M-006 | logger.bind(trace_id=...) | 日志注入 trace_id | DD-M 不创建/修改 M-006 文件，仅引用 |
| M-010 → shared | LLMUnavailableError / ScoreParseError | 异常 | DD-M 不创建/修改 shared 文件，仅 import |
| M-009 → M-010 | `from aitutor.feynman import build_feynman_scorer, FeynmanScorer` | 唯一公开入口 | M-009 由别的 DD-M 实例负责，本实例不触碰 |

**模块边界检查：** 本 DD-M-010 仅创建 `产出物/07-文件框架/M-010/` 路径下文件，跨模块文件操作数 = 0。

---

## 7. 来源可追溯性矩阵

| 文件框架元素 | 来源 |
|--------------|------|
| feynman/ 目录 + 3 源文件 | [DD-001:FS-010] |
| FeynmanScorer / FeynmanPromptBuilder / ScoreParser 类 | [DD-001:MD-010 类设计] |
| score_feynman / build / parse 函数签名 | [DD-001:MD-010 函数签名] |
| E01001 / E01002 异常处理 | [DD-001:MD-010 异常处理] |
| 测试 8 用例配比 | [DD-001:MD-010 测试策略] |
| FeynmanScore.degraded 字段 | [DD-M推断:依据=IC-002 E00901 兜底语义可观测性] |
| ParsedScore.strategy 字段 | [DD-M推断:依据=审计/日志可追溯] |
| _sanitize 注入防御 | [DD-M推断:依据=CS 8 安全规范] |
| _clamp_score 越界钳制 | [DD-M推断:依据=防御性编程] |
| 多层容错（JSON→Regex→fallback） | [DD-M推断:依据=LLM 实际输出多样性] |
| build_feynman_scorer 工厂函数 | [DD-M推断:依据=DI 测试友好] |

**总条目：11 项，DD-001 来源 5 项 / DD-M 推断 6 项 / 推断标注率 100%。**

---

来源标注：[DD-001:FS-010/MD-010/IC-002/CS] + [DD-M-010 推断]
