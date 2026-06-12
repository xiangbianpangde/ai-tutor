# 文件框架结构 — M-007 Pipeline 调度

> 对应模块: M-007
> 关联设计规范: FS-M-007 / MD-M-007 / IC-002 / IC-003
> 来源标注: [DD-001:FS-M-007]
> 作者: DD-M-007-20260602

---

## 模块概述

| 属性 | 值 |
|------|-----|
| 模块编号 | M-007 |
| 模块名称 | Pipeline 调度（Pipeline + Strategy） |
| 关联技术选型 | TS-001 Python / TS-002 FastAPI / TS-006 httpx |
| 关联接口 | IC-002（学习回合）/ IC-003（RAG 检索） |
| 子模块数 | 5（sm007-preprocess / retrieve / rerank / llm / postprocess） |
| 类数 | 7（PipelineOrchestrator / PipelineState / FallbackStrategy / PipelineStage / 5 Stage 类 + BaseStage） |
| 函数签名 | 6（execute_pipeline / preprocess / retrieve / rerank / call_llm / postprocess + 状态/兜底辅助） |
| 状态机 | 1（7 状态：INIT/PREPROCESS/RETRIEVE/RERANK/LLM/POSTPROCESS/DONE/LLM_FALLBACK） |

---

## 文件框架

```
M-007/
├── FF-M-007-AITutor-V3.1-20260602.md          ← [职责：文件框架结构文档]
├── API-M-007-AITutor-V3.1-20260602.md         ← [职责：接口注释清单]
├── FC-M-007-AITutor-V3.1-20260602.md          ← [职责：文件结构合规报告]
├── FDR-M-007-AITutor-V3.1-20260602.md         ← [职责：框架决策记录]
├── FH-M-007-AITutor-V3.1-20260602.md          ← [职责：文件框架健康度仪表盘]
├── src/aitutor/pipeline/                      ← M-007 源码目录
│   ├── __init__.py                            ← [职责：模块入口，导出公共符号]
│   ├── orchestrator.py                        ← [职责：PipelineOrchestrator + 6 函数]
│   │   - [类 PipelineOrchestrator 注释]
│   │   - [函数 execute_pipeline 注释]
│   │   - [函数 preprocess/retrieve/rerank/call_llm/postprocess 注释]
│   ├── state.py                               ← [职责：FSM 状态机]
│   │   - [枚举 PipelineStage 注释]
│   │   - [类 PipelineState 注释]
│   │   - [函数 mark_stage/transition_state/is_stuck 注释]
│   ├── fallback.py                            ← [职责：兜底策略]
│   │   - [类 FallbackStrategy 注释]
│   │   - [函数 should_fallback/execute_fallback/write_audit 注释]
│   └── stages/
│       ├── __init__.py                        ← [职责：5 阶段子包入口]
│       ├── preprocess.py                      ← [职责：阶段1 query 预处理]
│       │   - [类 BaseStage 注释]
│       │   - [类 PreprocessStage 注释]
│       │   - [方法 run/tokenize/extract_keywords/detect_intent 注释]
│       ├── retrieve.py                        ← [职责：阶段2 RAG 检索]
│       │   - [类 RetrieveStage 注释]
│       │   - [方法 run/_call_rag/_adapt_result 注释]
│       ├── rerank.py                          ← [职责：阶段3 重排序]
│       │   - [类 RerankStage 注释]
│       │   - [方法 run/_nli_score 注释]
│       ├── llm.py                             ← [职责：阶段4 LLM 调用]
│       │   - [类 LLMStage 注释]
│       │   - [方法 run/_build_prompt/_call_provider 注释]
│       └── postprocess.py                     ← [职责：阶段5 答案后处理]
│           - [类 PostprocessStage 注释]
│           - [方法 run/_replace_placeholders/_build_sources_section 注释]
└── tests/unit/test_pipeline/                  ← M-007 测试目录
    ├── __init__.py                            ← [职责：测试子包入口]
    ├── test_orchestrator.py                   ← [职责：8 用例：核心 5 + 边界 2 + 异常 1]
    │   - [测试场景 1~8 注释]
    ├── test_state.py                          ← [职责：6 用例：FSM 转换 + 卡死]
    │   - [测试场景 1~6 注释]
    ├── test_fallback.py                       ← [职责：4 用例：兜底成功 + audit + 失败]
    │   - [测试场景 1~4 注释]
    └── test_stages/
        ├── __init__.py                        ← [职责：阶段测试子包]
        ├── test_preprocess.py                 ← [职责：4 用例]
        ├── test_retrieve.py                   ← [职责：5 用例]
        ├── test_rerank.py                     ← [职责：3 用例]
        ├── test_llm.py                        ← [职责：5 用例]
        └── test_postprocess.py                ← [职责：3 用例]
```

---

## 文件间依赖关系

```
api/v1/turn.py (M-002)
  ↓
orchestrator.py ──→ state.py
  ├──→ stages/preprocess.py ──→ shared/types
  ├──→ stages/retrieve.py ──→ rag/engine (M-008)
  ├──→ stages/rerank.py ──→ rag/nli (M-008)
  ├──→ stages/llm.py ──→ httpx
  ├──→ stages/postprocess.py ──→ shared/types
  └──→ fallback.py ──→ state.py + stages/llm.py + monitor/logger

tests/ → [被测试文件]（镜像依赖）
```

### 关键约束

| 层级 | 允许依赖 | 禁止依赖 |
|------|---------|---------|
| `pipeline/orchestrator.py` | `state.py` / `stages/*` / `fallback.py` / `monitor/logger` | `api/`（反向依赖禁止） |
| `pipeline/stages/*` | `shared/types` / `rag/engine` | `api/` / `service` |
| `pipeline/state.py` | `shared/types` | `stages/*`（避免循环） |
| `pipeline/fallback.py` | `state.py` / `stages/llm.py` | `orchestrator.py`（避免循环） |

无循环依赖（R26 验证通过）。

---

## 来源标注

[DD-001:FS-M-007] + [DD-001:MD-M-007 类设计行] + [DD-M推断:依据=FS-M-007 M-007 段目录结构]
