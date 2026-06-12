# 数据流向图 — AITutor V2.0

> 45 DE × 2 (正常 + 异常) = 90 条流向
> 覆盖度 = 100%（45/45 DE 全部含正常+异常路径）
> 格式：DE-NNN | 产生 → 正常路径 → 消费 | 异常路径

---

## 配置与服务元数据（DE-001 ~ DE-005）

| DE | 产生 | 正常流向 | 异常流向 | 消费 | 存储 |
|----|------|----------|----------|------|------|
| DE-001 配置 | M-001 | 启动加载 → M-001~M-010 | 损坏 → fallback .env.example | 全部模块 | SQLite config |
| DE-002 服务实例 | M-001 | 启动写入 → M-009 推送 | 启动失败 → 阻断 | M-009 | SQLite services |
| DE-003 兼容报告 | M-001 | 检测结果 → M-001 决策 | 不兼容 → 自动迁移 (EX-001) | M-001 | SQLite |
| DE-004 中间件清单 | M-001 | 装配结果 → OpenAPI | 某类失败 → 降级 | M-005 | SQLite |
| DE-005 WS 连接池 | M-001 | 连接建立 → 维护 → 断开 | 心跳超时 → 指数退避 (EX-025) | M-009 | 内存 + SQLite |

## 中间件实体（DE-006 ~ DE-010）

| DE | 产生 | 正常流向 | 异常流向 | 消费 | 存储 |
|----|------|----------|----------|------|------|
| DE-006 Session | M-001 | 装配 → M-006 实例化 | 长期记忆失败 → 降级 JSON (EX-007) | M-006 | 内存 + 磁盘 JSON |
| DE-007 Cache | M-001 | 装配 → M-005 读写 | Redis 不可用 → SQLite (EX-005) | M-005 | SQLite/Redis |
| DE-008 Monitor | M-001 | 装配 → 全埋点 | OTel 失败 → structlog (EX-006) | 全部模块 | 文件 + OTLP |
| DE-009 Pipeline | M-001 | 装配 → M-005 编排 | 步骤超时 → 中断 | M-005 | SQLite |
| DE-010 RAG | M-001 | 装配 → M-005 路由 | 路由失败 → 安全侧 (EX-032) | M-005 | SQLite |

## 教学数据（DE-011 ~ DE-018）

| DE | 产生 | 正常流向 | 异常流向 | 消费 | 存储 |
|----|------|----------|----------|------|------|
| DE-011 概念集 | M-002 | 知识图谱 → 复述题生成 | 抽取失败 → 跳过 (EX-023) | M-002 | SQLite |
| DE-012 复述题 | M-002 | 生成 → UI 展示 | 模板缺失 → 兜底题 | M-002 | SQLite |
| DE-013 用户复述 | M-002 | UI 提交 → 评分 | 串号 (CE-003) → user_id 双键校验 | M-002 | SQLite |
| DE-014 评分报告 | M-002 | 评分 → L5 tracer | LLM 不可用 (EX-009) → 10% 兜底 | M-002 | SQLite |
| DE-015 待复习 | M-004(M-002) | FSRS 扫描 → 调度 | 样本不足 → 维持档位 (EX-013) | M-002 | SQLite |
| DE-016 FSRS 卡片 | M-002 | 评分 → 写回 | 冲突 → WAL 乐观锁 (EX-012) | M-002 | SQLite |
| DE-017 正确率 | M-002 | 7 天窗口 → 档位判定 | 样本不足 → 维持 | M-002 | SQLite |
| DE-018 learner_profile | M-002/M-001 | 更新 → 引擎加载 | 并发写 (CE-005) → 加 hysteresis | M-002 | SQLite |

## 抗幻觉数据（DE-019 ~ DE-022）

| DE | 产生 | 正常流向 | 异常流向 | 消费 | 存储 |
|----|------|----------|----------|------|------|
| DE-019 声明集 | M-003 | 抽取 → NLI/SLM/LLM 评分 | 抽取失败 → 跳过该声明 | M-003 | SQLite |
| DE-020 幻觉评分 | M-003 | 加权裁决 → 附 source | 全部失败 → 标"无法验证" (EX-016) | M-005 | SQLite |
| DE-021 状态机 | M-008 | 规则匹配 → 转移 | 版本不匹配 (CE-007) → 强制升级 | M-008 | SQLite |
| DE-022 审计日志 | M-008 | 兜底调用 → 写入 | 写失败 → 阻断兜底 (EX-019) | M-008 | SQLite (不清理) |

## 数据管线（DE-023 ~ DE-027）

| DE | 产生 | 正常流向 | 异常流向 | 消费 | 存储 |
|----|------|----------|----------|------|------|
| DE-023 原始文档 | M-004 | research-tool → MinHash | 源失败 → 跳过该源 (EX-027) | M-004 | research-cache/ |
| DE-024 清洗文档 | M-004 | 去重 + LLM 过滤 | 假阳高 (EX-021) → 阈值 0.90 | M-004 | SQLite |
| DE-025 文档记录 | M-004 | 入库 + 分块 | UPSERT 冲突 (CE-008) → content_hash | M-005 | SQLite + documents/*.md |
| DE-026 FSRS 卡片表 | M-002 | 创建 → 调度 | 删表 → 自动 CREATE (CE-001) | M-002 | SQLite |
| DE-027 知识图谱 | M-004 | 抽取 → JSON-Lines | 抽取失败 (EX-023) → 跳过 + 重试 | M-005 | knowledge_graph/*.jsonl |

## GUI 与集成（DE-028 ~ DE-030）

| DE | 产生 | 正常流向 | 异常流向 | 消费 | 存储 |
|----|------|----------|----------|------|------|
| DE-028 窗口实例 | M-001 | GUI 主进程创建 → IPC | 安全不满足 (BR-037) → 阻断启动 | M-001 | 内存 |
| DE-029 research-tool | M-004 | 加载 → 6 模块 | 缺 pyproject (EX-026) → 硬错误 | M-004 | 内存 |
| DE-030 翻译后端 | M-004 | DeepSeek → 翻译 | 3 次失败 (BR-028) → 降级 LM Studio | M-004 | SQLite |

## RAG 与记忆（DE-031 ~ DE-036）

| DE | 产生 | 正常流向 | 异常流向 | 消费 | 存储 |
|----|------|----------|----------|------|------|
| DE-031 RAG 上下文 | M-005 | 检索 → 评估 | 覆盖 < 70% → 重检索 (BP-013 步骤 5) | M-005 | SQLite |
| DE-032 RAG 评估 | M-005 | 评估 → 决策 | 3 轮超限 (EX-031) → 返回"已尽力" | M-005 | SQLite |
| DE-033 会话列表 | M-006 | 创建/加载 → 用户 | JSON 损坏 (EX-036) → NDJSON 回退 | M-006 | SQLite |
| DE-034 短期记忆 | M-006 | 摘要 + 近期原文 | token 失控 (EX-035) → 强制摘要 | M-006 | SQLite |
| DE-035 长期记忆 | M-006 | 写入 LangGraph Store | 跨用户污染 (CE-012) → user_id 强校验 | M-006 | SQLite + JSON |
| DE-036 实体记忆 | M-006 | sqlite-vec 检索 | 扩展加载失败 (EX-008) → 关键词 | M-006 | SQLite + vec |

## 打包与扩展（DE-037 ~ DE-045）

| DE | 产生 | 正常流向 | 异常流向 | 消费 | 存储 |
|----|------|----------|----------|------|------|
| DE-037 CLI artifact | M-010 | 打包 → 校验 | 体积超 (EX-037) → 阻塞 | CI | artifacts/ |
| DE-038 构建 artifact | CI | 3 平台 → Release | 同上 | CI | GitHub Release |
| DE-039 文件图谱 | BP-017 (M-001 CI) | FILE_GRAPH → 校验 | Import Linter 红 (EX-039) → 阻塞 | CI | YAML |
| DE-040 任务表 | M-009 | 完成事件 → STATUS.md | 排序竞争 (CE-014) → completed_at 排序 | M-009 | SQLite + STATUS.md |
| DE-041 本地资料源 | M-001 | 配置 → M-004 优先 | 路径含特殊字符 (CE-016) → 规范化 | M-004 | SQLite |
| DE-042 Anki 草稿 | M-010 | 学习记录 → Q/A | 无源 → 空草稿 | M-010 | SQLite |
| DE-043 apkg 产物 | M-010 | genanki → 导入 | Anki-Connect 不可用 (EX-042) → 仅生成 | M-010 | .apkg 文件 |
| DE-044 Obsidian vault | M-010 | 读 vault → commit | >100MB (EX-043) → LFS | M-010 | 用户目录 |
| DE-045 插件注册 | M-010 | entry_point → 加载 | 加载失败 (EX-044) → 跳过 + WARN | M-010 | SQLite |

---

## 异常流向汇总（关键 5 条）

1. **抗幻觉 NLI 假阳 + LLM 超限**（CE-006）→ M-003 强制 prompt retry 1 次；步骤 4 LLM 全部失败则阻断回答
2. **重检索 + 抗幻觉双重循环**（CE-010）→ M-005 引入 `max_total_rounds=5` 全局计数器
3. **状态机版本漂移**（CE-007）→ M-008 启动校验 DE-021.version vs learner_profile
4. **缓存键碰撞**（CE-020）→ M-005 cache_key 组合 = query_hash + semantic_embedding_top1_doc_id
5. **STATUS.md 写入竞争**（CE-014）→ M-009 步骤 2 加 completed_at 排序
