# 系统边界定义 — AITutor V2.0

> 10 条边界（4 输入 + 4 输出 + 2 不处理）
> 全部含 数据格式 / 安全要求 / 关联模块

---

## 输入边界

### B-001 用户自然语言提问
- **类型**：输入边界
- **描述**：用户通过桌面 GUI / Web SPA 发送的自然语言学习问题（多轮会话上下文）
- **关联模块**：M-005（RAG 检索入口）
- **数据格式**：text/plain (UTF-8)；可选 audio_path
- **安全要求**：用户身份通过 session_id 绑定；跨用户强隔离（CE-012）
- **来源标注**：[SA:BP-014 步骤 1]

### B-002 用户喂入的本地资料
- **类型**：输入边界
- **描述**：用户在向导/设置中指定的本地资料目录（含 PDF/MD/其他）；CLI `ai-tutor ingest <path>` 也走此边界
- **关联模块**：M-004（数据管线）、M-001（配置）
- **数据格式**：file path（pathlib 规范化，CE-016）；文件类型 [pdf, md]
- **安全要求**：只读访问；路径校验（防路径穿越）；UTF-8/UTF-16 编码探测
- **来源标注**：[SA:BP-009 步骤 1] + [SA:BP-019 步骤 1]

### B-003 LLM Provider 凭证
- **类型**：输入边界
- **描述**：OpenAI / Anthropic / Ollama 的 API Key（仅本地 Ollama 无需 key）
- **关联模块**：M-007（LLM 适配器）
- **数据格式**：env var（OPENAI_API_KEY / ANTHROPIC_API_KEY / OLLAMA_HOST）
- **安全要求**：**硬编码 → CI 阻断** [BR-035]；.env.example 提供模板
- **来源标注**：[SA:BR-035] + [NFR-4]

### B-004 状态机规则更新
- **类型**：输入边界
- **描述**：开发者更新 DE-021 state_machine 表的 transitions 字段；启动时校验与本地 learner_profile 版本
- **关联模块**：M-008（状态机）
- **数据格式**：JSON transitions + int version
- **安全要求**：版本不匹配强制升级（CE-007 修复）；dev-only 入口
- **来源标注**：[SA:CE-007 修复]

---

## 输出边界

### B-005 学习回答（带 source + 幻觉评分）
- **类型**：输出边界
- **描述**：向用户返回的最终学习回答；事实性回答必带 source 引用 + NLI/SLM/LLM 法官评分记录
- **关联模块**：M-005 → M-003 → 用户
- **数据格式**：Markdown（含 source 链接 + score 列表 + trace_id）
- **安全要求**：含 trace_id 必带 [BR-004]；含 quality_score ≥ 0.7 否则标"已尽力"
- **来源标注**：[SA:BP-014 步骤 6] + [SA:BR-017]

### B-006 状态推送事件
- **类型**：输出边界
- **描述**：通过 WebSocket 推送到桌面/Web 前端的状态更新事件
- **关联模块**：M-009 → 桌面壳 / 浏览器
- **数据格式**：JSON `{type:"status_update", payload:{...}, trace_id}`；推送延迟 ≤ 1s
- **安全要求**：CSWSH 防护（token 校验）；消息大小限制 64KB
- **来源标注**：[SA:BP-018 步骤 3]

### B-007 审计日志（10% LLM 兜底）
- **类型**：输出边界
- **描述**：所有 LLM 兜底调用的 input/output/llm_judge_score 写入 audit_log；trace_id 索引
- **关联模块**：M-008 → audit_log 表
- **数据格式**：SQLite row（DE-022）
- **安全要求**：**写失败阻断兜底** [BR-021]；不清理（合规 R-09）；human_reviewed 标志
- **来源标注**：[SA:BR-021]

### B-008 制品发布（3 平台）
- **类型**：输出边界
- **描述**：CI 产出 CLI + Desktop + Web 三平台 artifact；发布到 GitHub Release
- **关联模块**：M-010（CLI/Desktop 打包） + CI
- **数据格式**：exe/dmg/AppImage + .apkg + static web bundle
- **安全要求**：体积校验 Electron ≤ 250MB / Tauri ≤ 50MB [BR-037]；Nuitka 禁用商业模块
- **来源标注**：[SA:BP-016] + [SA:EX-037/EX-038]

---

## 不处理边界

### B-009 OCR（扫描件 PDF）
- **类型**：不处理边界
- **描述**：本期不做 OCR；扫描件 PDF（无文本层）直接报错 NB-3
- **关联模块**：M-004
- **数据格式**：N/A
- **安全要求**：返回明确错误 EX-020，不静默失败
- **来源标注**：[SA:NB-3] + [SA:EX-020] + [调研报告:R-17]

### B-010 多用户并发登录
- **类型**：不处理边界
- **描述**：本期仅单用户 [AR-006]；家庭多用户/云端备份进 backlog
- **关联模块**：全模块
- **数据格式**：N/A
- **安全要求**：所有查询强制带 user_id（防止跨用户污染，CE-012）
- **来源标注**：[SA:AR-006] + [SA:CE-012]
