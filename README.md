# AI-Tutor

<div align="center">

### 48 小时学完一科的自适应 AI 私人辅导系统
**基于 L1~L7 七层认知架构 · 刚性知识图谱防幻觉 · PGFGA 心流自适应 · BKT 掌握度追踪 · FSRS-5 间隔重复**

[![Tests](https://img.shields.io/badge/tests-973%20passed%20(100%25)-success?style=flat-square)](./tests/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue?style=flat-square)](./pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-teal?style=flat-square)](./backend/)
[![React](https://img.shields.io/badge/React%20%7C%20Vite%20%7C%20Electron-18.x-61dafb?style=flat-square)](./frontend/)
[![MCP](https://img.shields.io/badge/MCP-4%20Servers%20%7C%2032%20Tools-orange?style=flat-square)](./servers/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](./README.md)

[产品特性](#-产品特性) • [七层认知架构](#-七层认知架构) • [四大硬核算法](#-四大核心创新点与算法) • [快速开始](#-快速开始) • [工程目录](#-工程目录结构) • [竞赛与团队任务](#-竞赛与团队任务包)

</div>

---

## 💡 为什么需要 AI-Tutor？

通用大语言模型（如 ChatGPT、Kimi、Claude）直接充当辅导老师时，普遍存在三大致命痛点：
1. **被动应答，缺乏教学目标感知**：大模型本质是“文本概率续写器”，学生不问就不教，学生盲目提问容易陷入“认知过载”与知识迷航。
2. **幻觉无法根除，缺乏事实锚点**：教育场景对正确性要求极高，传统 Prompt 方案无法彻底杜绝模型自由发挥捏造逻辑。
3. **缺乏状态记忆与情感调优**：没有数学模型量化学生到底“有没有掌握”，且打分生硬刻板，容易引发学生的挫败与焦虑。

**AI-Tutor 不是一个简单的套壳聊天机器人，而是一套完整的“认知操作系统”**。它将教材资料转化为刚性知识图谱，结合贝叶斯知识追踪、降阶学习法与心流调节，为学习者打造闭环、自适应的 48 小时极速过科体验。

---

## ✨ 产品特性

* 🗺️ **资料一键建图（L4 知识工程）**：支持 PDF、Markdown、网页文本输入，通过纯规则/LLM 混合管道自动化抽取概念骨架与拓扑前置关系，内置 NoiseGate 确保概念噪声率 `< 5%`。
* 🎯 **逆向主动教学（L6 教学引擎）**：基于布鲁姆认知模型与“降阶学习法”，系统主动发起摸底探测、概念讲解、针对性提问、反向攻击防御与阶段自适应校准。
* 🌊 **PGFGA 心理学心流回路（L5 学习者建模）**：实时捕获学生迟疑、退缩、冗长等 10 维心流信号；独创非评判防火墙（NonJudgmentFirewall），动态调优教学难度与节奏。
* 📈 **BKT 掌握度与 FSRS-5 调度（L3 长期记忆）**：基于贝叶斯知识追踪（BKT）量化知识掌握概率；采用第五代自由间隔重复算法（FSRS-5）排定最佳复习周期。
* 🧩 **多模态复习产物与双向同步（横切能力）**：一键生成 7 种复习产物（思维导图、针对性测验、互动闪卡、幻灯片简报、三角色对话等），支持无缝写回 Obsidian 与 Git 版本化沉淀。
* 🖥️ **现代暖纸风交互系统（L7 交互层）**：基于 Electron + React (Vite) 打造的桌面客户端，内建 D3 力导向知识图谱、认知负荷热力图与系统全状态监控。

---

## 🏛️ 七层认知架构

系统自底向上严格按照七层认知科学体系解耦实现：

```
┌────────────────────────────────────────────────────────────────────────┐
│ L7 交互层 (Interaction)     : React / Electron 暖纸风客户端, D3 图谱可视化   │
├────────────────────────────────────────────────────────────────────────┤
│ L6 教学引擎 (Teaching)       : 自适应策略状态机, 降阶学习法, 拓扑排程, 防火墙    │
├────────────────────────────────────────────────────────────────────────┤
│ L5 学习者建模 (Learner)      : BKT 掌握度追踪, 10维 PGFGA 心流增益反馈回路    │
├────────────────────────────────────────────────────────────────────────┤
│ L4 知识工程 (Knowledge)      : 资料采集, KG 抽取富化, 版本树(base_id), 冲突消解 │
├────────────────────────────────────────────────────────────────────────┤
│ L3 长期记忆 (Long-Term)      : FSRS-5 间隔重复, 遗忘曲线拟合, 知识点长效事实库    │
├────────────────────────────────────────────────────────────────────────┤
│ L2 短期记忆 (Working)        : 会话上下文 (SessionContext), 断点保存与打断恢复 │
├────────────────────────────────────────────────────────────────────────┤
│ L1 基础设施 (Infrastructure) : FastAPI 统一网关, 任务线程池, 事件总线, 本地SQLite│
└────────────────────────────────────────────────────────────────────────┘
  ▲                                                                    ▲
  │   横切服务 (MCP Server 协议解耦):                                   │
  ├── servers/knowledge_mcp/  (9 Tools : acquire, build, query, review...)│
  ├── servers/tutoring_mcp/   (12 Tools: cold_start, respond, inspect...)│
  ├── servers/digest_mcp/     (4 Tools : mindmap, quiz, slides, cards...) │
  └── servers/sync_mcp/       (6 Tools : obsidian_push, git_sync...)     │
```

---

## 🔬 四大核心创新点与算法

### 1. 降阶学习法：逻辑降维与补集证伪
高阶复杂知识往往由于维度交织导致认知超载。系统将复合概念拆解为不可再分的原子逻辑链（前提 $\rightarrow$ 推理 $\rightarrow$ 结论 $\rightarrow$ 边界）；同时运用**补集思维**，主动列出所有常见误区并逐一证伪，实现真理收敛。详见 [`doc/降阶学习法.md`](./doc/降阶学习法.md)。

### 2. PGFGA 心流自适应调节与非评判防火墙
基于积极心理学挑战-技能平衡模型，系统通过 `flow_signals.py` 动态捕获迟疑用词、作答长度衰减、求助频次等 10 维信号，划分 5 档心流等级；判分经由 `NonJudgmentFirewall` 过滤，彻底摒弃冷冰冰的负面评判，始终维持学习者的求知信心。详见 [`doc/PGFGA-TUNING.md`](./doc/PGFGA-TUNING.md)。

### 3. 刚性图谱约束与 Agentic RAG
以抽取校验后的概念图谱作为刚性教学大纲，大模型回答时必须挂靠已知节点，偏离即触发自主重检索（最多 3 轮）与 NLI 级答案-引用源一致性验证，从架构物理底层切断模型幻觉。

### 4. BKT 数理掌握度与 FSRS-5 记忆曲线
每个概念由 BKT（先验、猜度、失误、转移概率）数学模型动态维护掌握度 $P(L)$；学完后自动接入 FSRS-5（稳定性、难度双参数）矩阵算法，精准预测遗忘临界点并自动排布进今日复习队列。

---

## 🚀 快速开始

系统采用本地优先（Local-first）设计，支持跨平台（Windows / macOS / Linux）秒级启动。

### 1. 环境准备
* **Python**: `>= 3.11`（推荐使用极速包管理器 [uv](https://github.com/astral-sh/uv)）
* **Node.js**: `>= 18.0`（用于前端界面）

### 2. 安装与配置

```bash
# 1. 克隆本仓库
git clone https://github.com/xiangbianpangde/ai-tutor.git
cd ai-tutor

# 2. 安装 Python 核心与开发依赖
uv sync --extra dev

# 3. 配置环境变量（支持本地启发式降级，无 Key 也能平稳运行）
cp .env.example .env
# 编辑 .env 填入你的大模型提供商 API Key（如 DEEPSEEK_API_KEY）
```

### 3. 一键启动服务

* **启动后端统一服务**（FastAPI，监听 `127.0.0.1:18501`）：
  ```bash
  uv run python run_aitutor.py
  # 打开浏览器访问交互式 API 文档：http://127.0.0.1:18501/docs
  ```

* **启动前端 Web 客户端**（React + Vite，监听 `http://localhost:5173`）：
  ```bash
  cd frontend/renderer
  npm install
  npm run dev
  ```

* **运行全量自动化测试**（验证环境完整性）：
  ```bash
  uv run pytest
  # 预期结果：973 passed, 1 skipped，100% 通过
  ```

---

## 📂 工程目录结构

```
ai-tutor/
├── backend/                  # FastAPI 统一网关与现代后端服务
│   ├── app.py                # 应用装配工厂 (CORS, 中间件, 统一信封)
│   ├── main.py               # Uvicorn 启动入口
│   ├── routers/              # REST & WebSocket 路由端点 (knowledge, tutoring, digest, sync...)
│   ├── rag/                  # Agentic RAG 检索器与一致性校验器
│   ├── strategy/             # BKT, FSRS-5, 阶段校准与费曼判分算法
│   └── middleware/           # TaskManager 任务池, EventBus 事件总线, 缓存与文件管理
│
├── frontend/                 # 桌面与 Web 客户端
│   ├── main.js / preload.js  # Electron 宿主入口与最小安全沙箱桥接
│   └── renderer/             # React 18 + Vite 5 渲染层 (10 个路由页面, D3 力导向图组件)
│
├── servers/                  # 4 个标准化 MCP Server (可独立通过 Claude Desktop 驱动)
│   ├── knowledge_mcp/        # L4 知识工程 (9 Tools)
│   ├── tutoring_mcp/         # L2/L3/L5/L6 教学状态机 (12 Tools)
│   ├── digest_mcp/           # 多模态复习产物生成器 (4 Tools / 7 Formats)
│   └── sync_mcp/             # Obsidian 与 Git 双向工作流同步 (6 Tools)
│
├── shared/                   # L1 基础设施与数据模型
│   ├── models.py             # SQLAlchemy 14 张核心 ORM 数据表定义
│   ├── schemas.py            # Pydantic 核心数据契约与校验
│   ├── storage.py            # SQLite 与文件存储适配器
│   └── errors.py             # 统一 TutorError 与人话错误码映射
│
├── doc/                      # 项目设计与参考文档库
│   ├── tasks/                # 竞赛冲刺 4 人团队独立任务手册与学习计划
│   ├── architecture/         # L1~L7 原始系统设计与详细规范包
│   ├── worklogs/             # 历史研发日志与架构决策记录 (ADR)
│   ├── 降阶学习法.md          # 核心教育学理论推导
│   └── PGFGA-TUNING.md       # 心流回路与判定防火墙调参手册
│
├── tests/ & BDD/             # 单元测试、集成测试与 BDD 业务全链路验收套件
├── archive/                  # 历史模板与草稿归档目录
├── run_aitutor.py            # 生产级顶层启动入口
└── pyproject.toml            # 项目工程元数据与依赖锁定
```

---

## 🏆 竞赛与团队任务包

针对大学生创新创业与 AI 应用类竞赛（如“互联网+”、挑战杯、大学生计算机设计大赛等），团队已完成标准化职责拆解与 2 周极速新手实训计划。详情请查阅对应手册：

* 📘 [**00_项目总控与队长手册.md**](./doc/tasks/00_项目总控与队长手册.md)：全局里程碑甘特图、API 契约守门准则、Git 分支安全网与现场断网防翻车指南。
* 🎨 [**01_前端任务包_Web会话与MCP卡片.md**](./doc/tasks/01_前端任务包_Web会话与MCP卡片.md)：会话式 UI 改造、4 类 MCP 智能卡片组件、新手 2 周 React 临摹计划。
* ⚙️ [**02_后端任务包_接口桥接与演示保障.md**](./doc/tasks/02_后端任务包_接口桥接与演示保障.md)：`digest`/`sync` 路由补齐、本地演示 Mock 兜底机制、FastAPI 端点自测指南。
* 📊 [**03_测试评估任务包_双轨实验与数据图表.md**](./doc/tasks/03_测试评估任务包_双轨实验与数据图表.md)：3 门学科 Benchmark、抗作弊判分鲁棒性实验、SUS 可用性问卷量表与高清图表输出。
* 📝 [**04_竞赛写手任务包_四件套与答辩剧本.md**](./doc/tasks/04_竞赛写手任务包_四件套与答辩剧本.md)：15页立项主报告、8分钟路演 PPT 黄金节奏、3分钟现场 Demo 剧本与 10 大评委尖锐提问攻防表。

---

## 📄 开源许可证

本项目基于 [MIT License](./README.md) 协议开源。
欢迎学术交流、科研实验与教育创新竞赛引用！
