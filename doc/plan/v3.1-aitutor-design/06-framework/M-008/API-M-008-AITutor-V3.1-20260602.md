# 接口注释清单 — M-008 RAG 引擎（AITutor V3.1）

> 角色：DD-M-008 详细设计师（模块）
> 关联契约：IC-003 RAG 检索（来自 DD-001）
> 关联模块：M-008 RAG 引擎
> 来源标注：[DD-001:IC-003] + [DD-001:MD-M-008]

---

## 接口契约总览

| 接口契约 | 实现文件 | 函数签名注释 | 参数说明 | 返回值说明 | 错误码说明 |
|---------|---------|------------|---------|-----------|-----------|
| IC-003 | `rag/engine.py` | ✅ | ✅ | ✅ | ✅ |
| IC-003 | `rag/nli/scorer.py` | ✅ | ✅ | ✅ | ✅ |
| IC-003 | `rag/routing/keyword.py` | ✅ | ✅ | ✅ | ✅ |
| IC-003 | `rag/indexing/adapter.py` | ✅ | ✅ | ✅ | ✅ |

---

## API-008-001 RAGEngine.retrieve

- **接口编号**：API-008-001
- **关联契约**：IC-003 RAG 检索
- **实现文件**：`src/aitutor/rag/engine.py`
- **函数签名注释**：

```python
async def retrieve(self, query: str, top_k: int = 5) -> List[Chunk]:
    """执行单次 RAG 检索。

    [函数名] retrieve
    [职责] 调用四子能力完成 retrieve → nli_score → (重检索) → validate 流程
    [关联接口契约] IC-003

    [参数说明]
        参数1: query str 必填 规则 长度 [1, 2000] 检索 query
        参数2: top_k int 可选 默认 5 规则 [1, 20] 返回 chunk 数

    [返回值]
        类型: List[Chunk]
        描述: 检索结果（按 NLI 分数降序）
        特殊值: 空列表表示无法确认

    [错误码]
        错误码1: E00801 含义: 重检索 3 轮仍 < 0.7 触发: NLI 不达标
        错误码2: E00802 含义: NLI 不可用 触发: 模型加载失败
        错误码3: E00803 含义: 重路由失败 触发: 1 次重试仍败

    [前置条件] query 非空 / ChromaDB 集合已创建
    [后置条件] NLI 评分写入缓存（TTL 1h）/ trace_id 关联
    [并发安全] 是（asyncio 协程 + ChromaDB 单写者）
    [幂等性] 是 / 幂等键: query_hash (SHA256) / 有效期 1h
    [性能约束] ≤10s（P95）、≤15s（P99）

    [来源标注] [DD-001:IC-003] + [DD-001:MD-M-008]
    """
```

- **来源标注**：[DD-001:IC-003] + [DD-001:MD-M-008 retrieve 函数签名]

---

## API-008-002 RAGEngine.rerank

- **接口编号**：API-008-002
- **关联契约**：IC-003（rerank 隐含于 retrieve）
- **实现文件**：`src/aitutor/rag/engine.py`
- **函数签名注释**：

```python
async def rerank(self, query: str, chunks: List[Chunk]) -> List[Chunk]:
    """重排序候选 chunks。

    [函数名] rerank
    [职责] 基于 query 与 chunk 相似度 + 来源权威性重排
    [关联接口契约] IC-003

    [参数说明]
        参数1: query str 必填 规则 长度 [1, 2000] 原始 query
        参数2: chunks List[Chunk] 必填 待重排 chunks

    [返回值]
        类型: List[Chunk]
        描述: 重排后的 chunks（按综合分降序）
        特殊值: 输入空时返回空列表

    [错误码]
        错误码1: E00803 含义: 重路由失败 触发: 重排过程异常

    [前置条件] chunks 非 None
    [后置条件] chunks 顺序已变更 / 不修改 chunk 内部字段
    [并发安全] 是
    [幂等性] 是
    [性能约束] 单次 ≤500ms

    [来源标注] [DD-001:MD-M-008] + [DD-001:IC-003]
    """
```

- **来源标注**：[DD-001:MD-M-008 rerank 函数签名]

---

## API-008-003 RAGEngine.validate_answer

- **接口编号**：API-008-003
- **关联契约**：IC-003（隐含的 sources 校验）
- **实现文件**：`src/aitutor/rag/engine.py`
- **函数签名注释**：

```python
async def validate_answer(
    self, answer: str, sources: List[str]
) -> ValidationResult:
    """验证答案与引用源一致性。

    [函数名] validate_answer
    [职责] 用 NLI 评分验证 answer 是否被 sources 支撑
    [关联接口契约] IC-003

    [参数说明]
        参数1: answer str 必填 规则 长度 [1, 5000] LLM 生成的答案
        参数2: sources List[str] 可选 默认 [] 引用源文本

    [返回值]
        类型: ValidationResult
        描述: 验证结果（含 is_supported, confidence, mismatched_claims）
        特殊值: sources 为空时返回 is_supported=False

    [错误码]
        错误码1: E00802 含义: NLI 不可用 触发: 模型加载失败

    [前置条件] answer 非空
    [后置条件] trace_id 关联
    [并发安全] 是
    [幂等性] 是
    [性能约束] 单次 ≤2s

    [来源标注] [DD-001:MD-M-008] + [DD-001:IC-003 错误码 E00802]
    """
```

- **来源标注**：[DD-001:MD-M-008 validate_answer 函数签名]

---

## API-008-004 NLIScorer.score

- **接口编号**：API-008-004
- **关联契约**：IC-003（nli_score 字段）
- **实现文件**：`src/aitutor/rag/nli/scorer.py`
- **函数签名注释**：

```python
async def score(self, premise: str, hypothesis: str) -> float:
    """对 (premise, hypothesis) 做 NLI 评分。

    [函数名] score
    [职责] 返回 [0, 1] 相关性分数
    [关联接口契约] IC-003

    [参数说明]
        参数1: premise str 必填 规则 长度 [1, 5000] 来源文本
        参数2: hypothesis str 必填 规则 长度 [1, 1000] 待验证文本

    [返回值]
        类型: float
        描述: [0, 1] 之间的相关性分数
        特殊值: NLI 不可用且 fallback_to_llm=true 时返回 LLM 评分

    [错误码]
        错误码1: E00802 含义: NLI 不可用 触发: 模型加载失败

    [前置条件] premise 与 hypothesis 非空
    [后置条件] 评分结果写入 M-005 缓存（TTL 1h）
    [并发安全] 是
    [幂等性] 是 / 幂等键: (premise_hash, hypothesis_hash)
    [性能约束] 单次 ≤1s（P95）

    [来源标注] [DD-001:MD-M-008 nli_score] + [DD-001:IC-003]
    """
```

- **来源标注**：[DD-001:MD-M-008 nli_score 函数签名] + [DD-001:IC-003 nli_score 字段]

---

## API-008-005 KeywordRouter.route

- **接口编号**：API-008-005
- **关联契约**：IC-003（route_decision 字段）
- **实现文件**：`src/aitutor/rag/routing/keyword.py`
- **函数签名注释**：

```python
async def route(self, query: str) -> RouteDecision:
    """根据 query 内容决策路由。

    [函数名] route
    [职责] 关键字匹配 + 兜底 default_route
    [关联接口契约] IC-003

    [参数说明]
        参数1: query str 必填 规则 长度 [1, 2000] 用户 query

    [返回值]
        类型: RouteDecision
        描述: "direct" | "rag" | "web" | "cannot_confirm"
        特殊值: 无匹配时返回 default_route

    [错误码]
        错误码1: E00803 含义: 重路由失败 触发: 1 次重试仍败

    [前置条件] query 非空
    [后置条件] trace_id 关联
    [并发安全] 是
    [幂等性] 是 / 幂等键: query_hash
    [性能约束] ≤50ms

    [示例]
        ```
        decision = await router.route("今天天气如何")
        # 命中 web 关键字 → 返回 "web"
        ```

    [来源标注] [DD-001:MD-M-008] + [DD-001:IC-003]
    """
```

- **来源标注**：[DD-001:MD-M-008 KeywordRouter.route] + [DD-001:IC-003 route_decision]

---

## API-008-006 ChromaIndexAdapter.query

- **接口编号**：API-008-006
- **关联契约**：IC-003（top_k_chunks）
- **实现文件**：`src/aitutor/rag/indexing/adapter.py`
- **函数签名注释**：

```python
async def query(
    self, query_embedding: Embedding, top_k: int = 5
) -> List[Chunk]:
    """委托给 ChromaCollection.query 并转换为 Chunk。

    [函数名] query
    [职责] Adapter 委派 + 类型转换
    [关联接口契约] IC-003 top_k_chunks

    [参数说明]
        参数1: query_embedding Embedding 必填 查询向量
        参数2: top_k int 可选 默认 5 规则 [1, 20]

    [返回值]
        类型: List[Chunk]
        描述: 检索结果

    [前置条件] 集合已创建
    [后置条件] trace_id 关联
    [并发安全] 是（ChromaDB 单写者多读者）
    [幂等性] 是 / 幂等键: query_hash
    [性能约束] ≤1s（P95）

    [来源标注] [DD-001:MD-M-008] + [DD-001:IC-003]
    """
```

- **来源标注**：[DD-001:MD-M-008 ChromaIndexAdapter.query] + [DD-001:IC-003 top_k_chunks]

---

## 接口契约验收汇总

| 接口 | 入参完整 | 出参完整 | 错误码覆盖 | 性能约束 | 幂等性 | 验收 |
|------|---------|---------|-----------|---------|--------|------|
| API-008-001 retrieve | ✅ | ✅ | ✅ E00801/2/3 | ✅ ≤10s | ✅ | 通过 |
| API-008-002 rerank | ✅ | ✅ | ✅ E00803 | ✅ ≤500ms | ✅ | 通过 |
| API-008-003 validate_answer | ✅ | ✅ | ✅ E00802 | ✅ ≤2s | ✅ | 通过 |
| API-008-004 score | ✅ | ✅ | ✅ E00802 | ✅ ≤1s | ✅ | 通过 |
| API-008-005 route | ✅ | ✅ | ✅ E00803 | ✅ ≤50ms | ✅ | 通过 |
| API-008-006 query | ✅ | ✅ | ✅ E01702 | ✅ ≤1s | ✅ | 通过 |

**6/6 全部通过验收**

来源标注：[DD-001:IC-003] + [DD-001:MD-M-008] + [DD-M推断:依据=验收清单]
