# 性能优化方案 — AITutor V3.1

> 10 个性能指标全部覆盖（[TD:PC-AITutor] 100% 达成）。

---

## PO-001 WS 推送延迟 ≤1s (P95)

- **性能指标**：[TD:PC-AITutor:WS 推送延迟] ≤1s 端到端
- **瓶颈模块**：M-002（API 网关 + WS）
- **瓶颈分析**：单进程 asyncio + 21 编排并发；WS 推送走事件总线 → 序列化 → 发送
- **优化策略**：
  1. asyncio 直推（避免线程切换）
  2. 心跳 5s 保活
  3. 状态聚合（5s 窗口去重）
  4. JSON 序列化走 orjson 加速
- **实施步骤**：
  - M-006 引入 `orjson` 替代 `json`
  - M-002 WS 推送走协程直推
- **验证方法**：100/500/1000 并发推送 p95/p99 压测
- **回滚策略**：移除 orjson / 关闭聚合 → 退回标准 json
- **来源标注**：[TD:PC-AITutor:WS 推送延迟] + [调研报告:RI-007/WSE-17]

## PO-002 PDF 翻译 10 页 ≤60s (P95)

- **性能指标**：[TD:PC-AITutor:PDF 翻译]
- **瓶颈模块**：M-014（数据管线）
- **瓶颈分析**：pdf2zh 阻塞调用 + LLM 调用 + clean 步骤
- **优化策略**：
  1. ThreadPoolExecutor（4 workers）
  2. 3 次降级链：pdf2zh → pdfplumber → LM Studio
  3. 60s 超时强制降级
- **实施步骤**：
  - M-014 引入 ThreadPool + 降级链
  - 计时埋点（每段耗时）
- **验证方法**：50/100 页 PDF 翻译时间 + 成功率
- **回滚策略**：ThreadPool 改回顺序执行 / 关闭超时降级
- **来源标注**：[TD:PC-AITutor:PDF 翻译] + [调研报告:RI-006/PDF-47/03/12]

## PO-003 50 轮 token 增长 < 30%

- **性能指标**：[TD:PC-AITutor:50 轮 token 增长]
- **瓶颈模块**：M-013（会话编排）
- **瓶颈分析**：每轮对话 token 累积，长期会话 OOM 风险
- **优化策略**：
  1. 摘要压缩（BR-008）
  2. LRU 淘汰最旧 10%（[TD:ADR-012]）
  3. 长期 store 分页（按需加载）
- **实施步骤**：
  - M-013 引入摘要压缩
  - SQLite LRU 字段（last_access_at）
- **验证方法**：模拟 200 轮对话 token 增长曲线
- **回滚策略**：禁用摘要压缩 / LRU 改为禁用
- **来源标注**：[TD:PC-AITutor:50 轮] + [TD:ADR-012]

## PO-004 NLI 重检索 ≤3 轮

- **性能指标**：[TD:PC-AITutor:NLI 重检索]
- **瓶颈模块**：M-008（NLI 子能力）
- **瓶颈分析**：NLI 模型加载慢 + 推理延迟
- **优化策略**：
  1. NLI 模型 lazy load + 一次常驻
  2. NLI 推理异步化（不阻塞 LLM 调用）
  3. NLI 评分缓存（语义相同 query 命中）
  4. LLM 法官兜底（[TD:SR-005] 缓解）
- **实施步骤**：
  - DP-003 NLI 模型独立进程（子进程）
  - M-005 缓存 NLI 评分（TTL 1h）
- **验证方法**：1000 query 重检索轮次分布
- **回滚策略**：NLI 改回进程内加载 / 关闭缓存
- **来源标注**：[TD:PC-AITutor:NLI 重检索] + [TD:ADR-006] + [TD:SR-005] + [调研报告:RI-009/NLI-01]

## PO-005 LLM 兜底比例 ≈10%

- **性能指标**：[TD:PC-AITutor:LLM 兜底]
- **瓶颈模块**：M-009（教学编排）+ M-007（Pipeline）
- **瓶颈分析**：FSM 状态机覆盖率不足
- **优化策略**：
  1. FSM 状态机优化（覆盖率提升）
  2. 节流（避免反复兜底）
  3. audit_log 必传（[TD:SR-011] 缓解）
- **实施步骤**：
  - M-009 FSM 状态扩展
  - DE-023/024 字段全 NOT NULL
- **验证方法**：100 任务 FSM 命中/兜底分布
- **回滚策略**：FSM 改回最小集 / 关闭节流
- **来源标注**：[TD:PC-AITutor:LLM 兜底] + [TD:ADR-005] + [TD:SR-011]

## PO-006 缓存命中率 ≥30% (WARN < 30%)

- **性能指标**：[TD:PC-AITutor:缓存命中率]
- **瓶颈模块**：M-005（Cache 中间件）
- **瓶颈分析**：语义相似度阈值 + TTL 抖动
- **优化策略**：
  1. 语义阈值 0.85~0.95
  2. TTL ±20% 抖动（防雪崩）
  3. LRU 容量上限
  4. 命中失败时查 SQLite 兜底
- **实施步骤**：
  - M-005 实现语义缓存
  - 双后端（SQLite 默认 / Redis 可选）
- **验证方法**：10k query hit_rate 分布
- **回滚策略**：改回精确匹配 / 关闭抖动
- **来源标注**：[TD:PC-AITutor:缓存命中率] + [TD:ADR-004] + [调研报告:RI-010/CACHE-13]

## PO-007 覆盖率 ≥80% (CI 阻断)

- **性能指标**：[TD:PC-AITutor:覆盖率]
- **瓶颈模块**：M-016（红线编排）
- **瓶颈分析**：测试用例不充分
- **优化策略**：
  1. CI 强制阻断（branch protection）
  2. 修复手册链接
  3. 覆盖率门禁（80%）
- **实施步骤**：
  - `.github/workflows/redlines.yml` 配置
  - `pytest --cov-fail-under=80`
- **验证方法**：覆盖率门禁压测
- **回滚策略**：阈值临时调低 / 关闭 CI 阻断
- **来源标注**：[TD:PC-AITutor:覆盖率] + [TD:ADR-010] + [TD:BR-046~050] + [调研报告:RI-004]

## PO-008 打包体积 CLI<50MB / GUI<200MB

- **性能指标**：[TD:PC-AITutor:打包体积]
- **瓶颈模块**：M-015（打包调度）
- **瓶颈分析**：chromadb / sentence-transformers 依赖重
- **优化策略**：
  1. Nuitka onedir（禁 onefile）
  2. UPX 压缩（软约束 warn only，ADR-009）
  3. 平台分（V3.5 GUI 形态决定）
- **实施步骤**：
  - M-015 引入 UPX
  - CI 矩阵 3 平台
- **验证方法**：3 平台 artifact 大小
- **回滚策略**：关闭 UPX / 改回 onedir
- **来源标注**：[TD:PC-AITutor:打包体积] + [TD:ADR-009] + [调研报告:RI-003/PYN-19]

## PO-009 启动时间 ≤30s

- **性能指标**：[TD:PC-AITutor:启动时间]
- **瓶颈模块**：M-001（服务入口）
- **瓶颈分析**：5MW 装配 + 配置加载
- **优化策略**：
  1. 5MW 异步注册（不阻塞）
  2. warmup 缓存预热
  3. SQLite 索引预创建
- **实施步骤**：
  - M-001 启动期异步并发注册
  - 关键路径 LRU 缓存
- **验证方法**：冷启动/热启动时间
- **回滚策略**：改回同步注册 / 关闭预热
- **来源标注**：[TD:PC-AITutor:启动时间] + [TD:BR-002] + [TD:SR-010]

## PO-010 红线 CI 时长 ≤5min (P95)

- **性能指标**：[TD:PC-AITutor:红线 CI]
- **瓶颈模块**：M-016（红线编排）
- **瓶颈分析**：4 工具链全量跑
- **优化策略**：
  1. 4 工具并行执行
  2. Ruff/Import Linter 缓存（增量）
  3. pytest 选择性跑（仅变更模块）
- **实施步骤**：
  - GitHub Actions matrix 并行
  - pytest 加 `--co` 收集 + 缓存
- **验证方法**：PR 全量红线时长
- **回滚策略**：改回串行 / 关闭缓存
- **来源标注**：[TD:PC-AITutor:红线 CI] + [TD:ADR-010]

---

## 性能优化策略汇总

| 类别 | 优化手段 | 应用指标 |
|------|---------|---------|
| 异步 | asyncio / 协程直推 | WS / RAG / PDF |
| 缓存 | LRU + 语义 + 双后端 | 命中率 / WS |
| 并行 | ThreadPool / 矩阵 | PDF / CI |
| 降级 | 3 次降级链 | PDF / NLI / FSM |
| 抖动 | TTL ±20% | 缓存 |
| 压缩 | UPX / onedir | 打包 |
| 锁版本 | CI 锁 | 工具链 / 升级 |
| lazy load | NLI 模型 | RAG |
| 索引 | ChromaDB HNSW | RAG |
| 摘要 | token 压缩 | 长期记忆 |
