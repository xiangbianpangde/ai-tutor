# 状态面板 — 设计规格

> 状态：✅ 已实现（Slice DASH，2026-05-24）— `servers/dashboard/`（state.py + server.py + templates/index.html）。
>        技术选型从 FastAPI 改为 **Starlette + uvicorn**（二者由 fastmcp 传递引入，零新依赖；FastAPI 未装）。
>        启动 `uv run python -m servers.dashboard.server` → http://localhost:8501（DASHBOARD_PORT 可改）。
>        139 概念真实 KG 上 live 验证通过。
>
> 目标：一个与系统共生的实时状态面板，不是一次性演示工具
> 定位：系统自己的"仪表盘"，教学会话中持续展示内部状态
> 原则：只读数据库、不修改生产代码、可独立启停

---

## 1. 与 demo 仪表盘的差异

| 维度 | demo-plan.md 的演示仪表盘 | 本设计的状态面板 |
|------|--------------------------|---------------|
| 目的 | 给教育专家作一次性演示 | 系统自身的常驻组件 |
| 生命周期 | 一次会议后就丢掉 | 系统启动后持续运行 |
| 数据展示 | 事后查数据库 | 实时反映当前教学状态 |
| 部署 | 手动启动 Streamlit | 与 MCP server 一同或独立启动 |
| 技术 | Streamlit 脚本 | FastAPI + 纯 HTML |

---

## 2. 架构

```
┌────────────┐     同一 SQLite      ┌──────────────┐
│  4 个 MCP  │    data/tutor.db     │  状态面板     │
│  server    │ ◄─────────────────► │  (浏览器)     │
│  (stdio)   │                      │  localhost     │
└────────────┘                      └──────────────┘
```

状态面板是一个**独立的只读 Web 视图**，与 4 个 MCP server 共享同一份 SQLite 数据库。不参与教学逻辑、不调用 MCP tool。

### 为什么是独立服务而非 MCP server

- MCP 协议适合工具调用（输入→输出），不适合持续展示
- 状态面板需要浏览器渲染，天然是 HTTP 服务
- 独立进程意味着崩溃不影响教学，反之亦然

---

## 3. 面板结构

单页 4 区域布局，不用 Tab 切换：

```
┌─────────────────────────────────────────────────────────┐
│  📊 ai-tutor 教学状态                     [刷新] [3s]   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │ 概念      │ │ 心流      │ │ 策略      │                │
│  │ 全微分    │ │ 🟢 FLUENT│ │ 降阶法    │                │
│  │ 0.78     │ │ 净分 +3  │ │ REDUCE 3/5│               │
│  └──────────┘ └──────────┘ └──────────┘                │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  降阶法步骤                                        │   │
│  │  🎯GOAL ✅ → 🔍REDUCE(3/5) ●  → ❌COMPLEMENT    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────┐  ┌──────────────────────────────┐     │
│  │ 掌握度       │  │ 最近交互                      │     │
│  │ ■■■■■■■■ 8  │  │ ✅ 原子2: 路径趋近            │     │
│  │ ■■■■■■   4  │  │ ✅ 原子1: 一元vs多元         │     │
│  │ 绿=已掌握   │  │ 🟡 GOAL 确认                 │     │
│  └─────────────┘  └──────────────────────────────┘     │
│                                                          │
│  48h 进度  Phase 2/5  ████████░░░░░░░░  65%            │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 四个区域

| 区域 | 数据源 | 刷新 | 说明 |
|------|--------|------|------|
| **顶部指标卡** | `sessions.context_json` | 每轮 respond | 当前概念/mastery/心流/策略——最重要的 4 个数 |
| **降阶法步骤条** | `current_strategy_state` | 每轮 respond | 4 步走到了哪，当前步高亮 |
| **掌握度分布 + 最近交互** | `bkt_params` + `recent_history` | 3s 轮询 | 绿/黄/红柱 + 最近 10 轮 |
| **48h 进度条** | `learning_plans` + BKT | 10s 轮询 | Phase 完成度 |

### 可展开详情

点击任何区域弹出详情面板：
- **掌握度** → 所有概念完整 BKT 表
- **心流** → 最近 20 轮心流折线 + 10 信号明细
- **最近交互** → 最近 30 轮完整对话
- **进度** → 5 Phase 各自进度 + 到期复习列表

---

## 4. 数据流

### 4.1 读取方式

```python
def get_dashboard_state():
    sessions = load_latest_session()
    if not sessions:
        return {"status": "idle"}
    
    ctx = sessions[0].context_json
    bkt = load_bkt_summary(ctx["user_id"])
    
    return {
        "current_concept": ctx.get("current_concept_id"),
        "mastery": bkt.get(ctx.get("current_concept_id", ""), 0),
        "flow_level": ctx["recent_history"][-1].get("flow_level"),
        "strategy": ctx.get("current_strategy"),
        "strategy_state": ctx.get("current_strategy_state"),
        "total_mastered": sum(1 for m in bkt.values() if m > 0.85),
        "total_learning": sum(1 for m in bkt.values() if 0.4 < m <= 0.85),
        "total_weak": sum(1 for m in bkt.values() if m <= 0.4),
        "recent_history": ctx["recent_history"][-10:],
        "plan_progress": compute_plan_progress(ctx),
    }
```

### 4.2 更新触发

| 方式 | 场景 |
|------|------|
| 3 秒轮询（默认） | 常规（3 次轻量 SQL 查询） |
| 手动刷新 | 即时查看 |
| SSE 推送（可选） | 将来升级实时 |

---

## 5. 技术选型

| 方案 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **FastAPI + 纯 HTML** | 零前端依赖、与 Python 统一、可独立部署 | 手写 HTML/CSS | ★ 首选 |
| Streamlit | 快速搭 | 依赖重、难常驻 | 保留给快速原型 |

### 推荐实现

```
servers/dashboard/
  server.py             # FastAPI + uvicorn
  templates/
    index.html          # 单文件 ~400 行（内联 CSS + fetch 轮询）
```

- 单文件 HTML，内联 CSS 和 JS，零前端构建工具
- `uv run python -m servers.dashboard.server` 启动
- 访问 `http://localhost:8501`

---

## 6. 与教学流程的对应

| 教学阶段 | 面板显示 |
|---------|---------|
| KG 构建中 | "正在构建知识图谱… 45/139 概念" |
| 冷启动摸底 | "摸底进行中… 第 5/10 题" |
| 教学循环 | 顶部指标卡 + 步骤条 + 最近交互 |
| 打断 | 心流下降，调节器参数变化 |
| Session 结束 | 本节统计摘要 |
| 跨天恢复 | 到期复习 + "从 Phase 2 开始" |

---

## 7. 与 demo-plan.md 的关系

`demo-plan.md` 的 6 Tab 方案保留作为**首次演示脚本**。本设计的 4 区域单页是**日常运行面板**，精简到最关键的 4 组信息。两者互补、不冲突。
