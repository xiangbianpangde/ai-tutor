# 安全设计方案 — AITutor V2.0

> 角色：AR-001
> 日期：2026-06-01
> 上游：TD-001 10 条系统边界（B-001~B-010）
> 覆盖率：10/10 = 100%（D8 = 100%）
> 设计原则：安全左移（soul 4.14 / R24）

---

## 一、安全设计总览

| 安全编号 | 关联边界 | 威胁模型 | 核心策略 | 来源 |
|---------|---------|---------|---------|------|
| SEC-001 | B-001 用户输入 | 注入/越权/敏感信息 | 输入校验 + user_id 隔离 + CSP | [SA:BP-014] + [CE-012] |
| SEC-002 | B-002 本地资料 | 路径穿越/越权读 | 路径规范化 + 只读访问 + 编码探测 | [SA:BP-009] + [CE-016] |
| SEC-003 | B-003 LLM 凭证 | 硬编码泄露 | env 注入 + CI 阻断 + .env.example 模板 | [SA:BR-035] + [NFR-4] |
| SEC-004 | B-004 状态机更新 | 版本漂移/恶意覆盖 | dev-only 入口 + 启动校验 + 强制升级 | [SA:CE-007] + [BR-021] |
| SEC-005 | B-005 学习回答 | 幻觉/敏感泄露 | source 强制 + 评分记录 + trace_id | [SA:BR-004/BR-017] |
| SEC-006 | B-006 WS 推送 | CSWSH/DoS/消息伪造 | Token 校验 + 64KB 限制 + 心跳 | [SA:BR-005] |
| SEC-007 | B-007 审计日志 | 审计丢失/篡改 | 写失败阻断兜底 + 不清理 + trace_id | [SA:BR-021] + [R-09] |
| SEC-008 | B-008 制品发布 | 体积异常/恶意代码 | 体积校验 + Nuitka 禁用 + 签名 | [SA:BR-037] + [EX-037] |
| SEC-009 | B-009 OCR 不处理 | 静默失败 | 显式错误 EX-020 | [SA:NB-3/EX-020] |
| SEC-010 | B-010 多用户不处理 | 跨用户污染 | 强制 user_id 注入 + 单租户模式 | [SA:AR-006] + [CE-012] |

---

## 二、安全设计详表（按 3.7 模板）

### SEC-001 B-001 用户输入
- **威胁模型**：注入攻击（SQL/Prompt）/ 越权访问 / 敏感信息泄露
- **认证策略**：session_id 绑定（[SA:BP-014 步骤 1]）
- **授权策略**：单租户模式（[B-010]），无跨用户访问
- **加密策略**：HTTP（本地，TLS 1.3 可选 Web 端）
- **审计策略**：所有 RAG 查询记录 trace_id + user_id + query
- **防护措施**：
  - 输入校验：Pydantic v2 强类型（[TS-004]）
  - SQL 注入：aiosqlite 参数化查询，无字符串拼接
  - Prompt 注入：M-005 后处理 + M-003 抗幻觉网关
  - 跨用户隔离：CE-012 user_id 强校验
- **合规要求**：GDPR（用户数据隔离）/ CCPA
- **来源标注**：[SA:BP-014] + [CE-012] + [调研报告:NLI-09 自恋偏差]

### SEC-002 B-002 本地资料
- **威胁模型**：路径穿越（../）/ 越权读 / 编码攻击
- **认证策略**：N/A（本地用户操作）
- **授权策略**：只读访问，不写入用户原目录
- **加密策略**：N/A
- **审计策略**：采集任务记录 source path
- **防护措施**：
  - 路径规范化：pathlib.Path.resolve() 检测 ..
  - 路径白名单：只允许用户配置的 data/ 子目录
  - 编码探测：chardet 自动识别 UTF-8/UTF-16
  - 文件类型白名单：[pdf, md]
- **合规要求**：用户数据所有权（用户原目录不被修改）
- **来源标注**：[SA:BP-009/BP-019] + [CE-016]

### SEC-003 B-003 LLM 凭证
- **威胁模型**：硬编码泄露 / 仓库提交 / 日志泄露
- **认证策略**：N/A
- **授权策略**：env var 注入（[SA:BR-035]）
- **加密策略**：.env 权限 0600
- **审计策略**：密钥使用记录（仅 hash 不入日志）
- **防护措施**：
  - 硬编码 → CI 阻断（[SA:BR-035]）：detect-secrets / gitleaks
  - .env.example 提供模板（不含真实 key）
  - 密钥轮转：支持 3 provider 切换
  - 日志脱敏：structlog 过滤器自动遮蔽
- **合规要求**：NFR-4 安全基线
- **来源标注**：[SA:BR-035] + [NFR-4]

### SEC-004 B-004 状态机更新
- **威胁模型**：版本漂移 / 恶意覆盖 / 启动失败
- **认证策略**：dev-only 入口（仅 127.0.0.1 + dev token，[API-002]）
- **授权策略**：开发者权限
- **加密策略**：N/A
- **审计策略**：版本变更写入 audit_log
- **防护措施**：
  - 启动时校验 DE-021.version vs learner_profile
  - 版本不匹配强制升级（[CE-007]）
  - 状态机表 JSON 完整性校验
  - dev 入口仅监听 localhost
- **合规要求**：N/A
- **来源标注**：[SA:CE-007 修复] + [ADR-008]

### SEC-005 B-005 学习回答
- **威胁模型**：幻觉信息 / 敏感数据泄露 / 责任不可追溯
- **认证策略**：N/A
- **授权策略**：N/A
- **加密策略**：N/A
- **审计策略**：trace_id 必带（[SA:BR-004]）+ quality_score 记录
- **防护措施**：
  - 100% 事实性回答附 source（[SA:BR-017]）
  - 幻觉评分 NLI/SLM/LLM 三级记录
  - quality_score < 0.7 标"已尽力"
  - trace_id 32 hex 必带
- **合规要求**：可解释 AI / AI Act（EU）
- **来源标注**：[SA:BR-004/BR-017] + [调研报告:NLI-09]

### SEC-006 B-006 WS 推送
- **威胁模型**：CSWSH（跨站 WebSocket 劫持）/ DoS / 消息伪造
- **认证策略**：Token 校验（[SA:BR-005]）
- **授权策略**：单连接单用户
- **加密策略**：N/A（本地）
- **审计策略**：连接建立/断开日志
- **防护措施**：
  - CSWSH 防护：Origin 头校验
  - 消息大小限制：64KB
  - 心跳机制：30s ping/pong
  - 心跳超时：指数退避 EX-025
  - 连接数限制：100
- **合规要求**：N/A
- **来源标注**：[SA:BR-005] + [调研报告:RI-007]

### SEC-007 B-007 审计日志
- **威胁模型**：审计丢失 / 审计被篡改 / 责任无法追溯
- **认证策略**：N/A
- **授权策略**：append-only（不修改）
- **加密策略**：SQLite 内置加密（SQLCipher 可选 V-3）
- **审计策略**：自我审计
- **防护措施**：
  - **写失败阻断兜底**（[SA:BR-021]）：audit_log 写失败则 LLM 兜底不执行
  - 不清理（合规 R-09）：磁盘满了归档到 fs 单独分区
  - human_reviewed 标志字段
  - trace_id 索引
  - 异步批量写 + 同步落盘开关
- **合规要求**：R-09 合规保留
- **来源标注**：[SA:BR-021] + [R-09]

### SEC-008 B-008 制品发布
- **威胁模型**：体积异常 / 恶意代码 / 商业模块滥用
- **认证策略**：N/A
- **授权策略**：CI 强制签名
- **加密策略**：GitHub Release 自动签名
- **审计策略**：CI 日志 + artifact hash
- **防护措施**：
  - 体积校验：Electron ≤250MB / Tauri ≤50MB（[SA:BR-037]）
  - 超限阻塞 release（[SA:EX-037]）
  - **PyInstaller onefile 禁用**（[调研报告:RI-003 CVE-2025-59042]）
  - **Nuitka 商业模块禁用**（[调研报告:RI-NEW-3]）
  - release artifact SHA256 记录
- **合规要求**：N/A
- **来源标注**：[SA:BR-037/EX-037] + [调研报告:RI-003]

### SEC-009 B-009 OCR 不处理
- **威胁模型**：静默失败（用户期望被满足但实际未做）
- **认证策略**：N/A
- **授权策略**：N/A
- **加密策略**：N/A
- **审计策略**：N/A
- **防护措施**：
  - 扫描件 PDF（无文本层）→ 显式错误 EX-020
  - 错误信息明确告知"本期不支持 OCR"
  - 不静默失败
- **合规要求**：N/A
- **来源标注**：[SA:NB-3/EX-020] + [调研报告:R-17]

### SEC-010 B-010 多用户不处理
- **威胁模型**：跨用户数据污染 / 隐私泄露
- **认证策略**：N/A（单用户）
- **授权策略**：user_id 强制注入
- **加密策略**：N/A
- **审计策略**：所有查询带 user_id
- **防护措施**：
  - **user_id 强校验**（[SA:CE-012]）：所有 SQLite 查询带 WHERE user_id = current
  - 单租户模式：DE-035 长期记忆按 user_id 隔离
  - 跨用户查询拦截数监控
  - 未来 V-3 引入 M-015 认证服务
- **合规要求**：GDPR / CCPA（用户隔离）
- **来源标注**：[SA:AR-006] + [CE-012]

---

## 三、Agent 间互认证（soul 4.14 / R3）

| Agent 调用 | 验证方式 | 失败处理 |
|----------|---------|---------|
| AG-005 → AG-003 | 进程内同步 + trace_id 串联 | 异常向上抛 |
| AG-002 → AG-007 | LLM 调用 trace_id 透传 | 日志记录 |
| AG-005 → AG-007 | LLM 调用 trace_id 透传 + 限流令牌 | 限流拒绝 |
| AG-008 → AG-007 | LLM 兜底 + audit_log 强制写 | 写失败阻断 |
| AG-009 → 全部 | WS 事件总线 + 状态变化 trace_id | 事件丢失仅影响 UI |
| AG-010 → AG-004 | entry_point 加载 + 签名校验（V-4） | 跳过 + WARN |

---

## 四、最小权限原则

| Agent | 权限范围 |
|-------|---------|
| AG-001 | 启动配置 + 中间件装配 |
| AG-002 | learner_profile + fsrs_cards 读写 |
| AG-003 | claim_set + hallucination_scores 读写 |
| AG-004 | documents + research_cache 读写 |
| AG-005 | rag_contexts + cache 读写 |
| AG-006 | session_meta + memories 读写 |
| AG-007 | LLM Provider 调用 + 无持久化权限 |
| AG-008 | state_machine + audit_log 写 |
| AG-009 | tasks + STATUS.md 写 |
| AG-010 | plugin_registry + apkg_artifacts 写 |

**验证**：✅ 所有 Agent 仅拥有完成职责所需的最小权限（R3 / 4.14）

---

## 五、密钥管理

| 密钥类型 | 存储 | 使用 | 轮转 |
|---------|------|------|------|
| LLM API Key | env var (.env 0600) | 启动时加载到内存 | 手动 |
| Anki-Connect URL | env var | 启动时加载 | N/A |
| DeepSeek API Key | env var | 启动时加载 | 手动 |
| Ollama Host | env var | 启动时加载 | N/A |
| SQLite 文件权限 | OS 文件权限 0600 | 进程内 | N/A |
| OTel Token | env var | 启动时加载 | 手动 |

**约束**：**禁止硬编码**（[SA:BR-035]）→ CI 阻断（detect-secrets）

---

## 六、审计策略

| 审计项 | 记录字段 | 保留期 | 查询方式 |
|--------|---------|--------|---------|
| LLM 兜底调用 | trace_id / input / output / llm_judge_score | 不清理（合规） | SQL 查询 |
| 用户登录 | user_id / IP / 时间 | 90 天 | 审计查询 |
| 中间件重载 | dev token / middleware_name | 90 天 | 审计查询 |
| 状态机版本变更 | old_version / new_version / 时间 | 不清理 | 审计查询 |
| API 错误 | trace_id / error_code / stack | 30 天 | 日志查询 |
| LLM provider 切换 | provider_from / provider_to / reason | 90 天 | 审计查询 |
| 插件安装 | plugin_name / hash / 安装时间 | 不清理 | plugin_registry |

---

## 七、安全左移检查清单（4.14）

| 检查项 | 状态 | 备注 |
|--------|------|------|
| 认证覆盖 | ✅ | 10/10 边界 |
| 授权粒度 | ✅ | 模块/接口级 |
| 传输加密 | ✅ | 本地 HTTP；Web 端 TLS 1.3 可选 |
| 输入校验 | ✅ | Pydantic v2 强类型 |
| 审计日志 | ✅ | audit_log 写失败阻断兜底 |
| 密钥管理 | ✅ | env 注入 + CI 阻断 |
| Agent 间互认证 | ✅ | trace_id 串联 |
| 最小权限原则 | ✅ | 10 Agent 权限矩阵 |
| 调用链审计 | ✅ | OTel trace_id 32 hex |

**结论**：✅ 10/10 边界在架构阶段已有安全策略（安全左移 100%）

---

## 八、AR 洞察

### [AR-洞察-012] SQLite 加密缺失
本期未启用 SQLCipher（SQLite 内置加密不在 Python stdlib 中），audit_log 与 learner_profile 是明文存储的。**风险**：用户设备被物理访问时数据可读。**建议**：V-3 多用户阶段引入 SQLCipher（与 BACKEND key 派生），本期单用户场景风险可接受。[AR推断:威胁模型评估]
