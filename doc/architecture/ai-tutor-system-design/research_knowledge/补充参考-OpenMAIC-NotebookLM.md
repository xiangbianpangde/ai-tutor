# 补充参考：OpenMAIC & NotebookLM 调研

> 来源：2026-05-19 网络爬取 → 清洗 → 知识树构建
> 原始资料：`research_raw/` (9个文件) → `research_clean/`（清洗版）
> 知识树：`research_knowledge/00-主表.md`
> 用途：为 AI Tutor 设计提供外部参照系，标注可采纳、需适配、必须避免的设计要素

---

## 一、OpenMAIC（清华大学 THU-MAIC）

### 1.1 基本信息

| 维度 | 内容 | 来源 |
|------|------|------|
| 全称 | Open Multi-Agent Interactive Classroom | OW |
| 开发方 | 清华大学 THU-MAIC 团队 | OW, OM |
| 开源 | GitHub (AGPL-3.0) | OG |
| 技术栈 | Next.js + React + TypeScript + LangGraph | OW |
| 规模 | 17.7k stars, 3.4k forks | OG |
| 验证 | 700+ 学生，20M+ 访问，2年+ 迭代 | OW, OM |
| 学术论文 | JCST 2026: "From MOOC to MAIC" | OW, OM |

### 1.2 核心架构

**两阶段生成流水线**：

```
用户输入（主题/文档）
  → Stage 1: Plan Agent 生成 Outline
    （学习目标 + 课程结构 + 步骤流程）
  → Stage 2: 每个 Outline 项展开为 Scene
    （幻灯片 + 测验 + 交互模拟 + PBL 活动）
```

技术实现：
- 多智能体编排：LangGraph 状态机管理 Agent 轮次和协作
- 28+ 动作类型：语音、白板绘图、聚光灯、激光笔
- 支持 LLM：OpenAI / Anthropic / Gemini / DeepSeek / MiniMax / GLM / MiMo
- 推荐模型：Gemini 3 Flash（质量与速度平衡）
- PDF 解析：MinerU 引擎
- TTS：VoxCPM2（自托管语音克隆）

**Deep Interactive Mode（新增功能）**：五种交互 UI 类型——3D 可视化、模拟实验、游戏、思维导图、在线编程。AI 教师可主动操作 UI 引导学生。

### 1.3 多智能体交互模式

| 模式 | 描述 | 来源 |
|------|------|------|
| 课堂讨论 | Agent 主动发起主题讨论，学生随时加入或被点名 | OW |
| 圆桌辩论 | 多个持不同观点的 Agent 辩论，配合白板示意 | OW, OC |
| Q&A 模式 | 学生自由提问，AI 教师用幻灯片/图表/白板回答 | OW |
| PBL | 学生选择角色，与 AI Agent 协作完成结构化项目 | OW |
| 白板协作 | Agent 实时绘图——解方程、画流程图、写公式 | OW |

Agent 角色分工：Teacher（讲解+评估）、Student（提问+尝试）、Reviewer（批判+改进建议）、Moderator（管理讨论流程）

### 1.4 已验证的效果

清华大学对照实验（OM）：
- 三组对比：人类教授 vs AI 教师（MAIC）vs 传统 MOOC 视频
- 结果：**AI 教师在学习效果上显著优于其他两组**
- 含义：自适应、结构化、交互式交付可能优于静态视频学习

### 1.5 与 AI Tutor 的关系

| 维度 | OpenMAIC | AI Tutor |
|------|----------|----------|
| 课件生成 | ★★★★★（两阶段流水线，7种Scene类型） | ★★★（digest-mcp，原生7种格式） |
| 用户参与 | ★（Agent间讨论排除用户） | ★★★★★（PGFGA铁律1：话语权永远在学习者） |
| 知识获取 | ★（依赖用户输入主题/文档） | ★★★★★（L4：自动采集+融合+KG构建） |
| 教学策略 | ★（Plan Agent做简单规划） | ★★★★★（L6：6种策略原语+自适应选择） |
| 学习追踪 | ☆（无） | ★★★★★（L5：DKT+BKT+错误诊断+画像） |
| 复习记忆 | ☆（无） | ★★★★★（L3：个性化遗忘曲线+多因子调度） |

**可借鉴**：
- 两阶段流水线（Outline→Scenes）可融入 `digest()` 内部编排
- Deep Interactive Mode 的 5 种交互类型可丰富 digest-mcp 的 simulation 格式
- 多 Agent 协作模式可增强 digest-mcp 的 multi-agent 格式

**必须避免**：
- Agent 间讨论排除用户——这正是用户设计 AI Tutor 时明确反对的模式
- 无学习追踪——这是 OpenMAIC 作为"课件生成器"而非"认知教练"的根本局限

---

## 二、NotebookLM（Google Labs）

### 2.1 基本信息

| 维度 | 内容 | 来源 |
|------|------|------|
| 全称 | Google NotebookLM | NW |
| 发布 | 2023.05 (Project Tailwind) → 2024 更名 → 2024.10 去实验标签 | NW, NG |
| 定位 | AI 研究助手 + 思考伙伴 | NG |
| 底层模型 | Gemini 3 (Pro + Flash) + Nano Banana Pro (图像) | NL, NW |
| 付费版 | NotebookLM Plus (Google One AI Premium) | NW |

### 2.2 核心技术：Source-Grounded RAG

NotebookLM 的核心差异：**所有 AI 回答严格锚定在用户上传的文档上**。

```
标准 LLM: 基于训练数据预测下一个词 → 可能幻觉
NotebookLM: 基于用户文档检索 + 生成 → 内联引用 + 原文出处
```

技术参数（NL）：
- 上下文窗口：每个 Notebook 最多 600 个来源
- 每来源上限：500,000 词
- 支持格式：PDF、Google Docs、网页、YouTube（通过转录）、Google Slides

**关键安全设计**（NG）：
- 模型只能访问用户上传的源材料
- 用户文件和对话对其他用户不可见
- 不上传数据用于训练新 AI 模型

### 2.3 Studio 多格式输出

NotebookLM 的 Studio 面板将同一批源材料转化为多种格式：

| 格式 | 描述 | 来源 |
|------|------|------|
| Audio Overviews | 两个 AI 主持人围绕源材料展开的 podcast 式深度对话 | NA, NL |
| Video Overviews | AI 生成的旁白幻灯片视频 | NL, NW |
| 思维导图 | 从散落事实中提取概念连接 | NL |
| 数据表格 | 结构化提取，可导出 Google Sheets | NL |
| 信息图 + 幻灯片 | Nano Banana Pro 图像生成 | NL, NW |
| 闪卡 | 概念记忆卡片 | NW |
| Deep Research | AI 自主制定研究计划、浏览数百网站、生成引用报告 | NL |

### 2.4 Audio Overviews 深度分析

这是 NotebookLM 最具标志性的功能（NA, NL）：

**基础模式**：两个 AI 主持人自动生成一段关于源材料的对话——总结、建立连接、轻松闲聊

**交互模式（2024.12 更新）**：用户可以"加入"对话——打断 AI 主持人、提问、引导对话方向

**关键特性与限制**（NA）：
- 生成时间：大型 Notebook 需要数分钟
- 语言限制：初期仅英语（后扩展至 80+ 语言）
- 非客观全面：对话反映的是上传源材料的视角，非客观综述
- 偶有不准确
- **重要限制**（NL）：逻辑/数学/化学科目表现弱——"不是基础理解的替代品"

**与 AI Tutor 的关联**：Audio Overviews 的"双人对话式讲解"可以直接启发 digest-mcp 的 audio 格式——从单人朗读升级为双人讨论。交互式打断模式与我们的 `interrupt()` tool 目标一致。

### 2.5 已知局限

| 局限 | 描述 | 来源 |
|------|------|------|
| 逻辑/数学弱 | 在化学、复杂数学证明等逻辑学科上表现不佳 | NL |
| "合成亲密感" | Audio Overviews 的主持人默认呈现"美国中产白人口音"，可能抹平文化差异 | NL |
| 非基础理解替代 | "补充工具，不是基础理解的替代品" | NL |
| 不支持教学策略 | 无学习路径规划、无知识掌握检测、无复习调度 | 推断 |
| 用户数据隔离 | 跨 Notebook 不共享上下文 | 推断 |

### 2.6 与 AI Tutor 的关系

| 维度 | NotebookLM | AI Tutor |
|------|-----------|----------|
| 源锚定 | ★★★★★（RAG + 内联引用） | ★★★（KG 有 source 字段但引用不显式） |
| 多格式输出 | ★★★★★（Studio：7种格式） | ★★★★（digest-mcp：7种格式） |
| 知识采集 | ★★（Deep Research Agent） | ★★★★★（L4：全自动采集+融合） |
| 教学策略 | ☆（无） | ★★★★★（L6） |
| 学习追踪 | ☆（无） | ★★★★★（L5） |
| 数据隐私 | ★★★★★（不上传训练数据） | 待设计 |
| 数学/逻辑准确性 | ★★（弱） | 待验证（高数场景是核心） |

**可借鉴**：
- Source-Grounded 设计：KG 的 source 字段应升级为内联引用模式
- Audio Overviews → digest-mcp audio 格式：从单人 TTS 升级为双人讨论
- Deep Research Agent 的计划-浏览-报告模式 → acquire_subject 的 web_collect 增强

**必须警惕**：
- NotebookLM 在数学/逻辑上弱——而我们的核心场景是高数。必须在 L4 KG 质量门中加强数学语义验证
- "合成亲密感"警示——PGFGA 的非评判防火墙要避免"虚假温暖"

---

## 三、三个系统的能力矩阵

```
                        OpenMAIC    NotebookLM    AI Tutor
                        ────────    ──────────    ────────
  自动知识采集              ✗            △            ✓
  源锚定/减少幻觉           ✗            ✓            △(待加强)
  知识图谱                  ✗            △(脑图)       ✓
  课件自动生成              ✓            ✓            ✓
  多智能体交互              ✓            ✗            △(multi-agent格式)
  个性化教学策略            ✗            ✗            ✓
  学习者认知建模            ✗            ✗            ✓
  心流/动机维持             ✗            ✗            ✓(PGFGA集成后)
  长期记忆/复习调度         ✗            ✗            ✓
  数据隐私保护              -            ✓            待设计
  用户全程参与话语权        △(可插话)     ✓(交互模式)    ✓(铁律1)
  数学/逻辑准确性           -            ✗            待验证
  48h系统学习               ✗            ✗            ✓(声称)
```

---

## 四、可操作建议

### 4.1 直接采纳（不改变架构）

| 建议 | 影响范围 | 工作量 |
|------|---------|--------|
| KG 概念节点的 source 字段升级为内联引用（仿 NotebookLM） | L4 Concept.sources | 0.5 天 |
| digest-mcp audio 格式参考 Audio Overviews 双人对话 | digest-mcp audio.py | 1 天 |
| digest-mcp multi-agent 格式借鉴 OpenMAIC 的角色分工 | digest-mcp multi_agent.py | 0.5 天 |

### 4.2 需要适配（轻量架构调整）

| 建议 | 说明 |
|------|------|
| acquire_subject 的 web_collect 借鉴 Deep Research Agent 的计划-浏览-报告模式 | 增加 research_plan 步骤，输出结构化采集报告 |
| digest() 内部编排借鉴两阶段流水线（Outline→Scenes） | 已经有关联逻辑，形式化即可 |

### 4.3 必须避免

| 陷阱 | 说明 |
|------|------|
| Agent 间讨论排除用户（OpenMAIC 核心缺陷） | PGFGA 铁律1 已解决 |
| 虚假"合成亲密感"（NotebookLM 的文化抹平） | PGFGA 同频共振对齐应覆盖 |
| 数学/逻辑不可靠（NotebookLM 已知局限） | 在 L4 Quality Gate 中增加数学语义验证规则 |
| 无学习追踪（两者共有局限） | L5 已覆盖 |

---

## 五、来源追溯表

| 引用标记 | 原始文件 | 原始 URL |
|---------|---------|----------|
| OW | research_clean/openmaic_website.md | https://openmaic.io/ |
| OG | research_clean/openmaic_github.md | https://github.com/THU-MAIC/OpenMAIC |
| OM | research_clean/openmaic_medium.md | https://medium.com/@zoudong376/... |
| OC | research_clean/openmaic_clawblog.md | https://claw4science.org/blog/... |
| NW | research_clean/notebooklm_wikipedia.md | https://en.wikipedia.org/wiki/NotebookLM |
| NL | research_clean/notebooklm_linkedin_arch.md | https://www.linkedin.com/pulse/... |
| NG | research_clean/notebooklm_google_blog.md | https://blog.google/.../notebooklm-google-ai/ |
| NA | research_clean/notebooklm_audio_blog.md | https://blog.google/.../notebooklm-audio-overviews/ |
| NS | research_clean/notebooklm_support_audio.md | https://support.google.com/notebooklm/... |

---

> **产出状态**：阶段5 最终交付 | **知识树**：research_knowledge/00-主表.md | **下一版本**：待用户审查后加入 `specs/` 目录
