# BDD 规格：07 — research-tool 深度集成

> 对应功能点：#7 | 设计文档：[设计文档-research-tool集成](../plan/design/设计文档-research-tool集成.md)

## 功能 1：采集层统一委托 research-tool

### 场景 1：网页资料采集走 research-tool 完整管线
- 前置条件：research-tool 已安装（`uv sync --extra research`）
- 操作步骤：
  1. 用户在知识库页面输入主题"ACP大模型应用认证"
  2. 选择"网页采集"
- 预期结果：
  - research-tool Collect(10源搜索) → Deepen(反偏差深挖) → Clean(去噪/去重/相关性过滤)
  - 返回 `clean/` 下干净的 Markdown 文件
  - 采集日志可见搜索源数量、去重前后篇数、相关性过滤剔除篇数

### 场景 2：research-tool 不可用时回退
- 前置条件：research-tool 未安装
- 操作步骤：
  1. 用户尝试网页采集
- 预期结果：提示"research-tool 未安装，使用内置简化采集"→ 走 DuckDuckGo 单源采集 + 基础清洗

### 场景 3：P1 两阶段锚定/去锚
- 前置条件：用户搜索人物"中南民族大学 康怡琳"
- 操作步骤：
  1. Phase1 用完整 topic 锚定 → Phase2 用 core "康怡琳" + facets 去锚搜索
- 预期结果：搜索结果包含南洋理工/Google Scholar 的海外来源（去锚突破了机构名限制）

---

## 功能 2：KG 自动构建（depth=auto）

### 场景 1：从 research-tool 知识树构建 KG
- 前置条件：research-tool 已完成 extract + organize 阶段
- 操作步骤：
  1. `POST /api/knowledge/subjects/{id}/graphs` body: `{"depth": "auto"}`
- 预期结果：
  - 自动消费 `extracted/entities.json` + `tree/00-主表.md`
  - 产出 KG（概念 ≥ 提取的实体数，边 ≥ 提取的关系数）
  - `review_kg` 审查通过（无孤岛/无环）

### 场景 2：auto 模式质量不如 concept 模式时自动升级
- 前置条件：auto 模式产出的 KG 置信度 < 0.5 的概念占比 > 30%
- 操作步骤：
  1. KG Builder 检测低质量
- 预期结果：自动触发 concept 模式 LLM 富化（用 AI-Tutor 的 enricher 补充定义/例子/误解）

---

## 功能 3：Agentic RAG 用 research-tool 做检索后端

### 场景 1：RAG 检索走 10 源搜索
- 前置条件：Agentic RAG 执行检索
- 操作步骤：
  1. 查询"vLLM 部署优化"
  2. RAGAgent.search() → 内部调用 research-tool Collector.search_only()
- 预期结果：结果来自 arxiv/openalex/semantic_scholar/web 等多源，去重后 ≥ 15 条

### 场景 2：Deepen 补全缺口
- 前置条件：初检覆盖率 45%
- 操作步骤：
  1. RAG 触发深入检索
  2. 调用 research-tool Deepen（缺口检测 + 矛盾检测 + 补搜）
- 预期结果：最终覆盖率 ≥ 70%

---

## 功能 4：KG 质量迭代（Backward 反向传播）

### 场景 1：自动补全稀疏概念
- 前置条件：KG 中某概念仅 1 个来源引用
- 操作步骤：
  1. Backward 检测到稀疏节点 → LLM 生成修正查询
  2. Collector 重搜 → Cleaner 重洗 → Organizer 重组织
  3. diff_kg → update_kg(versioned) 更新 KG
- 预期结果：稀疏概念的来源数从 1 → ≥ 3

---

## 功能 5：FactChecker 外部验证

### 场景 1：教学陈述与外部搜索结果交叉验证
- 前置条件：LLM 生成了教学讲解
- 操作步骤：
  1. FactChecker 提取关键陈述 → research-tool 搜索
  2. 搜索结果与陈述交叉比对
- 预期结果：高置信度矛盾时拦截并替换
