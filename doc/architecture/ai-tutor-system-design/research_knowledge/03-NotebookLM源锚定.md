# 分表3：NotebookLM 源锚定架构

> 核心问题：什么是 Source-Grounded AI？它的 Studio 如何工作？

---

## S1 原始资料依据

**NL (notebooklm_linkedin_arch.md)**:
- "NotebookLM functions as a Source-Grounded AI. It uses Retrieval-Augmented Generation (RAG) to anchor every response to specific documents, audio files, and web resources you upload, significantly reducing hallucinations"
- "inline citations for verification"
- "context window: up to 600 sources per notebook, each source containing up to 500,000 words"
- "Gemini 3 Pro & Flash Integration"

**NG (notebooklm_google_blog.md)**:
- "NotebookLM: an AI notebook for everyone. Think of it as a virtual research assistant that can summarize facts, explain complex ideas, and brainstorm new connections — all based on the sources you select"
- "NotebookLM's source-grounding does seem to reduce the risk of model hallucinations"
- "We've built NotebookLM such that the model only has access to the source material that you've chosen to upload"

**NW (notebooklm_wikipedia.md)**:
- "an online research and note-taking retrieval-augmented generation tool"
- "Known for its Audio Overviews feature, which generates podcast-like discussions"

**NL (notebooklm_linkedin_arch.md) — Studio section**:
- "Studio panel that transforms raw data into different media formats"
- "Audio Overviews: banter-filled deep-dive conversation between two AI hosts"
- "Video Overviews: narrated slideshows leveraging Nano Banana"
- "Deep Research Agents: automates the information-gathering phase — creates a research plan, browses hundreds of websites, compiles a comprehensive cited report"
- "Data Tables & Mind Maps: extract scattered facts or generate branching mind maps"

---

## S2 核心观点提炼

1. **Source-Grounded RAG 是 NotebookLM 的核心差异**。所有回答锚定在用户文档上，带内联引用——这是对标准 LLM "自由发挥+幻觉"问题的硬约束。AI Tutor 的 KG 已有 source 字段，但缺少"内联引用"的显式设计。

2. **"Deep Research Agent" 是 acquire_subject 的互补参考**。NotebookLM 的 Agent 做"计划→浏览→报告"三步，与 AI Tutor 的 web_collect 同构但更结构化。可以借鉴其"research plan→multi-source browse→cited report"模式升级 web_collect。

3. **数据隐私设计值得学习**。"模型只能访问用户上传的源材料、数据不用于训练"——AI Tutor 的 L1 存储设计应该显式声明这一点。

4. **上下文窗口规模惊人**。600 来源 × 500K 词 = 3 亿词上下文——这为 AI Tutor 的 KG 构建提供了理想目标（虽然我们做不到这个规模，但方向一致）。

---

## S3 与其他节点的关系

| 关联节点 | 关系 | 说明 |
|---------|------|------|
| 节点4 (交互与学习体验) | 互补 | Studio 是"产出"，交互模式是"消费"——两者配合 |
| 节点5 (AI Tutor差异化) | 对比 | 源锚定是 NotebookLM 的强项，AI Tutor 的 KG source 字段需加强 |
| 节点6 (可采纳清单) | 来源 | "内联引用""Deep Research 模式"的直接来源 |

---

## S4 在主线中的位置

```
主线: NotebookLM源锚定架构 → 交互体验 → AI Tutor差异化定位 → 可采纳清单

本节点回答: "它如何保证信息准确性？" — 定义了 NotebookLM 的核心竞争力。
对 AI Tutor 的启示：KG 不仅是"概念关系图"，还应是"可追溯的知识来源网"。
```
