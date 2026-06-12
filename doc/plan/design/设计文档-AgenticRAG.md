# 设计文档：Agentic RAG

> 涉及模块：`backend/rag/`（retriever / reranker / agent）
> 解决问题：#9(重检索), #11(缓存+监控), #15(Agentic RAG)

## 背景

当前项目**没有检索层**。知识图谱查询 (`query_knowledge`) 只是简单的 DB 查询：
- `concept`：SQL LIKE 模糊匹配
- `neighbors`：固定类型边查询
- `path`：networkx 最短路径
- `subgraph`：N 跳 BFS

这导致（问题 #9）：
> "搜索 ACP 大模型应用，考试要求 50%，你搜集到 45%，得到 35%，没过。
>  重索引能搜集 45%，深入搜索 70%~80%"

缺少 Agentic RAG 的核心能力：初检 → 评估 → 改写 → 深入检索 → 精排。

## 目标

- 实现多轮迭代检索：初检覆盖面 → 自我评估 → 查询改写 → 再检索 → 精排
- 向量检索 + 关键词检索双路召回
- 检索结果与 KG 概念关联（检索到的知识自动定位到 KG 节点）
- 缓存常见查询，避免重复检索
- 监控每次检索质量，反馈到管线优化

## 方案

### Agentic RAG 流程

```
用户查询 "ACP大模型应用考试要求"
          │
          ▼
┌─────────────────────┐
│ 1. Query Rewrite    │ ← LLM 改写：拆分子问题、扩展同义词
│    → ["ACP认证考试大纲", "阿里云大模型应用知识点", ...]
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 2. Dual Retrieve    │ ← 向量检索 (本地KG) + research-tool 10源搜索
│    → 各召回 top 20  │      Collector.search_only(query, deep_search=True)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 3. Rerank           │ ← BGE-Reranker / LLM Cross-encoder
│    → 精排 top 10    │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 4. Self-Evaluate    │ ← LLM 评估覆盖率 "已覆盖 45%，缺: 模型部署/推理优化"
│    → coverage_score │
└────────┬────────────┘
         │
    coverage < 70%?
         │ YES
         ▼
┌─────────────────────┐
│ 5. Deep Retrieve    │ ← 针对缺口生成新查询，深入检索
│    → "ACP大模型部署 推理优化 vLLM"  │
│    → 追加 top 10    │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 6. Final Rerank     │ ← 合并两轮结果，精排 + 去重
│    → top 15         │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ 7. KG Link          │ ← 结果中的概念映射到 KG 节点
│    → "部署优化" → kg:acp:3.2:vllm_bushu
└────────┬────────────┘
         │
         ▼
     返回结果
```

### 核心组件

```python
# backend/rag/retriever.py

class DualRetriever:
    """双路检索：向量 + 关键词。"""

    def __init__(self):
        self.vector_store = VectorStore()    # ChromaDB 或 numpy 本地
        self.bm25_index = BM25Index()        # 基于 rank-bm25

    def retrieve(self, queries: list[str], top_k: int = 20) -> list[Document]:
        dense = self.vector_store.search(queries, top_k)
        sparse = self.bm25_index.search(queries, top_k)
        return fusion_rerank(dense, sparse)  # RRF 融合
```

```python
# backend/rag/reranker.py

class Reranker:
    """精排器。本地模型优先，LLM 兜底。"""

    def rerank(self, query: str, docs: list[Document], top_k: int) -> list[Document]:
        # 优先：本地 BGE-Reranker (bge-reranker-v2-m3, 软探测)
        # 兜底：LLM Cross-encoder (DeepSeek, 耗 token 但质量高)
```

```python
# backend/rag/agent.py

class RAGAgent:
    """Agentic RAG 代理。多轮迭代检索。"""

    def search(self, query: str, target_coverage: float = 0.70) -> RAGResult:
        # 1. rewrite
        # 2. retrieve → rerank
        # 3. evaluate coverage
        # 4. if coverage < target: deep_retrieve → rerank
        # 5. link_to_kg
        # 6. return + record monitor
```

### 检索源

| 源 | 说明 | 实现 |
|----|------|------|
| 本地 KG | 已构建的知识图谱概念 | DualRetriever 搜索 KG 节点 |
| 本地文件 | 用户拖拽上传的 PDF/MD | 预先切 chunk + embedding 入库 |
| 网络搜索 | **10 源并行搜索**（web/arxiv/openalex/semantic_scholar/pubmed/wikipedia/github/google_news/tavily/crossref）| 委托 research-tool `Collector.search_only()` |
| Deepen 深挖 | 反偏差多视角搜索（画像注入/时间线回溯/同名消歧）| 委托 research-tool `DeepenStage` |
| Backward 反传 | 检测缺口→修正查询→追加检索 | 委托 research-tool `Backward` |
| Obsidian Vault | 用户的 Obsidian 笔记 | sync-mcp 已支持拉取，增量索引 |

## 影响范围

- **新增**：`backend/rag/` 3 个文件 + 测试
- **依赖**：软探测 `chromadb`、`sentence-transformers`、`rank-bm25`。缺则降级到纯 LLM 检索
- **修改**：`backend/engines/knowledge/kg_query.py` → `query_knowledge` 内部可选走 RAG
- **不修改**：教学引擎（RAG 是检索层，与教学解耦）

## 风险

| 风险 | 缓解 |
|------|------|
| RAG 多轮迭代耗 token（每轮 LLM 评估 + 改写） | 评估用轻量 prompt（≤200 token），迭代上限 3 轮 |
| 本地 embedding 模型下载慢/体积大 | 软探测，缺失时降级到 LLM embedding API |
| 检索结果与 KG 概念匹配错误 | 匹配时用 cosine 相似度阈值（>0.75），低于阈值不强行关联 |
