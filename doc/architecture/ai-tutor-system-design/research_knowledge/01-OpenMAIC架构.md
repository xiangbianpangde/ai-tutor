# 分表1：OpenMAIC 架构全景

> 核心问题：它的技术架构、生成流水线、多智能体编排是怎样的？

---

## S1 原始资料依据

**OW (openmaic_website.md)**:
- "OpenMAIC is built on a modern web stack centered around Next.js, React, and TypeScript"
- "multi-agent orchestration layer is powered by LangGraph, which manages a state machine governing agent turns"
- "two-stage generation pipeline: Stage 1 analyzes user input and produces a structured lesson outline. Stage 2 transforms each outline item into rich multimedia scenes"
- "28+ action types — speech, whiteboard drawing, spotlight effects, laser pointer"
- "supports OpenAI, Anthropic, Google Gemini, DeepSeek"
- "Deep Interactive Mode: 3D Visualization, Simulation, Game, Mind Map, Online Programming"

**OG (openmaic_github.md)**:
- "Stage: Outline → AI analyzes input and generates structured lesson outline"
- "Stage: Scenes → Each outline item becomes a rich scene"
- "Classroom Components: Slides, Quiz, Interactive Simulation, Project-Based Learning (PBL)"
- "Multi-Agent Interaction: Classroom Discussion, Roundtable Debate, Q&A Mode, Whiteboard"

**OM (openmaic_medium.md)**:
- "Plan Agent generates learning objectives, curriculum structure, step-by-step lesson flow"
- "Using LangGraph, OpenMAIC orchestrates multiple agents in collaborative settings"
- "Evolution: 2024(LLM+RAG) → 2025(Agents+code generation) → 2026(Autonomous agents)"

---

## S2 核心观点提炼

1. **两阶段流水线是可复用的课件生成模式**：Outline→Scenes 的分层设计与 AI Tutor 的 L6 教学路径规划 + digest-mcp 课件生成是同构的。

2. **LangGraph 状态机是成熟的多智能体编排方案**：已有 28+ 种动作类型、4 种角色（Teacher/Student/Reviewer/Moderator），直接验证了"状态机驱动多 Agent 协作"的可行性。

3. **Deep Interactive Mode 扩展了"课件"的定义**：不仅是幻灯片和测验，还包括 3D 可视化、模拟实验、游戏——这对 AI Tutor 的 digest-mcp simulation 格式有直接启发。

4. **技术栈验证**：Next.js+TypeScript+LangGraph 的组合已被 700+ 学生、20M+ 访问验证，证明 LLM+状态机+前端渲染的教育架构是可行的。

---

## S3 与其他节点的关系

| 关联节点 | 关系 | 说明 |
|---------|------|------|
| 节点2 (用户参与局限) | 互补 | 架构强但用户参与弱——OpenMAIC 解决了"怎么教"但没解决"教谁" |
| 节点5 (AI Tutor差异化) | 对比 | AI Tutor 的 L4(知识采集)+L5(学习者建模) 是 OpenMAIC 缺失的 |
| 节点6 (可采纳清单) | 来源 | 两阶段流水线→digest()内部编排；Deep Interactive→simulation格式 |

---

## S4 在主线中的位置

```
主线: OpenMAIC架构能力 → 用户参与局限 → AI Tutor差异化定位 → 可采纳清单

本节点回答: "它有什么能力？" — 是整条分析链的起点。
若没有这个节点的信息，就无法判断哪些能力是独特的、哪些是可以借鉴的。
```
