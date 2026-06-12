# 框架决策记录（FDR） — M-007 Pipeline 调度

> 对应模块: M-007
> 来源标注: [DD-M推断:依据=Pipeline + Strategy 设计模式] + [DD-001:MD-M-007]
> 作者: DD-M-007-20260602

---

## FDR-M007-001

| 字段 | 值 |
|------|-----|
| 决策编号 | FDR-M007-001 |
| 决策标题 | 5 阶段独立子模块 + 抽象 BaseStage |
| 决策状态 | 已接受 |
| 决策内容 | 将 Pipeline 拆分为 preprocess / retrieve / rerank / llm / postprocess 5 个独立子模块文件，引入 BaseStage 抽象基类统一 run(input) 接口 |
| 决策理由 | ① 符合 MD-M-007 子模块拆分 ② 单文件 ≤20 函数约束 ③ 单一职责原则（每个阶段一个文件） ④ 便于 DD-S 按 Stage 分别搭建代码骨架 |
| 拒绝的替代方案 | A. 单文件 5 阶段函数（orchestrator.py 内含 5 个 run_xxx 函数）—— 拒绝理由：单文件 > 200 行、循环依赖风险、难测试 |
| 影响范围 | stages/ 目录下 5 个文件、orchestrator.py 的注入方式 |
| 相关FDR | 无 |

---

## FDR-M007-002

| 字段 | 值 |
|------|-----|
| 决策编号 | FDR-M007-002 |
| 决策标题 | 状态机与兜底分离 |
| 决策状态 | 已接受 |
| 决策内容 | FSM 状态定义（state.py）与兜底策略（fallback.py）分离为两个文件 |
| 决策理由 | ① 单一职责（FSM 只管状态转换，Fallback 只管兜底）② 避免 state.py 引入 LLM 依赖导致循环 ③ MD-M-007 状态机段和异常处理段本就分离 |
| 拒绝的替代方案 | A. FSM + Fallback 合一（pipeline_state.py）—— 拒绝理由：兜底需要 LLMStage 引用，state 不应依赖 stage |
| 影响范围 | state.py、fallback.py |
| 相关FDR | 无 |

---

## FDR-M007-003

| 字段 | 值 |
|------|-----|
| 决策编号 | FDR-M007-003 |
| 决策标题 | 5 阶段子包用 stages/ 而非 stage_N.py |
| 决策状态 | 已接受 |
| 决策内容 | 5 阶段文件归类到 stages/ 子目录（如 stages/preprocess.py）而非平铺（preprocess_stage.py 等） |
| 决策理由 | ① 符合 FS-M-007 目录规范 ② 5 阶段内聚性高、便于按子包导入 ③ 限制 stages/ 子包规模 < 10 文件 |
| 拒绝的替代方案 | A. 平铺（orchestrator.py 同级）—— 拒绝理由：aitutor/pipeline/ 根目录文件数膨胀到 8 个 |
| 影响范围 | stages/__init__.py + 5 个 stage 文件 |
| 相关FDR | 无 |

---

## FDR-M007-004

| 字段 | 值 |
|------|-----|
| 决策编号 | FDR-M007-004 |
| 决策标题 | 测试文件镜像源码结构 |
| 决策状态 | 已接受 |
| 决策内容 | 测试目录采用 tests/unit/test_pipeline/ 镜像 src/aitutor/pipeline/，5 阶段测试在 test_pipeline/test_stages/ 子目录 |
| 决策理由 | ① FS-M-007 全局目录规范 ② pytest testpaths 默认 tests/ ③ 镜像结构便于定位 |
| 拒绝的替代方案 | A. 测试平铺为 test_pipeline_preprocess.py 等长名 —— 拒绝理由：违反 Python 模块命名规范 |
| 影响范围 | tests/unit/test_pipeline/ 10 个文件 |
| 相关FDR | 无 |

---

## FDR-M007-005

| 字段 | 值 |
|------|-----|
| 决策编号 | FDR-M007-005 |
| 决策标题 | 注释率 100%（D3=100） |
| 决策状态 | 已接受 |
| 决策内容 | 所有文件（src + tests + 5 文档）共 20 个产出全部含文件头/类/函数/测试场景注释 |
| 决策理由 | ① 满足 soul 3.2-3.6 模板要求 ② 100% 注释覆盖确保 DD-S 搭建骨架不遗漏 ③ 测试场景注释供 DD-T 编写测试 |
| 拒绝的替代方案 | A. 仅 src 注释、tests 简略 —— 拒绝理由：违反 R3 注释完整性 |
| 影响范围 | 全部 20 个产出 |
| 相关FDR | 无 |

---

## 来源标注

[DD-001:MD-M-007 子模块拆分行] + [DD-001:FS-M-007 目录结构段] + [DD-M推断:依据=soul 4.13 FDR 模板]
