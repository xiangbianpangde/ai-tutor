# 知识三元组 Schema

> 完整定义 L4 知识工程中知识图谱的存储格式  
> 文件格式：JSONL（每行一个三元组）+ concepts.json + embeddings.npy

---

## 一、三元组 JSONL 格式

每行一个 JSON 对象，表示一条语义关系：

```json
{"subject": "limit_definition", "predicate": "prerequisite_strong", "object": "function_concept", "weight": 0.95, "explanation": "理解极限必须先理解函数", "sources": [{"type": "textbook", "page": "P23", "text": "..."}], "confidence": 0.92, "version": "v1.0", "added_at": "2026-05-19T10:00:00Z"}
```

### 完整字段定义

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `subject` | string | ✅ | 主语概念 ID |
| `predicate` | string | ✅ | 关系类型（12选1） |
| `object` | string | ✅ | 宾语概念 ID |
| `weight` | float | ✅ | 关系强度 0.0~1.0 |
| `explanation` | string | ✅ | 人类可读的解释 |
| `sources` | array[SourceRef] | ✅ | 至少一个来源引用 |
| `confidence` | float | ✅ | 抽取置信度 0.0~1.0 |
| `version` | string | | 所属 KG 版本 |
| `added_at` | datetime | | 添加时间 |
| `deprecated` | boolean | | 标记为已弃用（不删除） |
| `superseded_by` | string | | 被哪个三元组替代 |

### 12 种 predicate 值

| Predicate | 符号 | 说明 | 示例 |
|-----------|------|------|------|
| `is_a` | A → B | A 是 B 的子类 | 函数极限 → 极限 |
| `part_of` | A → B | A 是 B 的组成部分 | 偏导数 → 全微分 |
| `prerequisite_strong` | A ⇒ B | 不会A则B绝对学不会 | 函数 → 极限 |
| `prerequisite_weak` | A ⇢ B | 不会A则B较难 | 集合论 → 函数 |
| `analogous_to` | A ↔ B | A 与 B 类比 | 多元极限 ↔ 一元极限 |
| `contradicts` | A ⊥ B | 来源间矛盾 | 教材A说 vs 视频B说 |
| `generalizes` | A ⊃ B | A 是 B 的推广 | 多元函数 ⊃ 一元函数 |
| `instantiates` | A ⊂ B | A 是 B 的特例 | 线性函数 ⊂ 函数 |
| `proves` | A ⊢ B | A 用于证明 B | 中值定理 ⊢ 泰勒定理 |
| `computed_from` | A → B | B 由 A 计算推导 | 泰勒展开 ← 导数定义 |
| `common_pitfall` | A ⚠ B | A 概念常见对 B 的误解 | 极限 → 连续性混淆 |
| `historical_origin` | A ← B | A 从 B 演化 | 极限 ← 无穷小分析 |

---

## 二、概念节点 JSON 格式

```json
{
  "id": "gaoshu-v8:2.1.1:limit_epsilon_delta",
  "names": ["极限的ε-δ定义", "limit ε-δ definition"],
  "category": "definition",
  "definition": "设函数f(x)在点x₀的某去心邻域内有定义...",
  "informal_description": "当x无限接近x₀时，f(x)的值无限接近某个确定的数A",
  "attributes": {
    "notation": "lim_{x→x₀} f(x) = A",
    "alternate_forms": ["数列极限定义", "海涅定理"],
    "domain_constraints": ["去心邻域", "f(x)在该邻域有定义"]
  },
  "classification": {
    "bloom_level": "understand",
    "abstract_level": 0.78,
    "domain": "高等数学/极限论",
    "cross_domain_tags": ["实分析", "拓扑学/连续性"]
  },
  "difficulty": {
    "prereq_count": 3,
    "prereq_max_depth": 2,
    "formula_density": 0.65,
    "coupling": 0.72,
    "cognitive_load_estimate": 0.68,
    "typical_learning_time_min": 15
  },
  "examples": [
    {"text": "证明 lim_{x→2} (3x+1) = 7", "type": "proof"},
    {"text": "f(x) = 1/x 在 x→0 时极限不存在", "type": "counterexample"}
  ],
  "counter_examples": [
    {"text": "f(x)=sin(1/x) 在 x→0 时振荡，极限不存在", "type": "pathological"}
  ],
  "common_misconceptions": [
    "极限值等于函数值（混淆极限与连续）",
    "极限过程必须从两边趋近（忽略单侧极限）"
  ],
  "linguistic_signals": {
    "keywords": ["ε-δ", "极限", "趋近", "去心邻域", "任意小"],
    "embedding": null
  },
  "sources": [
    {"type": "textbook", "ref": "同济高数v8", "page": "P23-P24", "text": "..."},
    {"type": "video", "ref": "B站宋浩高数", "timestamp": "02:15:30"}
  ],
  "confidence": 0.93
}
```

---

## 三、Knowledge Graph Manifest

```json
{
  "kg_id": "gaoshu-v8-kg-v1",
  "subject_id": "gaoshu-v8",
  "version": "v1.0",
  "created_at": "2026-05-19T10:45:00Z",
  "source_corpora": ["gaoshu-v8-yhn-20260519"],
  "build_params": {
    "depth": "full",
    "llm_model": "deepseek-chat",
    "embedding_model": "all-MiniLM-L6-v2",
    "quality_gate_passed": true
  },
  "stats": {
    "node_count": 847,
    "edge_count": 3247,
    "by_category": {"definition": 234, "theorem": 189, "formula": 203, "method": 145, "property": 76},
    "by_relation": {"prerequisite_strong": 890, "prerequisite_weak": 567, "is_a": 456, "computed_from": 321, "proves": 298, "analogous_to": 234, "generalizes": 189, "instantiates": 123, "part_of": 98, "common_pitfall": 45, "contradicts": 12, "historical_origin": 14}
  },
  "quality_report": {
    "overall": "pass",
    "chapter_coverage": 0.92,
    "isolated_nodes": 3,
    "cycles": 1,
    "avg_confidence": 0.87,
    "warnings": [
      "3个概念缺少示例: [taylor_remainder, riemann_sum, flux]",
      "1个依赖循环: multi_partial → partial_def → multi_function → multi_partial (已弱化)"
    ],
    "suggestions": [
      "考虑补充 taylor_remainder 的拉格朗日余项示例",
      "flux（通量）可能需要物理背景的类比例子"
    ]
  },
  "file_paths": {
    "triples": "data/knowledge_graphs/gaoshu-v8/v1.0/triples.jsonl",
    "concepts": "data/knowledge_graphs/gaoshu-v8/v1.0/concepts.json",
    "embeddings": "data/knowledge_graphs/gaoshu-v8/v1.0/embeddings.npy",
    "graph_gml": "data/knowledge_graphs/gaoshu-v8/v1.0/graph.gml",
    "graph_png": "data/knowledge_graphs/gaoshu-v8/v1.0/graph.png"
  }
}
```

---

## 四、Delta（增量更新）格式

```json
{
  "from_version": "v1.0",
  "to_version": "v2.0",
  "updated_at": "2026-06-15T14:00:00Z",
  "changes": {
    "added_nodes": [{...}, {...}],
    "removed_nodes": ["gaoshu-v8:3.4.2:deprecated_method"],
    "modified_nodes": [{...}],
    "added_edges": [{...}],
    "removed_edges": [{...}],
    "modified_edges": [{...}]
  },
  "summary": "新增8个概念（补充了习题课内容），移除1个已被替代的求解方法，修改变分法章节的概念关系",
  "breaking_changes": false
}
```

---

## 五、Corpus 语料库 Manifest

```json
{
  "corpus_id": "gaoshu-v8-yhn-20260519",
  "subject": "同济版高等数学下册",
  "version": "8th",
  "created_at": "2026-05-19T00:40:00Z",
  "sources": [
    {
      "type": "textbook",
      "format": "pdf",
      "original_file": "gaoshu_v8_scanned.pdf",
      "converted_file": "md/gaoshu_v8.md",
      "pages": 400,
      "language": "zh",
      "parser": "pdf2zh",
      "parser_version": "v1.9",
      "quality": {"formula_accuracy": 0.94, "text_accuracy": 0.97}
    },
    {
      "type": "video_transcript",
      "source_url": "https://www.bilibili.com/video/BV1...",
      "transcript_file": "md/video_transcript.md",
      "summary_file": "md/video_summary.md",
      "duration_min": 480,
      "language": "zh",
      "transcriber": "faster-whisper-base"
    }
  ],
  "toc": [...],
  "stats": {
    "total_chapters": 12,
    "total_sections": 86,
    "estimated_concepts": 847,
    "total_md_size_kb": 2847
  },
  "file_paths": {
    "raw": "data/corpora/gaoshu-v8-yhn-20260519/raw/",
    "md": "data/corpora/gaoshu-v8-yhn-20260519/md/",
    "normalized": "data/corpora/gaoshu-v8-yhn-20260519/normalized/"
  }
}
```
