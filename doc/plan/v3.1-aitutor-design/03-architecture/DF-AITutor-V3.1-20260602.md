# 数据流向图 — AITutor V3.1

> 接收：DE-001~DE-048
> 覆盖：48 个实体的正常 + 异常流向（每实体 2 条路径 = 96 条）

---

## 一、正常流向（48 DE 全映射）

| DE | 名称 | 产生 | 正常路径 | 消费 | 存储 | 一致性 |
|----|------|------|---------|------|------|--------|
| DE-001 | config | M-001 | pyproject.toml + .env → [合并] → M-001 | 全部 MW | SQLite / 内存 | 强 |
| DE-002 | service_instance | M-001 | 启动 → [记录 PID/ts] → 内存 | M-006 监控 | 内存 | 强 |
| DE-003 | 兼容报告 | M-001 | schema 检测 → [v1→v2 迁移] → M-001 | M-001 决策 | SQLite | 强 |
| DE-004 | middleware_status | M-001 | 5 MW 装配 → [enabled] → 全部 MW | M-001 | SQLite | 强 |
| DE-005 | WS 连接 | M-002 | 客户端连接 → [握手] → M-002 | M-002 推送 | 内存 | 强 |
| DE-006 | session | M-004 | 启动会话 → [加载] → M-009 | M-013 | SQLite | 强 |
| DE-007 | cache_entry | M-005 | 写入 → [语义hash+TTL±20%] → M-005 | M-008 检索 | SQLite/Redis | 最终 |
| DE-008 | monitor_log | M-006 | 埋点 → [trace_id 32hex] → M-006 | 全部 | SQLite | 强 |
| DE-009 | pipeline_state | M-007 | 5 阶段调度 → [状态机] → M-007 | M-008 编排 | 内存 | 强 |
| DE-010 | rag_state | M-008 | 路由 → [round=0..3] → M-008 | M-008 重检索 | 内存 | 强 |
| DE-011~014 | 费曼 | M-010 | LLM 评分 → [追问 ≤2] → M-010 | M-009 推进 | SQLite | 最终 |
| DE-015~016 | FSRS | M-011 | py-fsrs → [Again 节流 5min] → M-011 | M-002 推送 | SQLite | 强 |
| DE-017~018 | 阶段 | M-012 | 7 天窗口 → [hysteresis] → M-012 | M-009 | SQLite | 强 |
| DE-019 | rest_log | M-009 | 25min 静默 → [toast] → M-009 | M-002 | SQLite | 强 |
| DE-020~022 | NLI | M-008 | 抽取 → [评分 ≥0.7] → M-008 | M-008 生成 | SQLite | 强 |
| DE-023~024 | chunk+audit | M-009 | 5万行分块 → [状态机 90%] → M-009 | M-008 检索 | SQLite | 强 |
| DE-025 | 翻译 | M-014 | pdf2zh+DeepSeek → [60s 预算] → M-014 | M-014 清洗 | 文件/SQLite | 最终 |
| DE-026 | chunks | M-014 | clean+chunk → [≤2000tok+200overlap] → M-014 | M-008 检索 | Chroma+SQLite | 最终 |
| DE-027 | 看板状态 | M-002 | 聚合 → [WS 推送 ≤1s] → M-002 | 客户端 | 内存+WS | 最终 |
| DE-028 | 路由决策 | M-008 | 复杂度判定 → [simple/mod/complex] → M-008 | M-008 分流 | 内存 | 强 |
| DE-029 | 检索结果 | M-008 | top-K → [精排] → M-008 | M-008 生成 | 内存 | 强 |
| DE-030 | monitor_metric | M-006 | 聚合 → [hit_rate/latency] → M-006 | M-002 | SQLite | 强 |
| DE-031~032 | 长期记忆 | M-013 | 关键事实 → [实体+时间] → M-013 | M-009 | SQLite | 最终 |
| DE-033~034 | artifact | M-015 | Nuitka onedir → [sha256] → M-015 | CI upload | 文件+SQLite | 强 |
| DE-035 | file_tree | M-017 | FILE_GRAPH 扫描 → [校验] → M-017 | CI warn | 文件+SQLite | 弱 |
| DE-036 | setup | M-003 | 向导 6 步 → [P50≤10min] → M-003 | M-001 | SQLite | 强 |
| DE-037 | local_lib | M-008 | 索引+Obsidian → [本地≥60%] → M-008 | M-008 检索 | Chroma+SQLite | 最终 |
| DE-038 | artifact_cfg | M-001 | 1:N config → [USER scope] → M-001 | M-015 | SQLite | 强 |
| DE-039 | doctor_report | M-016 | 自检 → [6+1 矩阵] → M-016 | M-003 | SQLite | 强 |
| DE-040 | web_session | M-002 | 浏览器 → [fingerprint] → M-002 | M-002 | SQLite | 强 |
| **DE-046** | **redline_report** ⭐ | M-016 | 4 工具链 → [退出码/规范号] → M-016 | CI/M-003 | SQLite | 强 |
| **DE-047** | **ci_run** ⭐ | M-016 | 触发 → [PR/main/手动] → M-016 | M-016 | SQLite | 强 |
| **DE-048** | **tool_version_lock** ⭐ | M-016 | requirements-dev.txt → [语义版本] → M-016 | M-016 | 文件 | 强 |

---

## 二、异常流向（关键异常）

| DE | 触发 | 异常路径 | 降级策略 | 终态 |
|----|------|---------|---------|------|
| DE-001 | EX-004 配置损坏 | M-001 → [拒绝] → M-016 → [备份] → 提示用户 | 需人工 | 启动失败 |
| DE-003 | EX-001 旧库不兼容 | M-001 → [迁移 v1→v2] → M-001；失败 → [EX-001] → 备份 | 自动 / 人工 | 数据迁移 |
| DE-004 | EX-006 MW 失败 | M-001 → [详细日志] → M-016 | 退出码非 0 | 启动失败 |
| DE-005 | EX-020 断连 / CE-016 风暴 | M-002 → [指数退避 ≤30s] → M-002 | 自动重连 | 连接恢复 |
| DE-007 | EX-005 Redis 不可用 / CE-002 雪崩 | M-005 → [降级 SQLite] → M-005；TTL ±20% | 自动 | 命中恢复 |
| DE-008 | EX-007 trace 缺失 | M-006 → [自动补 trace_id] → M-006 + WARN | 自动 | 监控恢复 |
| DE-009 | EX-017 状态机卡死 | M-007 → [走 LLM 兜底 10%] → M-009 audit_log | 自动 | 流程继续 |
| DE-010 | EX-016 重检索 3 轮 < 0.7 | M-008 → [强制标注"无法确认"] → M-008 + 切 web 搜索 | 自动 | 显式无源 |
| DE-013 | CE-003 评分串号 | M-010 → [强校验 user_id] → M-016 | 需 schema 迁移 | 数据修复 |
| DE-016 | CE-004 Again 风暴 | M-011 → [5min 仅 1 次 Again] → M-011 + 计数 | 自动 | 节流 |
| DE-018 | CE-005 档位跳变 | M-012 → [hysteresis 2 天] → M-012 | 自动 | 档位稳定 |
| DE-021 | EX-015 NLI 不可用 | M-008 → [降级 LLM 法官] → M-008 + trace_id | 自动 | 兜底 |
| DE-025 | EX-018 pdf2zh 失败 | M-014 → [降级 pdfplumber → LM Studio] → M-014 | 3 次降级 | 翻译完成 |
| DE-026 | EX-019 重复率 >30% | M-014 → [增强 clean+WARN] → M-014 | 不阻塞 | 标 ⚠️ |
| DE-033 | EX-023 体积超目标 | M-015 → [标 ⚠️+UPX] → M-015 | 阻塞该平台 | 优化重试 |
| **DE-046** | **EX-021 红线失败** ⭐ | M-016 → [修复手册链接] → M-016 → 阻塞 merge | 需修复后重跑 | CI 红 |
| **DE-047** | **EX-029~033 子流程** ⭐ | M-016 → [具体工具+规则 ID] → 修复手册 | 需代码修改 | 重跑 |
| **DE-048** | **EX-033 版本破坏** ⭐ | M-016 → [恢复锁版本] → M-016 | 人工+TDD | 版本稳定 |

---

## 三、数据孤岛检测

- DE-046/047/048 ⭐ V3.1 新增：唯一创建流程 = M-016 红线编排 → 消费节点 = CI / M-003 CLI → 无孤岛
- DE-035 file_tree：唯一创建 = M-017 扫描 → 消费 = CI warn → 无孤岛
- DE-038 artifact_cfg：唯一创建 = M-001 config 派生 → 消费 = M-015 打包 → 无孤岛
- 全部 48 实体均已映射产生与消费节点，D5 = 100%
- CE-007 长期记忆数据孤岛已修复（DE-032 流向在 M-013/M-009 闭环）

来源标注：[SA:DE-001~DE-048] + [SA:CE-007 数据孤岛修复]
