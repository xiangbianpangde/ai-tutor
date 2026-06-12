# AI-Tutor — 项目文件图谱

> **新文件放哪？先查这个决策树。**
> 每次新增/移动文件后更新本文件。

## 决策树

```
新文件是什么类型？
│
├── 计划文档（背景/清单/设计）
│   └── doc/plan/
│       ├── 背景.md              项目背景与设计决策
│       ├── 开发清单.md           功能点列表 + 依赖关系
│       └── design/              涉及 3+ 模块的复杂功能五段设计文档
│
├── BDD 规格
│   └── doc/specs/
│
├── 规范/约定
│   ├── conventions/             本项目的开发规范（可引用外部 开发规范/）
│   └── DEVELOPMENT-NORM.md      文件增长控制原则
│
├── 工作日志
│   └── worklogs/
│       ├── YYYY-MM-DD_描述.md   每次功能点开发的工作日志
│       └── decisions/           ADR（仅收束节点产出）
│
├── 汇报
│   └── doc/reports/             收束报告 / 阶段汇报（仅收束节点或人要求时落盘）
│
├── 调研
│   └── doc/research/            调研资料与调研报告
│
├── 模板
│   └── doc/templates/           文档模板（复制起步，不手搓）
│
├── 源代码
│   ├── shared/                  L1 基础设施（跨引擎共用）
│   ├── servers/                 4 个 MCP server（v1）
│   │   ├── knowledge_mcp/       L4 知识工程
│   │   ├── tutoring_mcp/        L2/L3/L5/L6 教学
│   │   ├── digest_mcp/          多模态产物
│   │   └── sync_mcp/            Obsidian+git
│   └── scripts/                 tutor_cli.py（统一 CLI 入口）+ demo 脚本
│
├── 测试
│   ├── tests/                   跨 server 测试
│   └── BDD/                     BDD 行为测试
│
├── 构建/打包配置
│   ├── pyproject.toml
│   └── pyinstaller.spec         打包配置（v2 阶段）
│
├── AI 上下文
│   └── CLAUDE.md                新会话自动加载（AI 读）
│
├── 人类入口
│   └── README.md                项目使用指南（人读）
│
└── 状态追踪
    └── STATUS.md                进度 + 收束节点 + 技术债
```

## 当前文件归类

| 目录 | 文件数 | 说明 |
|------|--------|------|
| `shared/` | ~14 | L1 基础设施 |
| `servers/knowledge_mcp/` | ~19 | L4 知识工程 |
| `servers/tutoring_mcp/` | ~27 | L2/L3/L5/L6 教学 |
| `servers/digest_mcp/` | ~11 | 多模态产物 |
| `servers/sync_mcp/` | ~6 | Obsidian+git |
| `servers/dashboard/` | ~5 | 状态面板（v2 被前端替代） |
| `scripts/` | ~14 | `tutor_cli.py` 统一 CLI（采集→建图→质检→产物→教学，免写脚本）+ demo |
| `tests/` | ~10 | 跨 server 测试 |
| `doc/` | ~16 | 文档（旧） |
| `doc/plan/` | 11 | v2 重构计划 |
| `doc/plan/v3.1-aitutor-design/` | ~120 | v3.1 设计包（plan-writing 工作流产出，2026-06-02 交付） |
| `doc/research/v3.1-aitutor-research/` | 16 | v3.1 调研报告（18 个 research-tool run / 57 S/A 级来源） |
| `doc/reports/v3.1-aitutor-simulation/` | 6 | v3.1 系统模拟运行报告（端到端 15 拍 + 闭环判定） |
| `doc/specs/` | 9 | BDD 规格 |
| `doc/templates/` | 2 | 文档模板 |
| `worklogs/` | 2 | 工作日志（v3.1 设计交付 worklog 2026-06-02） |

## 禁止事项

- ❌ 根目录堆散文件（计划/日志/汇报一律入对应子目录）
- ❌ 重复文件（同一主题只在一处权威，其余引用）
- ❌ UUID 目录名（文件路径必须人类可读）
