# ADR-0003: M-008 RAG 务实落地——词法检索 + 启发式验证，不引 ChromaDB / NLI 模型

> 日期: 2026-06-15
> 状态: 已采纳

## 背景

v3.1 设计包 FF-M-008 定的 RAG 引擎要 **ChromaDB**（向量索引）+ **DeBERTa-v3-large-mnli**
（NLI 答案验证）。两者都是重依赖：ChromaDB 拉一串 C/C++ 扩展，DeBERTa 要从 HuggingFace
下 1.5GB 模型权重。而本机有据可查的**死系统代理**（127.0.0.1:7897，见持久记忆
`dead-system-proxy-workaround`）会让任何模型下载/索引初始化 10054 全炸；FF-M-008 自己也
标注 M-008 内聚度 3/6 最低、NLI 与 PDF 翻译存在 CPU 争抢。当前阶段（C3，核心引擎就位）
真正要的是**可端到端跑通、可测、确定性**的 RAG 闭环，不是 100 用户规模的向量召回。

## 决策

RAG 引擎**当前阶段务实落地为纯 Python 实现**（对齐 C2 全波次"复用 v1、可注入、测试不碰
网络/LLM/演示资产"哲学）：

1. **检索** = `LexicalRetriever`（idf 加权 token 重叠，BM25-lite）。中文 tokenize 产单字 +
   bigram。chunk 来源抽成 `ChunkSource` Protocol（`KGChunkSource` 读概念表 /
   `StaticChunkSource` 测试）——**未来换 ChromaDB/Qdrant 只换 ChunkSource，engine 不动（OCP）**。
2. **验证** = `AnswerValidator`，NLI 风格答案-引用源一致性。**LLM 法官可注入**（有就走主路径）；
   回退启发式**永不过度授信**（无源不支撑 / 置信封顶 0.6 / 法官挂自动降级不抛），沿用 FIX-L
   教训——回退路径绝不冒充高置信判定。
3. **重检索循环** = engine 内 ≤3 轮自主放宽召回（Agentic 体现），状态机
   IDLE→RETRIEVED→SCORED→VALIDATED/CANNOT_CONFIRM，与 MD-M-008 一致。

## 考虑的替代方案

| 方案 | 优点 | 缺点 |
|------|------|------|
| **词法检索 + 启发式验证 + 法官可注入**（采纳）| 零网络零模型；确定性可测；接口对齐设计状态机；ChunkSource/judge 注入点留好升级路 | 召回质量逊于向量；启发式验证粗 |
| 照设计装 ChromaDB + DeBERTa | 与 FF-M-008 字面一致 | 死代理下装不上/跑不动；CI 不可复现；当前规模过度工程 |
| 干脆不做验证，只检索 | 最省 | 丢掉 #9 AgenticRAG 的"反幻觉/可确认"内核 |

## 后果

- 正面：C3 即有可跑通、21 测试覆盖（含"永不过度授信"红线）的 RAG 闭环；升级到真向量后端
  只动 ChunkSource，judge 注入即接 LLM 验证；不被死代理阻塞。
- 负面：召回/验证精度是占位级；真向量后端与 NLI 模型留待规模化阶段（设计文档保留为目标态）。
- 守边界：新增 import-linter 契约 `backend.rag` 不反向依赖上层。

## 相关

- 设计：`doc/plan/v3.1-aitutor-design/06-framework/M-008/`（FF/engine.py 目标态）
- 实现：`backend/rag/`（C3 提交 88b8031）+ pyproject 第 6 契约
- 关联教训：FIX-L（判分回退永不授 correct）/ 持久记忆 dead-system-proxy-workaround
