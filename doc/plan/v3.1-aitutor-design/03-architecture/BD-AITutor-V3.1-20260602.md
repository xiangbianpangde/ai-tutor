# 系统边界定义 — AITutor V3.1

> 接收：BP-001~BP-021 / EX-001~EX-033 / BR-001~BR-050
> 边界数：15（输入 6 / 输出 5 / 不处理 4）

---

## B-001 用户输入（CLI/GUI）
- 类型：输入边界
- 描述：用户通过 CLI 子命令或 GUI 桌面端触发学习/查询/管理操作
- 关联模块：M-003 → M-002
- 数据格式：CLI 子命令 + JSON 参数 / GUI 事件流
- 安全：API token（CLI）/ 桌面端 loopback
- 来源：[SA:BP-001 触发] + [SA:BR-036]

## B-002 用户输入（Web）
- 类型：输入边界
- 描述：浏览器访问 http://localhost:8000/web
- 关联模块：M-003 (Web) → M-002
- 数据格式：HTTP REST + WebSocket
- 安全：token + CSP 头 + Depends(auth) 强校验（CE-018 修复）
- 来源：[SA:BP-020] + [SA:CE-018]

## B-003 LLM Provider 接口
- 类型：输入边界
- 描述：OpenAI / Anthropic / Ollama / LM Studio 等 LLM 服务
- 关联模块：M-008 / M-010 / M-013
- 数据格式：OpenAI 兼容 HTTP（httpx async）
- 安全：API key 环境变量 / loopback（本地）
- 来源：[SA:AR-003 保留三家] + [SA:BR-001 禁 MCP]

## B-004 NLI 本地推理
- 类型：输入边界
- 描述：本地 NLI 模型（entailment 评分）
- 关联模块：M-008 (NLI 子)
- 数据格式：HTTP / 进程内调用
- 安全：loopback
- 来源：[SA:BP-007] + [SA:EX-015]

## B-005 本地资料库（文件/目录）
- 类型：输入边界
- 描述：用户选择本地 PDF / Obsidian vault / 文件夹
- 关联模块：M-014 / M-008
- 数据格式：PDF / Markdown / 图片
- 安全：文件路径白名单 + 权限校验
- 来源：[SA:BP-009/017/018]

## B-006 CI / 工具链
- 类型：输入边界
- 描述：PR push / pre-commit / 4 工具链调用
- 关联模块：M-016
- 数据格式：GitHub Actions YAML / 进程退出码
- 安全：secrets 加密
- 来源：[SA:BP-021] + [SA:BR-046]

---

## B-007 WebSocket 推送输出
- 类型：输出边界
- 描述：状态/进度/FSRS 队列/告警 实时推送
- 关联模块：M-002 → 客户端
- 数据格式：JSON 事件流
- 安全：token + 连接数限制 (max=1000, CE-016 修复)
- 来源：[SA:BP-010] + [SA:BR-007] + [SA:CE-016]

## B-008 打包产物
- 类型：输出边界
- 描述：CLI/GUI 三平台 artifact
- 关联模块：M-015 → 文件系统 / CI artifact
- 数据格式：exe/dmg/AppImage/whl + sha256
- 安全：sha256 校验
- 来源：[SA:BP-014] + [SA:BR-031~033]

## B-009 学习结果
- 类型：输出边界
- 描述：用户可见的学习进度/评分/推荐
- 关联模块：M-002 → 客户端
- 数据格式：JSON
- 安全：用户隔离
- 来源：[SA:BP-003/004/005]

## B-010 监控指标
- 类型：输出边界
- 描述：trace_id / metric / 告警
- 关联模块：M-006 → Prometheus / 日志
- 数据格式：OTel 协议 / structlog JSON
- 安全：脱敏 (BR-038)
- 来源：[SA:BR-004/038] + [SA:EX-007]

## B-011 红线报告
- 类型：输出边界
- 描述：6+1 规范矩阵命中报告 + 修复手册链接
- 关联模块：M-016 → CI artifact / 控制台
- 数据格式：GitHub 格式 + Markdown 报告
- 安全：-
- 来源：[SA:BP-021] + [SA:BR-050] + [SA:DE-046]

---

## B-012 多用户支持（不处理）
- 类型：不处理边界
- 描述：本期不实现多用户/家庭成员支持
- 关联模块：-
- 原因：[SA:AR-005] 进入 B-002 backlog
- 来源：[SA:AR-005] + [SA:BR-005]

## B-013 云端备份（不处理）
- 类型：不处理边界
- 描述：本期不实现云端同步/备份
- 关联模块：-
- 原因：[SA:AR-004] 进入 B-001 backlog
- 来源：[SA:AR-004]

## B-014 PPT/Word 翻译（不处理）
- 类型：不处理边界
- 描述：本期仅 PDF→Markdown，PPT/Word 翻译进入 backlog
- 关联模块：-
- 原因：[SA:AR-007] 进入 B-003 backlog
- 来源：[SA:AR-007]

## B-015 扫描件 OCR（不处理）
- 类型：不处理边界
- 描述：扫描件/手写 OCR 走 backlog
- 关联模块：-
- 原因：BP-018 仅支持图片/录音，扫描件进 B-004
- 来源：[SA:BP-018 分支条件]

---

## 边界汇总

- 输入边界 6 条（B-001~B-006）：CLI/GUI、Web、LLM、NLI、本地资料、CI
- 输出边界 5 条（B-007~B-011）：WS、打包、学习结果、监控、红线报告
- 不处理边界 4 条（B-012~B-015）：多用户、云备份、PPT/Word、扫描件

D4 达成：15 条边界全部含输入/输出/不处理 + 关联模块 + 数据格式 + 安全要求 + 来源标注 = 100%
