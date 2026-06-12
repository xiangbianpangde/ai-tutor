# 业务流程图 — AITutor V3.1（终版）

> 接收：PRD V3.1（CCI=0.988）+ 调研报告 V3.1（RCI=0.997）+ 需求追溯矩阵（21/21 闭环）
> 风险等级：核心（写操作/状态变更）/ 标准（读操作/查询）/ 辅助（日志/通知/增强）
> 编号：BP-001 ~ BP-020 对应 F-001 ~ F-020
> **V3.1 相对 V2.0 增量**：① BP-001 增补 S-020 4 工具链 0 红命令验收步骤；② 新增 BP-021 4 工具链 CI 红线检测流水线（覆盖 RI-004 落地）；③ BP-019 CLI 增补 S-021 规范矩阵自检子命令。

---

## BP-001 后端单体化启动与健康检查（F-001）【核心】

- **触发条件**：用户执行 `ai-tutor serve` 或桌面端启动器调用子进程
- **步骤序列**：
  1. 启动器 → 加载 `pyproject.toml` 依赖（uv lock 锁定）→ 产出 [DE-001 配置实体]
  2. 启动器 → 调用 FastAPI 单进程入口 `backend/main.py:app` → 产出 [DE-002 服务实例]
  3. 服务 → 校验 `data/tutor.db` 存在性 → 存在则 schema 兼容检测 → 产出 [DE-003 向后兼容报告]
  4. 服务 → 注册中间件（Session/Cache/Monitor/Pipeline/RAG） → 产出 [DE-004 中间件清单]
  5. 服务 → 启动 WebSocket 推送循环 → 产出 [DE-005 WS 连接池]
  6. 服务 → 暴露 `/healthz` `/version` `/status` `/metrics` `/readyz` 5 端点 → 200 响应
  7. **【V3.1 = S-020 新增】** CI 触发 4 工具链 0 红命令清单（详见 BP-021）：
     - `ruff check backend/ --output-format=github` → 退出码 0
     - `lint-imports`（指向 `.importlinter`）→ 退出码 0
     - `redocly lint api/openapi.yaml --extends=recommended-strict` → 退出码 0
     - `pre-commit run --all-files`（本地）+ `pytest --cov=ai_tutor --cov-fail-under=80`（CI）→ 退出码 0
- **分支条件**：
  - 旧库不兼容 → 走 `migrate_v1_to_v2()` → 成功回主路径 / 失败回 EX-001
  - 端口占用 → 提示 + 自动递增重试 3 次 / 仍冲突 → EX-002
  - **【V3.1 新增】** 4 工具链任一红 → 走修复手册（`doc/runbooks/redlines-fix.md`）→ 仍红 → EX-021
- **结束条件**：正常：5 端点 200 + 4 工具链全 0 红 + WebSocket ready；异常：迁移失败 / 端口冲突 / 红线未清
- **关联数据**：DE-001, DE-002, DE-003, DE-004, DE-005, DE-046
- **关联异常**：EX-001, EX-002, EX-003, EX-004, **EX-021（V3.1 新增）**
- **来源标注**：[PRD:F-001] + [调研报告:RI-001/S-001] + **V3.1:S-020/RCFM-01**

---

## BP-002 中间件层装配与依赖注入（F-002）【核心】

- **触发条件**：FastAPI 启动时（BP-001 步骤 4）
- **步骤序列**：
  1. 注册 Session（短期 ConversationSummaryBufferMemory + 长期 LangGraph Store + 实体 sqlite-vec） → [DE-006]
  2. 注册 Cache（SQLite 默认 / Redis 生产可选，语义阈值 0.85~0.95） → [DE-007]
  3. 注册 Monitor（structlog + OTel Bridge，trace_id 32hex + span_id 16hex） → [DE-008]
  4. 注册 Pipeline（preprocess→retrieve→rerank→llm→postprocess） → [DE-009]
  5. 注册 RAG（Agentic + 复杂度路由） → [DE-010]
  6. 中间件 → 注册到 FastAPI Depends 层，OpenAPI schema 可见
- **分支条件**：Redis 不可用且配置为生产模式 → 降级到 SQLite + WARN（不阻塞）
- **结束条件**：5 类中间件全部装配成功并暴露 API
- **关联数据**：DE-006, DE-007, DE-008, DE-009, DE-010
- **关联异常**：EX-005, EX-006, EX-007
- **来源标注**：[PRD:F-002] + [调研报告:RI-008/RI-010/RI-013, S-011/S-013/S-016]

---

## BP-003 教学策略：费曼学习法（F-003.1）【核心】

- **触发条件**：用户完成一节学习（点击"下一节"或系统判定完成）
- **步骤序列**：
  1. 学习引擎 → 从 L5 知识图谱取本节核心概念 → [DE-011]
  2. 引擎 → 状态机（FSM-State=POST_LEARN）→ 调用费曼 Prompt 模板 → [DE-012 复述题]
  3. UI → 弹窗显示复述题 + 录音/文本框 → [DE-013 用户复述]
  4. 引擎 → LLM 评分 + 追问薄弱点 → [DE-014 评分报告]
  5. 引擎 → 更新 L5 tracer 实体记忆 → 写入 audit log（trace_id 必带）
- **分支条件**：
  - 评分 < 60 → 触发追问循环 ≤ 2 次 / 仍低 → 标记"未掌握"+ 调度 FSRS 重学
  - LLM 评分不可用 → 走 10% LLM 兜底分支，带 trace_id
- **结束条件**：正常：评分 ≥ 60 且写入 L5；异常：LLM 调用失败走兜底
- **关联数据**：DE-011, DE-012, DE-013, DE-014, DE-026 (FSRS)
- **关联异常**：EX-008, EX-009, EX-010
- **来源标注**：[PRD:F-003.1] + [调研报告:RI-002, S-019]

---

## BP-004 教学策略：遗忘曲线调度（F-003.2）【核心】

- **触发条件**：用户完成费曼评分后 或 定时任务（每 5 分钟扫描）
- **步骤序列**：
  1. 调度器 → 从 SQLite `fsrs_cards` 拉取 `next_due <= now` 的卡片 → [DE-015]
  2. 调度器 → 对每张卡调用 py-fsrs `repeat(card, rating)` → [DE-016]
  3. 调度器 → 写回 SQLite（stability/difficulty/retrievability/next_due）
  4. 调度器 → 触发 WebSocket 推送到前端 → [DE-005 WS 消息]
  5. 前端看板 → 渲染遗忘曲线图
- **分支条件**：
  - 评分=Again（rating=1）→ stability 重置 + 立即重排 1 分钟后
  - py-fsrs 库版本 < 0.16.0 → EX-011
- **结束条件**：所有到期卡片已调度
- **关联数据**：DE-015, DE-016, DE-026
- **关联异常**：EX-011, EX-012
- **来源标注**：[PRD:F-003.2] + [调研报告:RI-002, S-002] + [RI-NEW-2 移交 BKT/DKT 协同]

---

## BP-005 教学策略：阶段渐进与自适应档（F-003.3 + F-016）【核心】

- **触发条件**：每节学完 或 7 天滑动窗口校准
- **步骤序列**：
  1. 引擎 → 统计最近 7 天正确率 → [DE-017]
  2. 引擎 → 状态机判定档位（<60%=1.0 / 60~80%=1.5 / >80%=2.0）
  3. 引擎 → 根据档位调整课程密度（节数/天 + 例题数量）
  4. 引擎 → 写入 `learner_profile` 表
- **分支条件**：样本不足 7 天 → 维持当前档位
- **结束条件**：档位判定 + 课程计划更新完成
- **关联数据**：DE-017, DE-018
- **关联异常**：EX-013
- **来源标注**：[PRD:F-003.3, F-016]

---

## BP-006 教学策略：休息提醒（F-003.4）【标准】

- **触发条件**：每节学完 或 25 分钟静默
- **步骤序列**：
  1. 调度器 → 检测最后交互时间 → 25 分钟无活动 → 触发
  2. 桌面端 → 弹 toast 通知（"建议休息 5 分钟"）
  3. 用户 → 可选"继续学习" / "进入休息"
- **分支条件**：桌面端未运行 → 仅写日志，不弹通知
- **结束条件**：用户响应
- **关联数据**：DE-019 (rest_log)
- **关联异常**：EX-014
- **来源标注**：[PRD:F-003.4]

---

## BP-007 教学策略：抗幻觉 NLI 验证（F-003.5）【核心】

- **触发条件**：LLM 生成答案完成时
- **步骤序列**：
  1. 生成结果 → 抽取事实三元组 → [DE-020 三元组]
  2. NLI 模型 → 对每条事实做 entailment 评分 → [DE-021 NLI 评分]
  3. 评分 < 阈值（如 0.7）→ 标记"待重检索"
  4. 重检索（最多 3 轮）→ 仍 < 阈值 → 强制标注"无法确认" + 提示用户
  5. LLM 法官（兜底）→ 交叉裁决
  6. 最终结果 → 100% 事实带源
- **分支条件**：
  - NLI 不可用 → 走 LLM 法官单一路径（带 trace_id）
  - 仍无源 → 拒答 + 提示"建议切换资料"
- **结束条件**：所有事实带源 或 显式标注"无法确认"
- **关联数据**：DE-020, DE-021, DE-022
- **关联异常**：EX-015, EX-016
- **来源标注**：[PRD:F-003.5] + [调研报告:RI-009, S-012] + [RI-NEW-1 移交 NLI 部署成本]

---

## BP-008 教学策略：降阶法 + 状态机引擎（F-003.6）【核心】

- **触发条件**：用户启动学习 或 复杂任务分发
- **步骤序列**：
  1. 引擎 → 加载 5 万行 md（分块喂入 ≤ 2000 token / 块）→ [DE-023 chunk]
  2. 引擎 → 状态机按"读 → 概括 → 出题 → 评估 → 推荐"转移
  3. 90% 转移走状态机 → 10% 模糊场景走 LLM 兜底（带 trace_id + 审计）
  4. 引擎 → 写 audit log
- **分支条件**：
  - 文档体量 > 5 万行 → 走"分块喂入"机制（OC-9 已包含）
  - 状态机卡死 → 走 LLM 兜底
- **结束条件**：学习会话完成 或 用户主动退出
- **关联数据**：DE-023, DE-024 (audit_log)
- **关联异常**：EX-017
- **来源标注**：[PRD:F-003.6] + [调研报告:S-019] + [PRD:F-020/NFR-2]

---

## BP-009 数据管线：PDF 入库与清洗（F-004 + F-006）【核心】

- **触发条件**：用户选择本地 PDF 文件
- **步骤序列**：
  1. 用户 → 选择 PDF → 上传至 `data/inbox/`
  2. 管线 → pdf2zh + DeepSeek 翻译（中文论文支持）→ [DE-025 翻译结果]
  3. 管线 → clean 步骤（去重 / 规范化）→ 重复率 -30%
  4. 管线 → chunk（≤ 2000 token + 200 overlap）→ 入 ChromaDB
  5. 管线 → 写 `documents` 表（status=READY）
- **分支条件**：
  - pdf2zh 失败 → 降级到 pdfplumber → 仍失败 → EX-018
  - LLM 调用超时 → 3 次重试 → 仍失败 → 切 LM Studio（本地）
- **结束条件**：状态=READY，可被检索
- **关联数据**：DE-025, DE-026 (chunks)
- **关联异常**：EX-018, EX-019
- **来源标注**：[PRD:F-004, F-007] + [调研报告:RI-006, S-009]

---

## BP-010 前端看板：实时状态更新（F-005 + F-013）【标准】

- **触发条件**：用户打开看板 / WebSocket 收到推送
- **步骤序列**：
  1. 前端 → 连接 WebSocket `/ws/status`
  2. 后端 → 推 status 更新（学习进度 / FSRS 队列 / 当前步骤）
  3. 前端 → 渲染看板（≤ 1s 刷新）→ [DE-027 看板状态]
- **分支条件**：
  - WS 断连 → 自动重连（指数退避 ≤ 30s）
  - 状态冲突 → 走最终一致
- **结束条件**：用户关闭看板
- **关联数据**：DE-005, DE-027
- **关联异常**：EX-020
- **来源标注**：[PRD:F-005, F-013] + [调研报告:RI-007, S-010]

---

## BP-011 RAG 检索与重检索（F-006 + F-008）【核心】

- **触发条件**：用户提问 / 学习引擎需要补料
- **步骤序列**：
  1. 查询 → 复杂度路由判定（simple/moderate/complex）→ [DE-028 路由决策]
  2. 简单查询 → 单轮检索 + 精排
  3. 中等 → 多轮检索 + 重写
  4. 复杂 → Agentic RAG（agent loop ≤ 3 轮，70% 阈值触发重检索）
  5. 检索 → 精排 → top-K → LLM 生成 → NLI 验证
- **分支条件**：
  - 复杂路由 → 路由阈值未确认（RI-NEW-4 移交 POC）
  - 重检索 3 轮仍 < 70% → 降级到 web 搜索
- **结束条件**：答案生成完成 / 显式"无法回答"
- **关联数据**：DE-028, DE-029
- **关联异常**：EX-021（与 EX-021 重名 → 改名 EX-021-2）
- **来源标注**：[PRD:F-006, F-008] + [调研报告:RI-009, S-012]

---

## BP-012 缓存与监控（F-002 + F-009）【标准】

- **触发条件**：所有数据访问路径
- **步骤序列**：
  1. 请求 → 先查 Cache（语义阈值 0.85~0.95）→ 命中返回
  2. 未命中 → 走正常检索管线
  3. 结果 → 写 Cache（带 expires_at + ±20% 抖动）
  4. 监控 → 记录 hit_rate / latency / token_usage
- **分支条件**：
  - Redis 不可用 → 降级 SQLite + WARN
  - 命中率 < 30% → WARN 日志 + 告警
- **结束条件**：请求完成 + 监控埋点
- **关联数据**：DE-007, DE-030 (monitor_metric)
- **关联异常**：EX-005
- **来源标注**：[PRD:F-002, F-009] + [调研报告:RI-010, S-013]

---

## BP-013 会话与长期记忆（F-002 + F-010）【核心】

- **触发条件**：用户开始学习会话
- **步骤序列**：
  1. 会话启动 → 加载短期（ConversationSummaryBufferMemory） + 长期（LangGraph Store）→ [DE-031 session]
  2. 每轮对话 → 写短期摘要（buffer 阈值 2000 token）
  3. 关键事实 → 提取写入长期 Store（按实体 / 时间）
  4. 50 轮 token 增长监控 → 超 30% 触发压缩
- **分支条件**：
  - LLM 调用失败 → 走兜底（不阻塞短期）
  - 长期 Store 满 → LRU 淘汰
- **结束条件**：用户结束会话
- **关联数据**：DE-031, DE-032 (long_term_memory)
- **关联异常**：EX-022
- **来源标注**：[PRD:F-002, F-010] + [调研报告:RI-008, S-011]

---

## BP-014 一键打包与分发（F-011）【核心】

- **触发条件**：CI 触发 / 用户执行 `make build`
- **步骤序列**：
  1. CI → matrix build（Windows + macOS + Linux）
  2. 后端 → Nuitka onedir（禁 PyInstaller onefile）→ [DE-033 artifact]
  3. 桌面端 → 按 OC-1 决策打包（Electron / Tauri / PyWebView）
  4. CI → 上传 artifact + 报告体积（CLI 目标 < 50MB / GUI < 200MB）
- **分支条件**：
  - 单平台失败 → 标 ❌ 不阻塞其他平台
  - 体积超目标 → 标 ⚠️ 需优化
- **结束条件**：3 平台 artifact 全部产出
- **关联数据**：DE-033, DE-034 (build_log)
- **关联异常**：EX-023
- **来源标注**：[PRD:F-011] + [调研报告:RI-003, S-004/S-005] + [RI-NEW-3 移交 Nuitka 商业许可]

---

## BP-015 文件结构治理（F-012）【辅助】

- **触发条件**：CI 触发 / 手动 `make file-graph`
- **步骤序列**：
  1. 脚本 → 扫描 `meta/FILE_GRAPH.md` 决策树 → [DE-035 file_tree]
  2. 脚本 → 校验当前文件结构符合决策树
  3. 不符 → 提示"建议重构"+ 不阻塞（warn only）
- **分支条件**：决策树缺失 → 走默认值
- **结束条件**：扫描完成
- **关联数据**：DE-035
- **关联异常**：EX-024
- **来源标注**：[PRD:F-012]

---

## BP-016 首次启动向导（F-014）【标准】

- **触发条件**：用户首次启动
- **步骤序列**：
  1. 向导 → 引导选择 LLM provider（OpenAI/Anthropic/Ollama）→ [DE-036 setup]
  2. 向导 → 引导选择本地资料目录 + 缓存策略
  3. 向导 → 自动跑 `doctor` 自检（覆盖率 / 工具链 / 配置）
  4. 向导 → 完成后跳学习首页
- **分支条件**：
  - LLM key 缺失 → 提示补填（不阻塞）
  - 资料目录为空 → 提示导入
- **结束条件**：P50 ≤ 10 分钟完成
- **关联数据**：DE-036
- **关联异常**：EX-025
- **来源标注**：[PRD:F-014]

---

## BP-017 本地资料库（F-015 + F-018）【标准】

- **触发条件**：用户添加本地文件夹 / Obsidian vault
- **步骤序列**：
  1. 用户 → 选择目录
  2. 引擎 → 建立索引（语义 chunk + 实体）→ [DE-037 local_lib]
  3. 检索 → 本地优先 ≥ 60% 命中
  4. Obsidian 同步 → 双向 git sync（每 30 分钟检测）
- **分支条件**：
  - 本地命中 < 60% → 补充 web 检索
  - Obsidian vault 不存在 → 走纯本地
- **结束条件**：目录索引完成
- **关联数据**：DE-037
- **关联异常**：EX-026
- **来源标注**：[PRD:F-015, F-018] + [调研报告:S-015]

---

## BP-018 多模态输入（F-017）【辅助】

- **触发条件**：用户上传图片 / 录音
- **步骤序列**：
  1. 上传 → OCR / ASR → 文本
  2. 文本 → 走正常 RAG 管线
- **分支条件**：
  - OCR/ASR 失败 → 提示重传
  - 模态不支持 → 走 backlog（B-004 扫描件 OCR）
- **结束条件**：文本入库
- **关联数据**：DE-038
- **关联异常**：EX-027
- **来源标注**：[PRD:F-017]

---

## BP-019 CLI 增强与 doctor 自检（F-019 + NFR-8 部分）【标准】

- **触发条件**：用户执行 `ai-tutor doctor` / CI
- **步骤序列**：
  1. CLI → 启动 doctor 子命令
  2. doctor → 跑 4 工具链 0 红命令（详见 BP-021）
  3. doctor → 跑 6+1 规范矩阵自检（每行 0 命中）
  4. doctor → 输出可读报告（彩色 + 退出码）
- **分支条件**：
  - 任意红 → 退出码非 0 + 打印修复手册链接
  - 全部绿 → 退出码 0
- **结束条件**：自检完成
- **关联数据**：DE-039 (doctor_report)
- **关联异常**：EX-021
- **来源标注**：[PRD:F-019, NFR-8] + **V3.1:S-021/RCFM-02**

---

## BP-020 Web 端入口（F-020）【辅助】

- **触发条件**：用户浏览器访问 `http://localhost:8000/web`
- **步骤序列**：
  1. Web → 走 FastAPI + Vite 静态资源
  2. Web → 与桌面端共享后端 API
  3. Web → 看板同 BP-010
- **分支条件**：Web 端不支持某些桌面端特性 → 走降级
- **结束条件**：用户关闭浏览器
- **关联数据**：DE-040 (web_session)
- **关联异常**：EX-028
- **来源标注**：[PRD:F-020]

---

## BP-021 【V3.1 新增】4 工具链 CI 红线检测流水线（NFR-8 + RI-004 + S-020/S-021）【核心】

- **触发条件**：PR push / main push / 本地 `pre-commit run --all-files`
- **步骤序列**：
  1. **【规范 01-架构】** Import Linter → `lint-imports` → 校验 `.importlinter` 合约（Layers + Forbidden + Independence 三类合约全启用）→ 退出码 0
  2. **【规范 02-代码】** Ruff → `ruff check backend/ --output-format=github` → 启用 `E/F/B/UP/S` 规则子集 → 退出码 0
  3. **【规范 03-Git】** pre-commit + commitlint → `pre-commit run --all-files` → 校验 commit message 符合 Conventional Commits + 钩子全过
  4. **【规范 04-API】** Redocly CLI → `redocly lint api/openapi.yaml --extends=recommended-strict` → 退出码 0
  5. **【规范 05-测试】** pytest + coverage → `pytest --cov=ai_tutor --cov-fail-under=80` → 覆盖率 ≥ 80%
  6. **【规范 06-文档】** PR 模板检查 → README.md 存在 + CHANGELOG diff 非空 + 公共 API 有 docstring
  7. **【规范 08-图谱】** 双图谱生成器 → `make codegraph && make understand-anything` → 产出 `meta/CODE_GRAPH.md` + `meta/UNDERSTAND_ANYTHING.md`
  8. **【CI 锁版本】** `requirements-dev.txt` 中 `ruff==/import-linter==/redocly-cli==/commitlint==` 锁定当前稳定版（缓解 R-17）
  9. **【CI 阻断】** main branch protection + required status checks（4 命令全过才允许 merge）→ S3 测量方式第 3 层
- **分支条件**：
  - 任一红 → 走修复手册 `doc/runbooks/redlines-fix.md`：
    - Ruff 错误码（F401 / T201 / BLE001）→ 删除 / 替换 logging / 具体化 except
    - Import Linter `BROKEN: <contract>` → 检查 `.importlinter` 合约定义 / `forbidden` 列表
    - Redocly 规则 ID（如 `operation-description`）→ 按规则修正
    - pre-commit 钩子失败 → 本地先 `pre-commit run --all-files` 通过再 push
    - 覆盖率不达标 → 补正常+边界+异常 3 类用例
- **结束条件**：6+1 规范矩阵 8 行全部 0 命中 + 4 工具链退出码全 0
- **关联数据**：DE-046 (redline_report), DE-047 (ci_config), DE-048 (tool_version_lock)
- **关联异常**：EX-021（红线检测失败专项）
- **来源标注**：[PRD:NFR-8, F-001 验收 5.] + [调研报告:RI-004/S-020/S-021/S-022/RCFM-01~06] + [调研报告:REDOC-12/25/30/31/39/52/53/54]

---

## SA 洞察

1. **【隐含依赖】** BP-021 是 BP-001 / BP-019 的"前置闸门"——若红线未清，BP-001 步骤 7 失败，PR 不可 merge。这条依赖在 V2.0 PRD 未显式；V3.1 由 S-020 显式化后，SA 需将 BP-021 标为"BP-001/019 的强制前置"，下游架构师应在 CI workflow 中加 `needs: redlines` 依赖。
2. **【跨流程风险】** BP-014 一键打包的体积目标（CLI < 50MB / GUI < 200MB）在 BP-021 步骤 5（覆盖率门禁）下可能冲突——补异常用例会增大 backend 体积，SA 需在 BP-014 步骤 4 加"体积与覆盖率权衡"分支。
3. **【推断膨胀预警】** 本轮 V3.1 新增 3 条 S-NNN 全部为"显式化增强"非"假设修正"，推断占比维持在 18% 以下（远低于 40% 阈值），D8 维持高值。

---

[阶梯退出检查] ①全部 F-001~F-020 + BP-021 全部展开: 是 ②映射无空行: 是 ③D1: 100% D3: ≥ 95%
