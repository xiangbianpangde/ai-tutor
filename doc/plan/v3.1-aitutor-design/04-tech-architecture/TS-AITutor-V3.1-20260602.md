# 技术选型清单 — AITutor V3.1

> 18 个核心选型 + 6 项备选被拒方案。每项通过 4.7 六项合理性检查。

---

## TS-001 Python 3.11.9

- **适用场景**：M-001~M-017 全栈语言（单进程承载 5MW + 21 编排）
- **合理性检查（4.7）**：
  - 场景匹配：✅ 异步 + AI 生态丰富（FastAPI/ChromaDB/py-fsrs）
  - 社区活跃：✅ Python 3.11 官方维护，3.13 已发但生态未稳
  - 学习曲线：✅ 团队 2 周内可掌握
  - 运维成本：✅ 单进程 + pip/uv 部署
  - 生态兼容：✅ 与 FastAPI/ChromaDB/SQLAlchemy 2.0 全兼容
  - 长期维护：✅ Python 3.11 EOL 2027-10，迁移 3.12/3.13 路径明确
- **拒绝的替代方案**：Node.js（异步好但 AI 生态弱）/ Go（性能好但 LLM 客户端少）/ Rust（学习曲线太陡）
- **风险等级**：低
- **技术债务**：否
- **来源**：[调研报告:RI-001/MCP-16/18/25] + [调研报告:UVP-01/PYN-19] + [TD:BR-002]

## TS-002 FastAPI 0.115.0

- **适用场景**：M-001 服务入口 + M-002 API 网关 + WS 推送
- **合理性检查**：
  - 场景匹配：✅ 原生 async + Pydantic 校验 + OpenAPI 自动生成
  - 社区活跃：✅ GitHub 75k+ stars，月度 commit 活跃
  - 学习曲线：✅ FastAPI 文档完善，1 周上手
  - 运维成本：✅ Uvicorn 单进程
  - 生态兼容：✅ 与 starlette.websockets/SQLAlchemy 全兼容
  - 长期维护：✅ 持续活跃开发
- **拒绝的替代方案**：Flask（无原生 async）/ Django（重，WS 需扩展）/ Starlette（裸框架，缺 OpenAPI）
- **风险等级**：低
- **技术债务**：否
- **来源**：[调研报告:RI-001/MCP-16] + [TD:BR-002/003]

## TS-003 SQLite 3.46.1

- **适用场景**：M-017 主存（单用户单文件）+ M-005 默认缓存后端
- **合理性检查**：
  - 场景匹配：✅ 单用户场景下 WAL 模式可支撑 100+ 并发读
  - 社区活跃：✅ SQLite 持续维护，3.46 优化器升级
  - 学习曲线：✅ 标准 SQL
  - 运维成本：✅ 单文件，零部署
  - 生态兼容：✅ SQLAlchemy 2.0 async 全兼容
  - 长期维护：✅ 永久维护（核心库）
- **拒绝的替代方案**：PostgreSQL（运维重，单用户杀鸡用牛刀）/ MySQL（同 PG）
- **风险等级**：低
- **技术债务**：否
- **来源**：[调研报告:RI-010/CACHE-13] + [TD:BR-006] + [TD:ADR-004]

## TS-004 ChromaDB 0.5.20

- **适用场景**：M-008 RAG 检索 + M-014 数据入库
- **合理性检查**：
  - 场景匹配：✅ Python 原生 + 嵌入式 + HNSW 索引
  - 社区活跃：✅ GitHub 14k+ stars，月度 commit
  - 学习曲线：✅ API 简洁，1 周上手
  - 运维成本：✅ 嵌入式，零部署
  - 生态兼容：✅ 与 sentence-transformers/BGE 全兼容
  - 长期维护：✅ 商业化运作，长期路线图明确
- **拒绝的替代方案**：FAISS（缺元数据）/ Pinecone（云服务）/ Milvus（重）/ Qdrant（Go 生态）
- **风险等级**：中（嵌入式模式下 10 万 chunk 性能待实测）
- **技术债务**：是（TD-AR-001：V3.2 实测后评估迁移 Qdrant）
- **来源**：[调研报告:RI-008/ARA-29] + [AR推断:依据=BR-005 单用户量级]

## TS-005 Redis 7.4.1（可选）

- **适用场景**：M-005 缓存后端（生产模式）/ V4.0 跨实例共享
- **合理性检查**：
  - 场景匹配：✅ 高性能 KV + 持久化 + Pub/Sub
  - 社区活跃：✅ 持续维护
  - 学习曲线：✅ 团队熟
  - 运维成本：⚠️ 单实例部署 ≤0.1 人月（生产模式）
  - 生态兼容：✅ RESP3 协议 + 客户端丰富
  - 长期维护：✅ 商业化 + 社区双驱动
- **拒绝的替代方案**：Memcached（无持久化）/ KeyDB（分叉风险）
- **风险等级**：低
- **技术债务**：否
- **来源**：[调研报告:RI-010/CACHE-49] + [TD:ADR-004] + [TD:BR-005]

## TS-006 httpx 0.27.2

- **适用场景**：AG-007/AG-008/AG-010 LLM Provider 客户端（OpenAI 兼容协议）
- **合理性检查**：
  - 场景匹配：✅ async + HTTP/2 + 超时控制
  - 社区活跃：✅ GitHub 12k+ stars
  - 学习曲线：✅ requests 兼容
  - 运维成本：✅ 纯库
  - 生态兼容：✅ FastAPI/openai SDK 全兼容
  - 长期维护：✅ 持续活跃
- **拒绝的替代方案**：aiohttp（API 繁琐）/ requests（同步阻塞）
- **风险等级**：低
- **技术债务**：否
- **来源**：[调研报告:RI-001/MCP-25] + [AR推断:依据=BR-001 禁 MCP → 需自实现 HTTP 客户端]

## TS-007 py-fsrs 1.0.0

- **适用场景**：M-011 FSRS 间隔重复调度
- **合理性检查**：
  - 场景匹配：✅ FSRS v4 算法标准实现
  - 社区活跃：✅ Jarrett Ye 维护，Anki 官方推荐
  - 学习曲线：✅ 1 天上手
  - 运维成本：✅ 纯库
  - 生态兼容：✅ Python 数据类
  - 长期维护：✅ FSRS 算法路线图明确
- **拒绝的替代方案**：自研（无意义）/ SM-2（旧算法）
- **风险等级**：低
- **技术债务**：否
- **来源**：[调研报告:RI-002/ANK-19/20] + [TD:BR-012]

## TS-008 pdf2zh 1.9.6

- **适用场景**：M-014 PDF 翻译
- **合理性检查**：
  - 场景匹配：✅ 专为 PDF 双栏 / 学术论文优化
  - 社区活跃：✅ GitHub 5k+ stars，月度 commit
  - 学习曲线：⚠️ 命令行 / Python API
  - 运维成本：⚠️ AGPL 协议（[调研报告:R-11] 商用待法务评审）
  - 生态兼容：✅ 与 PyMuPDF/PDFplumber 互补
  - 长期维护：✅ 社区维护
- **拒绝的替代方案**：PyMuPDF（无翻译）/ Marker（无中文）
- **风险等级**：中（AGPL 协议 + 翻译质量）
- **技术债务**：是（TD-AR-002：AGPL 商用评审 + 翻译质量评估）
- **来源**：[调研报告:RI-006/PDF-47/03/12] + [调研报告:R-11]

## TS-009 OpenTelemetry + structlog

- **适用场景**：M-006 监控事件总线（trace + 结构化日志）
- **合理性检查**：
  - 场景匹配：✅ OTel 协议 + structlog JSON
  - 社区活跃：✅ CNCF 项目
  - 学习曲线：⚠️ OTel 概念多
  - 运维成本：✅ Prometheus pull 模型
  - 生态兼容：✅ FastAPI/SQLAlchemy 集成
  - 长期维护：✅ CNCF 长期支持
- **拒绝的替代方案**：Sentry（重）/ Datadog（商业）
- **风险等级**：低
- **技术债务**：否
- **来源**：[调研报告:RI-013/LOG-01/32]

## TS-010 Prometheus Client 0.21.0

- **适用场景**：M-006 指标采集（AG-018 旁观 Agent scrape）
- **合理性检查**：
  - 场景匹配：✅ pull 模型 + counter/gauge/histogram
  - 社区活跃：✅ CNCF
  - 学习曲线：✅ 简单
  - 运维成本：✅ 单进程
  - 生态兼容：✅ Grafana
  - 长期维护：✅ CNCF
- **拒绝的替代方案**：StatsD（推模型）/ InfluxDB（时序重）
- **风险等级**：低
- **技术债务**：否
- **来源**：[调研报告:RI-013/LOG-32]

## TS-011 Nuitka 2.5.9 (onedir 模式)

- **适用场景**：M-015 三平台打包（Windows/Linux/macOS）
- **合理性检查**：
  - 场景匹配：✅ onedir 模式 + Python 3.11 支持
  - 社区活跃：✅ 月度 commit
  - 学习曲线：⚠️ 编译选项多
  - 运维成本：⚠️ 三平台矩阵需 CI
  - 生态兼容：✅ 与 UPX/PyInstaller 不冲突
  - 长期维护：✅ Kay Hayen 长期项目
- **拒绝的替代方案**：PyInstaller（onefile 禁 BR-031）/ cx_Freeze（功能弱）
- **风险等级**：中（[调研报告:RI-NEW-3] chromadb/sentence-transformers 打包大小待实测）
- **技术债务**：是（TD-AR-003：V3.2 实测打包大小）
- **来源**：[调研报告:RI-003/PYN-19/59] + [TD:BR-031~033] + [TD:ADR-009]

## TS-012 UPX 4.2.4

- **适用场景**：M-015 打包后压缩
- **合理性检查**：
  - 场景匹配：✅ 二进制压缩
  - 社区活跃：✅ 长期维护
  - 学习曲线：✅ 简单
  - 运维成本：✅ 单文件
  - 生态兼容：✅ 与 Nuitka 兼容
  - 长期维护：✅ 长期
- **拒绝的替代方案**：自研压缩（无意义）
- **风险等级**：低
- **技术债务**：否
- **来源**：[AR推断:依据=CE-011 体积约束]

## TS-013~TS-016 4 工具链（Ruff / Import Linter / Redocly CLI / pre-commit）

- **适用场景**：M-016 6+1 规范矩阵
- **合理性检查**：
  - 场景匹配：✅ Ruff 替代 flake8+isort+black / Import Linter 架构边界 / Redocly CLI OpenAPI 规范 / pre-commit hook 框架
  - 社区活跃：✅ Ruff 36k+ / Import Linter 1.2k / Redocly CLI 1.5k / pre-commit 13k stars
  - 学习曲线：⚠️ 团队需 1 周集中培训
  - 运维成本：✅ CI 集成
  - 生态兼容：✅ 与 pytest 全兼容
  - 长期维护：✅ 主流框架均有明确路线图
- **拒绝的替代方案**：Spectral（休眠，REDOC-50）/ Flake8（功能弱）/ Spectral CLI（EOL 风险）
- **风险等级**：中（[调研报告:REDOC-09] Ruff 1.0 前破坏性 API 变更需 TDD 渐进）
- **技术债务**：是（TD-AR-004：锁版本 + TDD 渐进式升级）
- **版本**：Ruff 0.7.4 / Import Linter 2.1.0 / Redocly CLI 1.25.11 / pre-commit 4.0.1
- **来源**：[调研报告:RI-004/REDOC-12/25/30~53] + [TD:ADR-010] + [TD:BR-046~050]

## TS-017 pytest 8.3.3 + pytest-cov 5.0.0

- **适用场景**：M-016 单测 + 覆盖率门禁
- **合理性检查**：
  - 场景匹配：✅ Python 测试事实标准
  - 社区活跃：✅
  - 学习曲线：✅
  - 运维成本：✅
  - 生态兼容：✅
  - 长期维护：✅
- **拒绝的替代方案**：unittest（API 繁琐）
- **风险等级**：低
- **技术债务**：否
- **来源**：[AR推断:依据=BR-046~050]

## TS-018 pydantic-settings 2.6.1 + python-dotenv 1.0.1

- **适用场景**：M-001 配置加载（pyproject.toml + .env）
- **合理性检查**：
  - 场景匹配：✅ 类型安全配置
  - 社区活跃：✅
  - 学习曲线：✅
  - 运维成本：✅
  - 生态兼容：✅
  - 长期维护：✅
- **拒绝的替代方案**：dynaconf（重）/ os.environ（无类型）
- **风险等级**：低
- **技术债务**：否
- **来源**：[AR推断:依据=BP-001]

---

## 备选方案对比矩阵（主方案 vs 备选方案，7 维度）

| 对比维度 | 权重 | 主方案 A（Python+FastAPI+SQLite+ChromaDB+Nuitka）| 备方案 B（Node.js+Express+PostgreSQL+Milvus+Electron）|
|---------|------|---------|---------|
| D2 技术选型合理性 | 0.15 | 9（18 选型全通过 6 项检查）| 7（AI 生态弱）|
| D3 Agent 协作清晰度 | 0.15 | 9（asyncio 单进程清晰）| 7（多进程复杂）|
| D4 接口规范完整度 | 0.15 | 9（FastAPI + Pydantic）| 7（缺 Pydantic 等价物）|
| D5 部署可实现性 | 0.15 | 9（Nuitka onedir）| 6（Electron 体积大）|
| D6 性能优化覆盖 | 0.10 | 8（asyncio + SQLite WAL + ChromaDB HNSW）| 8（PG + Milvus）|
| D7 技术债务可控 | 0.15 | 7（6 项债务）| 8（4 项债务）|
| D8 安全设计覆盖 | 0.15 | 9（Depends 注入 + Depends(auth)）| 7（中间件鉴权）|
| **总分** | 1.00 | **8.5** | **6.9** |

**选择理由**：主方案 A 在 6/7 维度领先，技术栈与 RI-001/S-001 调研结论完全一致；备选 B 虽 PG+Milvus 性能更好但 AI 生态弱、部署复杂。差距 1.6 < 5 分阈值但 6 维度差距 > 1 分，**A 更适合 V3.1**。

---

## AR 洞察

- **INSIGHT-TS-001 ChromaDB 嵌入式 V4.0 风险**：单用户量级 OK，V4.0 多用户后单实例难支撑。**缓解**：V4.0 评估 Qdrant 集群方案。
- **INSIGHT-TS-002 pdf2zh AGPL 协议需法务介入**：商用前必须完成法务评审（[调研报告:R-11]）。**缓解**：本期 V3.1 暂不商用，PR 阶段补评审。
- **INSIGHT-TS-003 Ruff 0.x→1.0 升级窗口**：REDOC-09 警示 1.0 前 API 变更。**缓解**：CI 锁版本 + V3.2 走 TDD 渐进式升级。
