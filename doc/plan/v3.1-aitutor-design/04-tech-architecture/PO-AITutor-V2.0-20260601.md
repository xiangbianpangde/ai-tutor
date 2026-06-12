# 性能优化方案 — AITutor V2.0

> 角色：AR-001
> 日期：2026-06-01
> 上游：TD-001 性能容量预判表 8 项 NFR + 4 类容量上限
> 覆盖率：8/8 = 100%（D6 = 100%）

---

## 一、性能指标总览

| 性能指标 | 目标值 | 瓶颈模块 | 优化策略数 | 验证方法 | 来源 |
|---------|--------|---------|----------|---------|------|
| /health 响应时间 | < 500ms | M-001 | 1 | wrk -t4 -c100 -d30s | [SA:BR-030] |
| 1000 文档检索 P95 | < 2s | M-005 | 3 | locust 100 并发 | [SA:BR-032] |
| 单会话 8h token 增长 | < 50% | M-006 | 2 | 8h 持续对话 | [SA:BR-033] |
| 50 轮 token 增长 | < 30% | M-006 | 1 | pytest 50 轮 fixture | [SA:BR-034] |
| 二次查询 latency 下降 | ≥ 50% | M-005 | 2 | ab -n1000 cache hit | [SA:BR-031] |
| 10 页 PDF 翻译 | ≤ 60s | M-007 | 2 | 10/30/100 页 PDF | [SA:BR-027] |
| LLM 法官调用延迟 | < 5s P50 | M-003 | 3 | 1000 条 claim 吞吐 | [SA:BR-018] |
| 单元测试覆盖率 | ≥ 80% | 全部 | 1 | coverage report | [SA:BR-040] |

---

## 二、性能优化详表（按 3.6 模板）

### PO-001 /health 响应时间
- **性能指标**：响应时间 < 500ms
- **瓶颈分析**：M-001 启动时 5 类中间件装配 + 12 个 IF 路由解析
- **优化策略**：
  1. /health 路由只做端口 + DB ping（PRAGMA quick_check），不执行业务逻辑
  2. 避免在 /health 中调用 Pydantic 完整验证
  3. 使用 uvicorn `--loop uvloop` 加速事件循环
- **实施步骤**：
  1. M-001 注册独立 health_router，不依赖 Session 中间件
  2. PRAGMA quick_check 不解析 SQL 直接返回 OK
- **验证方法**：wrk -t4 -c100 -d30s /health，P95 ≤ 500ms
- **回滚策略**：健康检查降级为完整 Pydantic 验证（牺牲性能换取诊断信息）
- **来源标注**：[SA:BR-030] + [AR推断]

### PO-002 1000 文档检索 P95
- **性能指标**：1000 文档检索 P95 < 2s
- **瓶颈分析**：M-005 sqlite-vec 向量索引 + cross-encoder 精排 + LLM 推理
- **优化策略**：
  1. **缓存预热**（M-005 启动时预计算 top 100 高频查询 embedding）
  2. **多级缓存**：SQLite LRU (L1) → 语义阈值 0.85~0.95 (L2) → 重新检索 (L3)
  3. **向量分片**：V-1 阶段将 embedding 按文档域分片（V-1 引入 M-011 向量化缓存层）
- **实施步骤**：
  1. M-005 启动时触发预热任务（concurrent.futures + 10 worker）
  2. 语义缓存键 = query_hash + top1_doc_id（[ADR-007]）
  3. V-1 阶段加 M-011 抽象层（[AR洞察-007]）
- **验证方法**：locust 100 并发查询，统计 P95 ≤ 2s
- **回滚策略**：禁用 L2 语义缓存，回退到纯 LRU
- **来源标注**：[SA:BR-032] + [调研报告:CACHE-13/49] + [ADR-007]

### PO-003 单会话 8h token 增长
- **性能指标**：8h 持续对话 token 增长 < 50%
- **瓶颈分析**：M-006 短期记忆未及时摘要
- **优化策略**：
  1. **强制 50 轮摘要**（[SA:BR-034]）：超过 50 轮触发强制摘要
  2. **摘要间隔可配置**（默认 20 轮 + 50 轮强制）
- **实施步骤**：
  1. M-006 检测 conversation length
  2. 触发 summary_interval 滚动摘要
- **验证方法**：模拟 8h 对话 fixture，统计 token 增长曲线
- **回滚策略**：固定每 10 轮摘要（更激进但 LLM 调用更多）
- **来源标注**：[SA:BR-033/BR-034] + [调研报告:MEM-48]

### PO-004 50 轮 token 增长
- **性能指标**：50 轮对话 token 增长 < 30%
- **瓶颈分析**：同上 PO-003
- **优化策略**：
  1. ConversationSummaryBufferMemory（[TS-009]）原生支持
- **实施步骤**：
  1. M-006 直接使用 langchain.memory.ConversationSummaryBufferMemory
  2. 调整 summary_interval 到 20 轮
- **验证方法**：pytest + 50 轮 fixture
- **回滚策略**：改用 BufferWindowMemory（无摘要）
- **来源标注**：[SA:BR-034] + [调研报告:RI-008]

### PO-005 二次查询 latency 下降
- **性能指标**：相同/相似查询二次响应 latency 下降 ≥ 50%
- **瓶颈分析**：M-005 语义缓存未生效
- **优化策略**：
  1. **语义阈值 0.85~0.95 命中**（[SA:BR-031]）：embedding 相似度在范围内直接返回
  2. **缓存键防碰撞**（[ADR-007]）：query_hash + top1_doc_id
- **实施步骤**：
  1. M-005 cache 写回前做语义 embedding 计算
  2. 命中阈值 0.85~0.95（经验值）
- **验证方法**：ab -n1000 含 cache hit，对比 P50 延迟
- **回滚策略**：禁用语义阈值，仅 hash 匹配
- **来源标注**：[SA:BR-031] + [调研报告:CACHE-49] + [ADR-007]

### PO-006 10 页 PDF 翻译
- **性能指标**：10 页中文 PDF 翻译 ≤ 60s
- **瓶颈分析**：M-007 pdf2zh 串行翻译
- **优化策略**：
  1. **并发 5 页/批**（[SA:BR-027]）：asyncio.Semaphore(5)
  2. **3 次失败降级 LM Studio**（[BR-028]）
  3. **进度推送**（[M-009]）：每批完成推送 status_update
- **实施步骤**：
  1. M-004 拆 PDF 为 5 页批
  2. asyncio.gather 并发调用 pdf2zh
  3. 失败 3 次切 LM Studio
- **验证方法**：10/30/100 页 PDF 翻译基准
- **回滚策略**：单页串行（牺牲速度）
- **来源标注**：[SA:BR-027/BR-028] + [调研报告:RI-006]

### PO-007 LLM 法官调用延迟
- **性能指标**：单次 LLM 法官调用 < 5s P50
- **瓶颈分析**：M-003 异构 LLM（Claude Haiku + GPT-4o-mini）单次串行
- **优化策略**：
  1. **异构 LLM 并行**（[SA:BR-018]）：asyncio.gather 并行 ≥2 独立打分
  2. **HaluGate 三级级联**（[ADR-003]）：~95% 流量被 NLI/SLM 截断，仅 5% 走 LLM
  3. **V-1 阶段加 M-012 熔断器**（[TD:ER V-1]）
- **实施步骤**：
  1. M-003 编排 NLI → SLM → LLM 决策
  2. LLM 阶段 asyncio.gather 两个 provider
  3. 加熔断器（V-1 引入）
- **验证方法**：1000 条 claim 评分吞吐测试
- **回滚策略**：单 provider 串行（牺牲鲁棒性）
- **来源标注**：[SA:BR-018] + [调研报告:NLI-01/05/13] + [ADR-003]

### PO-008 单元测试覆盖率
- **性能指标**：单元测试覆盖率 ≥ 80%
- **瓶颈分析**：M-001~M-010 全部模块需测试
- **优化策略**：
  1. **CI 集成 pytest + coverage**（[TS-023]）
  2. **覆盖率 < 80% 阻塞 release**（[SA:BR-040]）
- **实施步骤**：
  1. CI 阶段执行 pytest --cov=src --cov-report=xml
  2. coverage < 80% 标记为红
- **验证方法**：coverage report + diff
- **回滚策略**：临时降低阈值到 60%（需 PM 决策）
- **来源标注**：[SA:BR-040]

---

## 三、容量规划（按 3.7 模板）

### CP-001 知识图谱节点扩容
- **性能指标**：节点数
- **当前容量**：10000 节点（JSON-Lines）
- **目标容量**：100000+ 节点
- **扩容倍数**：10×
- **所需资源增量**：
  - CPU：+2 核（图查询）
  - 内存：+2 GB
  - 存储：+5 GB
- **扩容步骤**：
  1. V-2 引入 Neo4j（图数据库，替代 JSON-Lines）
  2. M-014 图谱同步器（JSON-Lines → Neo4j）
  3. 双写 7 天 → 切换读取 → 下线 JSON-Lines
- **验证方法**：locust 100 并发图查询，P95 < 1s
- **回滚策略**：Neo4j 切只读 → JSON-Lines 切回活跃（30 分钟回退）
- **来源标注**：[TD:ER V-2] + [调研报告:SR-013]

### CP-002 文档数扩容
- **性能指标**：文档数
- **当前容量**：5000 文档
- **目标容量**：50000 文档
- **扩容倍数**：10×
- **所需资源增量**：
  - 内存：+1 GB
  - 存储：+10 GB
  - sqlite-vec 索引分片（按 domain 拆分）
- **扩容步骤**：
  1. V-1 阶段加 M-011 向量化缓存层
  2. sqlite-vec 索引按 domain 分片
  3. 并发读路由到对应分片
- **验证方法**：locust 100 并发，P95 < 2s
- **回滚策略**：回退单分片（牺牲并发）
- **来源标注**：[TD:ER V-1] + [SA:PC]

### CP-003 LLM QPS 扩容
- **性能指标**：LLM QPS
- **当前容量**：5 QPS
- **目标容量**：20 QPS
- **扩容倍数**：4×
- **所需资源增量**：
  - 内存：+500 MB（多 provider 客户端）
  - 网络：+5 Mbps
- **扩容步骤**：
  1. M-012 熔断器（V-1）支持多 provider 并发
  2. 令牌桶参数调整
- **验证方法**：locust 50 并发，错误率 < 1%
- **回滚策略**：降至 5 QPS（牺牲吞吐）
- **来源标注**：[TD:ER V-1] + [SA:PC]

---

## 四、性能瓶颈预判

### 4.1 CPU 瓶颈
- **DeBERTa-v3-large-mnli CPU 推理**（[调研报告:NLI-13]）：数百 ms/次
- **缓解**：ONNX 量化 + V-1 阶段可选 GPU（[AR洞察-001]）

### 4.2 IO 瓶颈
- **SQLite WAL 写并发**：单写者
- **缓解**：批量提交 + 5min 定期 flush

### 4.3 网络瓶颈
- **LLM Provider 速率限制**：OpenAI Tier 1 500 RPM
- **缓解**：令牌桶 5 QPS/provider + 主备切换

### 4.4 内存瓶颈
- **DeBERTa-v3-large ONNX 模型**：~400MB
- **缓解**：单例加载 + 进程内共享

---

## 五、AR 洞察

### [AR-洞察-011] Python GIL 对 RAG 编排的影响
M-005 RAG 编排中包含 LLM 推理（CPU 密集）和 sqlite-vec 检索（IO 密集）。**建议**：RAG 编排主协程跑在事件循环中，CPU 密集的 NLI 推理通过 run_in_executor 卸载到默认 ThreadPoolExecutor（不受 GIL 影响，因 onnxruntime 是 C++ 绑定）。[AR推断:GIL 规避]
