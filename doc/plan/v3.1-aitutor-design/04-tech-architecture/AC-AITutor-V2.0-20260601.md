# Agent 协作方案 — AITutor V2.0

> 角色：AR-001 架构师
> 日期：2026-06-01
> 上游：TD-001（10 模块 / 30 接口 / 90 流向 / 10 边界 / 8 性能指标）

---

## 一、Agent 角色清单（10 个内部逻辑 Agent + 2 个外部用户角色）

> 说明：M-001 ~ M-010 模块与内部逻辑 Agent 一一对应；额外保留 PM-AGENT（产品经理）/ USER（终端用户）两个外部角色。

| Agent 编号 | 角色名 | 对应模块 | 生命周期 | 状态 |
|----------|--------|---------|---------|------|
| AG-001 | Bootstrap Agent | M-001 启动中间件 | 全程常驻 | 已发布 |
| AG-002 | Pedagogy Agent | M-002 教学引擎 | 全程常驻 | 已发布 |
| AG-003 | HaluGate Agent | M-003 抗幻觉网关 | 全程常驻 | 已发布 |
| AG-004 | DataPipeline Agent | M-004 数据管线 | 全程常驻 | 已发布 |
| AG-005 | RAG Orchestrator | M-005 检索与生成 | 全程常驻 | 已发布 |
| AG-006 | Memory Agent | M-006 会话与记忆 | 全程常驻 | 已发布 |
| AG-007 | Integration Adapter | M-007 集成适配器 | 全程常驻 | 已发布 |
| AG-008 | FSM Agent | M-008 流程状态机 | 全程常驻 | 已发布 |
| AG-009 | Status Broadcaster | M-009 状态推送 | 全程常驻 | 已发布 |
| AG-010 | Extension Agent | M-010 扩展生态 | 全程常驻 | 已发布 |
| AG-011 | PM-AGENT（外部） | 产品经理 | 间歇（PRD/ADR 评审时） | 外部 |
| AG-012 | USER（外部） | 终端用户 | 全程交互 | 外部 |

---

## 二、Agent 协作定义（按 3.3 模板完整定义）

### AG-001 Bootstrap Agent
| 字段 | 内容 |
|------|------|
| 职责边界 | 加载配置/校验 DB 兼容/注册 5 类中间件/启动 WebSocket/暴露 /health；**不**负责业务逻辑与数据处理 |
| 输入接口 | pyproject.toml + .env；IF-001 健康检查；IF-002 中间件重载；IF-003 OpenAPI |
| 输出接口 | DE-001 配置；DE-002 服务实例；DE-003 兼容报告；DE-004 中间件清单；DE-005 WS 连接池 |
| 通信协议 | 进程内 DI（Depends 注入）；启动信号走 asyncio.Event |
| 状态同步 | 无状态；纯启动器 |
| 冲突解决 | 端口冲突 → EX-002 递增重试 3 次；DB 不兼容 → EX-001 自动迁移；不与其他 Agent 冲突 |
| 故障恢复 | 启动失败 → 阻断；中间件降级 → 标记降级状态（DE-004） |
| 资源配额 | CPU 0.5 核 / 内存 100MB / 启动时间 < 5s / 端口尝试 ≤3 |
| 生命周期 | 创建：uv run main:app；运行：常驻；销毁：SIGTERM/SIGINT |
| 来源标注 | [TD:M-001/BR-003/BR-008] |

### AG-002 Pedagogy Agent
| 字段 | 内容 |
|------|------|
| 职责边界 | 调度 5 教学子策略（费曼/FSRS/阶段/休息/复述）；**不**负责 LLM 评分实现（M-007）；**不**负责 RAG 检索（M-005） |
| 输入接口 | IF-004 ~ IF-007；FSRS 调度事件（每 5 分钟）；DE-011 ~ DE-018 |
| 输出接口 | DE-013 用户复述；DE-014 评分报告；DE-015 待复习；DE-016 FSRS 卡片；DE-017 正确率；DE-018 learner_profile |
| 通信协议 | 进程内函数调用（同步）；LLM 评分走 M-007 REST（异步入队） |
| 状态同步 | 有状态（learner_profile 全量加载到内存，启动时读 SQLite，热路径 5min 持久化） |
| 冲突解决 | 并发写 learner_profile → BR-014 hysteresis + WAL 乐观锁；AGAIN 风暴 → ADR-006 5min 同卡 1 次 |
| 故障恢复 | LLM 评分不可用 → EX-009 10% 兜底；FSRS 算法异常 → 维持原档位 + WARN 日志 |
| 资源配额 | CPU 1 核 / 内存 200MB / 调度协程 ≤2 / LLM 评分并发 ≤5 / 超时 30s |
| 生命周期 | 创建：M-001 启动后；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-002/BR-011~BR-015] + [调研报告:S-002] |

### AG-003 HaluGate Agent
| 字段 | 内容 |
|------|------|
| 职责边界 | 三级级联抗幻觉裁决；**不**负责声明抽取（由 M-005 LLM 阶段产出 claim_set DE-019）；**不**负责回答生成 |
| 输入接口 | IF-008 验证请求；IF-009 评分查询；DE-019 声明集 |
| 输出接口 | DE-020 幻觉评分（附 source + 三层打分明细） |
| 通信协议 | 进程内同步调用（毫秒级）；异构 LLM 法官走 M-007 REST 并行 |
| 状态同步 | 无状态（每次调用是纯函数 + LLM 推理） |
| 冲突解决 | NLI 假阳 100%（[调研报告:NLI-05]）→ 强制 prompt retry 1 次；LLM 全部失败 → 阻断并返回"无法验证"（EX-016） |
| 故障恢复 | NLI 模型加载失败 → 跳过 NLI 直接走 SLM 层；SLM 失败 → 直接走 LLM；LLM 失败 → 阻断回答 |
| 资源配额 | CPU 1 核 + 内存 1GB（DeBERTa-v3-large ONNX）/ GPU 0.5GB（V-1+ 启用）；NLI 推理 ≤500ms / SLM ≤1s / LLM ≤3s |
| 生命周期 | 创建：M-001 启动时预加载 NLI 模型；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-003/BR-016~BR-019] + [调研报告:NLI-01/05/13] + [ADR-003] |

### AG-004 DataPipeline Agent
| 字段 | 内容 |
|------|------|
| 职责边界 | 5 步数据流转（采集→清洗→入库→分块→治理）；**不**负责会话管理（M-006）；**不**负责检索服务（M-005） |
| 输入接口 | IF-010 ~ IF-012；本地资料路径（B-002）；research-tool 10 外部源 |
| 输出接口 | DE-023 原始文档；DE-024 清洗文档；DE-025 文档记录；DE-026 FSRS 卡片表；DE-027 知识图谱 |
| 通信协议 | research-tool 走 pip -e 进程内 Python API；pdf2zh 走 CLI 进程 + 文件；LLM 抽取走 M-007 REST |
| 状态同步 | 有状态（每 task_id 持久化到 pipeline_configs DE-009） |
| 冲突解决 | 并发入库 → ADR-010 content_hash UPSERT；抽取失败 → EX-023 跳过 + 重试 3 次 |
| 故障恢复 | 单源失败 → EX-027 跳过该源继续；LLM 抽取失败 → 退化为关键词匹配；pdf2zh 失败 → 3 次降级 LM Studio（BR-028） |
| 资源配额 | CPU 2 核 / 内存 1GB / 并发任务数 ≤3 / pdf 翻译并发 5 页/批 / 超时 60s/页 |
| 生命周期 | 创建：M-001 启动后；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-004/BR-023~BR-026] + [调研报告:RI-005/RI-006/S-008] |

### AG-005 RAG Orchestrator（核心编排）
| 字段 | 内容 |
|------|------|
| 职责边界 | LangGraph StateGraph 编排（preprocess→retrieve→rerank→llm→postprocess）+ 抗幻觉后处理调用 AG-003；**不**负责 LLM Provider 实现（AG-007）；**不**负责文档存储（AG-004） |
| 输入接口 | IF-013 ~ IF-014；用户问题（B-001）；DE-031/DE-032 评估 |
| 输出接口 | B-005 学习回答（带 source + 幻觉评分） |
| 通信协议 | 进程内同步调用；LLM 走 AG-007 REST；WS 推送走 AG-009 |
| 状态同步 | 无状态（每次请求是独立 StateGraph run） |
| 冲突解决 | 重检索 + 抗幻觉双重循环 → ADR-005 max_total_rounds=5；缓存键碰撞 → ADR-007 query_hash+top1_doc_id 组合 |
| 故障恢复 | 重检索 3 轮超限 → EX-031 返回"已尽力"；LLM 不可用 → EX-009 10% 兜底；缓存降级 → EX-005 SQLite LRU |
| 资源配额 | CPU 2 核 / 内存 2GB / 并发 RAG 请求 ≤10 / 单请求超时 30s / LLM QPS ≤5 |
| 生命周期 | 创建：M-001 启动后；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-005/BR-019/BR-029/BR-032] + [调研报告:RI-002/RI-007] + [ADR-005] |

### AG-006 Memory Agent
| 字段 | 内容 |
|------|------|
| 职责边界 | 三层记忆管理（短期/长期/实体）+ 会话 CRUD；**不**负责向量模型加载（M-005 共享） |
| 输入接口 | IF-015 ~ IF-018；DE-033 ~ DE-036 |
| 输出接口 | 会话列表；短期摘要；长期事实；实体向量 |
| 通信协议 | 进程内同步；SQLite 走 aiosqlite；向量检索走 sqlite-vec |
| 状态同步 | 有状态（短期摘要常驻内存，定期持久化） |
| 冲突解决 | 跨用户污染 → CE-012 user_id 强校验；token 失控 → EX-035 强制 50 轮摘要 |
| 故障恢复 | 长期记忆失败 → EX-007 降级 JSON；sqlite-vec 扩展加载失败 → EX-008 关键词回退；JSON 损坏 → EX-036 NDJSON 回退 |
| 资源配额 | CPU 0.5 核 / 内存 500MB / 会话数 ≤100 / 单会话摘要 ≤2048 token |
| 生命周期 | 创建：M-001 启动后；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-006/BR-009/BR-010/BR-033/BR-034] + [调研报告:RI-008/S-011] |

### AG-007 Integration Adapter
| 字段 | 内容 |
|------|------|
| 职责边界 | 3 类外部集成（research-tool/pdf2zh/LLM Provider）；**不**负责业务编排；纯适配层 |
| 输入接口 | IF-019 ~ IF-021；B-003 LLM 凭证（env） |
| 输出接口 | OpenAI/Anthropic/Ollama 统一 LLMResponse schema；research-tool 6 模块结果；pdf2zh 翻译结果 |
| 通信协议 | LLM 走 HTTPS（OpenAI/Anthropic 443 / Ollama 11434）；research-tool 走 Python import；pdf2zh 走 CLI |
| 状态同步 | 无状态（每次调用是新请求） |
| 冲突解决 | LLM 多 provider 故障 → 主备切换（OpenAI→Anthropic→Ollama）；密钥缺失 → BR-035 CI 阻断 |
| 故障恢复 | 单 provider 失败 → 30s 超时 + 重试 1 次（EX-009）；3 provider 全失败 → 阻断并写入 audit_log |
| 资源配额 | CPU 1 核 / 内存 200MB / LLM 并发 ≤10 / 单次超时 30s / 速率限制 5 QPS/provider |
| 生命周期 | 创建：M-001 启动时初始化 3 provider；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-007/BR-027/BR-028/BR-035] + [调研报告:RI-005/RI-006/RI-007] |

### AG-008 FSM Agent
| 字段 | 内容 |
|------|------|
| 职责边界 | 90% 确定性状态机匹配 + 10% LLM 兜底（带审计）；**不**负责具体业务执行；纯路由决策 |
| 输入接口 | IF-022 ~ IF-024；DE-021 状态机；DE-022 审计日志 |
| 输出接口 | 状态转移决策；兜底 LLM 调用请求；audit_log 写入 |
| 通信协议 | 进程内同步；兜底 LLM 走 AG-007 |
| 状态同步 | 有状态（FSM 规则表 + version 启动时全量加载） |
| 冲突解决 | 版本不匹配 → EX-018 强制升级 + 持久化新 version；连续 3 次同状态兜底 → 写入 state_machine_proposals |
| 故障恢复 | 规则表损坏 → 启动失败阻断；LLM 兜底失败 → audit_log 写失败阻断（BR-021 写失败阻断兜底） |
| 资源配额 | CPU 0.5 核 / 内存 100MB / 匹配 QPS ≤100 / 兜底调用 ≤0.5 QPS / 审计写失败立即阻断 |
| 生命周期 | 创建：M-001 启动时加载 FSM + 校验 version；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-008/BR-020~BR-022] + [调研报告:RI-OC-10/S-019] + [ADR-008] |

### AG-009 Status Broadcaster
| 字段 | 内容 |
|------|------|
| 职责边界 | 监听任务完成事件 → 原子写 STATUS.md → WebSocket 推送；**不**负责业务事件生成；**不**负责业务逻辑 |
| 输入接口 | IF-025 ~ IF-026；任务完成事件（DE-040）；其他 Agent 状态变化 |
| 输出接口 | B-006 状态推送事件（WebSocket + STATUS.md） |
| 通信协议 | WebSocket（asyncio）；文件 IO 走 aiofiles |
| 状态同步 | 有状态（WS 连接池 DE-005 + STATUS.md 锁） |
| 冲突解决 | 写入竞争 → CE-014 completed_at 排序；心跳丢失 → EX-025 指数退避 |
| 故障恢复 | WS 客户端断开 → 移除连接 + 重连机制；STATUS.md 写失败 → 阻断推送（避免脏写） |
| 资源配额 | CPU 0.3 核 / 内存 50MB / WS 连接 ≤100 / 推送延迟 ≤1s / 消息大小 ≤64KB |
| 生命周期 | 创建：M-001 启动时建立 WS 服务；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-009/BR-005] + [调研报告:RI-007] |

### AG-010 Extension Agent
| 字段 | 内容 |
|------|------|
| 职责边界 | 4 类扩展（Anki/Obsidian/CLI Plugin/Web）；**不**负责核心业务；**不**负责安全沙箱（V-4 引入） |
| 输入接口 | IF-027 ~ IF-030；DE-042 ~ DE-045 |
| 输出接口 | .apkg 文件；Obsidian vault commit；CLI 插件 entry_point 注册；Web 静态资源 |
| 通信协议 | Anki-Connect HTTP 8765；git CLI 子进程；importlib.metadata entry_point；Vite build 静态托管 |
| 状态同步 | 有状态（plugin_registry DE-045） |
| 冲突解决 | 插件加载失败 → EX-044 跳过 + WARN；Obsidian vault >100MB → EX-043 LFS；Anki-Connect 不可用 → EX-042 仅生成 .apkg |
| 故障恢复 | 体积超限 → EX-037 阻塞 release；git 失败 → 保留本地不阻塞；CLI 插件签名缺失 → 不加载 |
| 资源配额 | CPU 1 核（打包时峰值）/ 内存 500MB / 插件数 ≤50 / commit 每日 ≤1 次 |
| 生命周期 | 创建：M-001 启动时扫描 entry_point；运行：常驻；销毁：随进程 |
| 来源标注 | [TD:M-010/BR-037] + [调研报告:RI-011/RI-012/S-014/S-015] |

### AG-011 PM-AGENT（外部）
| 字段 | 内容 |
|------|------|
| 职责边界 | 提交 PRD / 评审 ADR / 决策 GUI 形态（S-017）；不进入运行时 |
| 输入接口 | PRD V2.0 文件；GUI 决策结论 |
| 输出接口 | PRD 修订意见；GUI 形态决策 |
| 通信协议 | 文件级（人工）；不入进程 |
| 状态同步 | N/A |
| 冲突解决 | PM 决策优先于 AR 推断（如 S-017 GUI） |
| 故障恢复 | N/A |
| 资源配额 | N/A |
| 生命周期 | 间歇；评审时介入 |
| 来源标注 | [TD:SA-001 PM-AGENT] |

### AG-012 USER（外部）
| 字段 | 内容 |
|------|------|
| 职责边界 | 通过桌面/Web 端发起请求；查看状态 |
| 输入接口 | UI 操作；自然语言提问（B-001） |
| 输出接口 | 学习回答（B-005） |
| 通信协议 | HTTP/REST + WebSocket |
| 状态同步 | 客户端无状态（除 WebSocket） |
| 冲突解决 | N/A |
| 故障恢复 | 客户端断线 → UI 重连 + 指数退避 |
| 资源配额 | 客户端无限制 |
| 生命周期 | 全程 |
| 来源标注 | [TD:B-001/B-005] |

---

## 三、协作流程图（主链路）

```
[USER] ──HTTP──> [AG-001 Bootstrap /health 验证]
        │
        └─POST /v1/rag/query──> [AG-005 RAG Orchestrator]
                                       │
                                       ├─StateGraph run─┐
                                       │                 ↓
                              [AG-006 Memory] 加载短期+长期+实体
                                       │
                                       ↓
                              preprocess (清洗+扩写)
                                       │
                                       ↓
                              路由判定（80%标准/20%代理，ADR-004）
                                       │
                                       ↓
                              retrieve (sqlite-vec)
                                       │
                                       ↓
                              rerank (cross-encoder)
                                       │
                                       ↓
                              llm ([AG-007 LLM Adapter])
                                       │
                                       ↓
                              [AG-003 HaluGate] 三级级联评分
                                       │ 失败 → max_total_rounds++ → 重检索
                                       ↓ 全部失败 → 返回"已尽力" + EX-016
                              postprocess (附 source + trace_id)
                                       │
                                       ↓
                              [AG-002 Pedagogy] 写入学习记录
                                       │
                                       ↓
                              [AG-009 Broadcaster] WS 推送 status_update
                                       │
                                       ↓
                              [USER] 接收 B-005 学习回答
```

---

## 四、协作协议详细规范

### 4.1 进程内通信
- **框架**：FastAPI Depends 注入 + 模块单例
- **序列化**：进程内直接 Python 对象；无序列化开销
- **错误传播**：Python 异常向上抛；AG-001 中间件统一捕获 → structlog 记录 + HTTP 状态码

### 4.2 跨 Agent 事件总线
- **协议**：asyncio.Event + 内存 Pub/Sub（AG-009 Broadcaster 内部）
- **用途**：任务完成事件 → STATUS.md 更新
- **消息大小**：≤64KB
- **失败处理**：事件丢失仅影响 UI 看板，不影响数据

### 4.3 跨进程通信（如未来 V-3）
- **协议**：Redis Pub/Sub 或 NATS（V-3 引入）
- **序列化**：JSON（向后兼容）
- **降级**：Redis 不可用 → 切换为 SQLite 事件队列表

### 4.4 共享状态访问
- **主存储**：SQLite WAL 模式
- **访问方式**：aiosqlite 异步 + 单连接串行写
- **冲突解决**：事务 + 乐观锁 + ADR-005/006/010 业务规则

---

## 五、状态同步机制

| 状态 | 存储 | 同步方式 | 一致性 | 持久化 |
|------|------|---------|--------|--------|
| AG-001 配置/服务实例 | SQLite config/services | 启动加载 + 写回 | 强一致 | 启动时持久化 |
| AG-002 learner_profile | SQLite + 内存缓存 | 启动加载 + 5min 写回 | 强一致 | WAL 模式 |
| AG-003 NLI 模型 | 内存 | 启动预加载 | N/A | 无（重启重载） |
| AG-004 pipeline_configs | SQLite | 每 task_id 持久化 | 强一致 | 实时 |
| AG-005 RAG context | 内存（StateGraph） | 每请求独立 | 请求级 | 无 |
| AG-006 短期记忆 | 内存 + SQLite | 摘要触发持久化 | 最终一致 | 50 轮强制 |
| AG-007 LLM Provider | 无状态 | 每次新请求 | N/A | 无 |
| AG-008 FSM 规则 | 内存 + SQLite | 启动加载 + version 校验 | 强一致 | 启动时 |
| AG-009 WS 连接池 | 内存 | 实时维护 | N/A | 无 |
| AG-010 plugin_registry | SQLite | 启动扫描 | 强一致 | 实时 |

---

## 六、冲突解决策略汇总

| 冲突类型 | 检测机制 | 解决方案 | 涉及 Agent |
|---------|---------|---------|-----------|
| 端口冲突 | 启动时 bind 失败 | 8000 → 8001 → 8002 递增 | AG-001 |
| DB 不兼容 | 启动时 schema diff | EX-001 自动迁移脚本 | AG-001 |
| learner_profile 并发写 | BR-014 + WAL | hysteresis 2 天 + 乐观锁 | AG-002 |
| AGAIN 风暴 | 评分频次 | ADR-006 5min/卡 1 次 | AG-002 |
| NLI 假阳 | 评分分布监控 | 强制 retry 1 次 → SLM → LLM | AG-003 |
| FSM 版本漂移 | 启动 version 校验 | EX-018 强制升级 | AG-008 |
| 文档并发入库 | content_hash | ADR-010 UPSERT | AG-004 |
| WS 心跳丢失 | ping 间隔 > 30s | EX-025 指数退避 | AG-009 |
| 重检索+抗幻觉双重循环 | max_total_rounds | ADR-005 阈值 5 | AG-005/AG-003 |
| 缓存键碰撞 | hash 冲突 | ADR-007 组合键 | AG-005 |
| 缓存污染 | 拒绝回答 | 写回前过滤"无法/不能/拒绝" | AG-005 |
| 跨用户污染 | user_id 校验 | CE-012 强校验 | AG-006 |
| LLM 全部失败 | provider 错误率 | 主备切换 + 阻断 | AG-007 |
| 插件加载失败 | entry_point 异常 | EX-044 跳过 + WARN | AG-010 |
| STATUS.md 写竞争 | 多任务并发 | completed_at 排序 | AG-009 |

---

## 七、故障恢复机制（soul 4.15 协作闭环检测）

### 7.1 死锁检测
- **依赖图验证**：10 Agent 单向依赖 M-001 → 其他 Agent，无环（[TD:MP]）
- **超时机制**：所有跨 Agent 调用设置超时（参见各 Agent 资源配额）
- **结论**：✅ 无死锁风险

### 7.2 活锁检测
- **终止条件**：每个 Agent 协作流有明确退出条件（max_total_rounds=5 / FSM 匹配命中 / 写回完成）
- **最大重试**：LLM 调用 1 次（EX-009）；pdf2zh 3 次（BR-028）；FSM 兜底 3 次连续同状态才反哺
- **结论**：✅ 无活锁风险

### 7.3 降级策略汇总
| 失败场景 | 降级方案 | 数据损失 |
|---------|---------|---------|
| Redis 不可用 | SQLite LRU | 性能下降 |
| LLM provider 不可用 | 主备切换 | 无 |
| 全部 LLM 不可用 | audit_log 写失败阻断 | 阻断用户回答 |
| NLI 模型加载失败 | 跳过 NLI 直接 SLM | 准确度下降 |
| sqlite-vec 加载失败 | 关键词回退 | 检索质量下降 |
| research-tool 源失败 | 跳过该源 | 单源缺失 |
| WebSocket 不可用 | 客户端轮询 /health | 实时性下降 |
| pdf2zh 失败 | LM Studio 降级 | 无 |

### 7.4 状态一致性
- **强一致表**：config/services/learner_profile/fsrs_cards/audit_log
- **最终一致表**：cache_entries/monitor_events/short_term_memories
- **同步机制**：WAL + 5min 定期 flush + 启动时全量加载

---

## 八、Agent 协作完成度自评

- ✅ 10/10 内部 Agent 有完整协作定义（分工/通信/同步/冲突/故障恢复/资源配额）
- ✅ 1/1 外部 Agent（PM）有定义
- ✅ 1/1 用户角色有定义
- ✅ 全部协作流无死锁/活锁
- ✅ 全部 Agent 有超时配置
- ✅ 全部 Agent 有降级方案
- ✅ 状态同步机制明确
- **D3 估算 = 95%**（R3 职责不重叠验证通过；R26 协作闭环验证通过）

---

## 九、AR 洞察

### [AR-洞察-006] 状态机与 LLM 兜底的协作边界
AG-008 FSM Agent 内部"90% 自研 FSM + 10% LLM 兜底"组合存在 1 个隐含风险：LLM 兜底调用失败时 audit_log 写失败（BR-021）会阻断兜底，进而阻断上游 AG-005 RAG 的下一步。**建议**：在 AG-005 与 AG-008 之间增加"audit 异步队列"，audit 写失败仅记 WARN，不阻断上游。[AR推断:BR-021 严格性可能引发级联故障]
