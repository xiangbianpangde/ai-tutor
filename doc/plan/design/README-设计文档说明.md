# 设计文档索引

> 设计文档五段式：背景 / 目标 / 方案（含 Mermaid 图）/ 影响范围 / 风险
> 每个文档对应一个"涉及 3+ 模块"的复杂功能

| 文档 | 对应功能点 | 涉及模块 |
|------|-----------|---------|
| [设计文档-总体架构.md](设计文档-总体架构.md) | #1, #11 | 全部 |
| [设计文档-后端API层.md](设计文档-后端API层.md) | #2 | `backend/api/`, `backend/ws/`, `backend/engines/` |
| [设计文档-中间件层.md](设计文档-中间件层.md) | #3 | `backend/middleware/` |
| [设计文档-前端桌面应用.md](设计文档-前端桌面应用.md) | #4, #5 | `frontend/` |
| [设计文档-数据管线.md](设计文档-数据管线.md) | #6 | `backend/pipeline/` |
| [设计文档-research-tool集成.md](设计文档-research-tool集成.md) | #7 | `backend/engines/knowledge/`, `backend/rag/`, `backend/pipeline/` |
| [设计文档-pdf2zh集成.md](设计文档-pdf2zh集成.md) | #8 | `backend/pipeline/`, `backend/engines/knowledge/` |
| [设计文档-AgenticRAG.md](设计文档-AgenticRAG.md) | #9 | `backend/rag/` |
| [设计文档-教学策略升级.md](设计文档-教学策略升级.md) | #10 | `backend/engines/tutoring/` |
| [设计文档-打包发布.md](设计文档-打包发布.md) | #11 | 构建配置 |

## 外部项目引用

| 项目 | 路径 | 设计文档 |
|------|------|---------|
| research-tool | `C:/Users/yhn/Desktop/调研/research-tool/` | [设计文档-research-tool集成](设计文档-research-tool集成.md) |
| pdf2zh | `C:/Users/yhn/pdf2zh/` | [设计文档-pdf2zh集成](设计文档-pdf2zh集成.md) |
