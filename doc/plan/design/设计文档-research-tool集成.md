# 设计文档：research-tool 深度集成

> 涉及模块：`backend/engines/knowledge/`、`backend/pipeline/`、`backend/rag/`、`backend/engines/tutoring/`
> 外部依赖：`C:/Users/yhn/Desktop/调研/research-tool/`（本地路径依赖，已有）

## 背景

当前 AI-Tutor 已通过 `research_adapter.py` 浅层集成 research-tool：仅调用 `collect + clean` 两阶段做 web 资料采集。
但 research-tool 的完整能力远未利用：

| research-tool 能力 | 当前集成 | 应集成 |
|-------------------|---------|--------|
| Collect（10 源搜索 + 抓取） | ✅ 浅层 | ✅ 深度 |
| Deepen（反偏差深挖/画像注入/时间线回溯） | ❌ 未用 | ✅ 用于知识缺口补全 |
| Clean（去噪/去重/相关性过滤） | ✅ 浅层 | ✅ 深度 |
| Extract（实体/关系抽取） | ❌ 未用 | ✅ 用于 KG 自动构建 |
| Organize（知识树构建） | ❌ 未用 | ✅ 用于 KG 自动构建 |
| Report（报告生成） | ❌ 未用 | 🟡 可选 |
| Backward（反向传播修正） | ❌ 未用 | ✅ 用于 KG 质量迭代 |
| PDF 摄取 | ❌ 未用 | ✅ 替代自有 pdf_parser |
| P1 两阶段锚定/去锚 | ❌ 未用 | ✅ 用于精确检索 |
| P2 deep-search / 时间窗口 | ❌ 未用 | ✅ 用于 Agentic RAG |

## 目标

1. **资料采集**：PDF/网页/视频 全部走 research-tool 管线（替代自有 acquisition_adapter）
2. **KG 自动构建**：用 research-tool 的 Extract（实体/关系抽取）+ Organize（知识树）→ 直接生成 KG 初稿
3. **Agentic RAG**：用 research-tool 的 10 源搜索 + Deepen 多视角深挖作为检索后端
4. **KG 质量迭代**：用 Backward 反向传播（稀疏节点→修正查询→重采）自动补全 KG 缺口
5. **事实核查**：FactChecker 用 research-tool 做外部交叉验证

## 方案

### 1. 采集层统一：全部走 research-tool Pipeline

```
用户拖入 PDF / 输入 URL / 粘贴主题
          │
          ▼
┌──────────────────────────────────────┐
│        research-tool Pipeline         │
│                                       │
│  file → Collect(PDF摄入)              │
│  web  → Collect(10源搜索) → Deepen    │
│         → Clean(去噪/去重/相关性)      │
│         → Extract(实体/关系)           │
│  video→ Collect(yt-dlp+whisper, 待实现)│
│                                       │
│  输出: clean/*.md + extracted/*.json  │
└──────────────────┬───────────────────┘
                   │
                   ▼
         AI-Tutor KG Builder
         (消费 clean/ 正文 + extracted/ 三元组)
```

**关键变更**：废弃 `acquisition_adapter.py` 的自有文件处理，统一委托 research-tool：
- `_acquire_file()` → research-tool `PdfIngestor`（PDF→文本 + 可选翻译）
- `_acquire_web()` → research-tool `Collector + Cleaner`（已有，但缺 Deepen 和相关性过滤）
- `_acquire_video()` → 仍保留自身实现（research-tool 暂无 video 源）

### 2. KG 自动构建：从 research-tool 知识树到 KG

```
research-tool Extract Stage
  → extracted/entities.json     (实体列表 + 类型)
  → extracted/relations.json    (三元组: 头实体, 关系, 尾实体)
  → extracted/triples.json      (备用格式)

research-tool Organize Stage
  → tree/00-主表.md              (知识树索引)
  → tree/01-概念分类.md          (按类别组织的知识节点)
  → tree/02-关系网络.md          (概念间关系)

                    ↓ AI-Tutor 消费 ↓

KG Builder 新增模式: depth="auto"
  1. 读取 extracted/ → 直接映射为 Concept + Relation
  2. 读取 tree/ → 映射为章节骨架
  3. LLM 交叉验证 + 消歧 → 最终 KG
```

### 3. Agentic RAG：research-tool 作为检索后端

```
RAGAgent.search(query)
  │
  ├── 1. 本地 KG 检索（双路：向量 + 关键词）
  │
  ├── 2. research-tool Collector.search_only(query)
  │      └── 10 源并行搜索 → 去重 → top N
  │
  ├── 3. 覆盖率评估（LLM）
  │      └── 不足 70%?
  │           ├── research-tool Deepen（缺口/矛盾补搜）
  │           └── P1 去锚查询（core + facets）
  │
  └── 4. 精排 + KG 关联
```

### 4. KG 质量迭代：Backward 反向传播

```
初始 KG 构建完成
  │
  ▼
research-tool Backward
  ├── 评估 KG 节点"稀疏度"（引用来源 < 阈值 → 稀疏节点）
  ├── LLM 生成修正查询（针对稀疏概念/矛盾概念）
  ├── 追加检索 → 追加 raw/ → 重跑 clean/extract/organize
  └── 最多 N 轮（默认 2 轮）
  │
  ▼
AI-Tutor diff_kg → update_kg（版本化更新）
```

### 5. FactChecker：外部交叉验证

```python
class FactChecker:
    def verify_external(self, claim: str) -> FactCheckResult:
        # 用 research-tool 做外部搜索确认
        from research_tool import Collector, CollectorConfig
        collector = Collector(CollectorConfig(search_engines=["web", "wikipedia"]))
        hits = await collector.search_only(claim)
        # 交叉比对：搜索结果是否支持该陈述
        return self._cross_check(claim, hits)
```

## 影响范围

| 文件 | 变更 |
|------|------|
| `backend/engines/knowledge/acquisition_adapter.py` | 重写：全部委托 research-tool |
| `backend/engines/knowledge/kg_builder.py` | 新增 `depth="auto"` 模式 |
| `backend/engines/knowledge/kg_full.py` | 消费 research-tool 的 extracted/ 输出 |
| `backend/rag/agent.py` | 集成 research-tool 检索后端 |
| `backend/engines/tutoring/fact_checker.py` | 集成 research-tool 外部验证 |
| `backend/pipeline/` | 精简：清洗/结构化由 research-tool 完成 |
| `pyproject.toml` | research-tool 从 optional → 核心依赖 |

## 风险

| 风险 | 缓解 |
|------|------|
| research-tool 不稳定导致 AI-Tutor 不可用 | research-tool 失败时回退到自有简化实现（保留旧 acquisition_adapter 作为 fallback） |
| research-tool 的 extract/organize 质量不如 AI-Tutor 的 LLM 富化 | `depth="auto"` 模式先用 research-tool 产出草稿 → AI-Tutor 的 concept/full 做二次富化 |
| 两套代码的 LLM 调用叠加导致 token 消耗翻倍 | research-tool 和 AI-Tutor 共享 LLM provider 实例 + 共享缓存层 |
| 两个项目的版本不同步 | research-tool 固定为本地路径依赖（`editable = true`），AI-Tutor v2 要求特定版本 |
