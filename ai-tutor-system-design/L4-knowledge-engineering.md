# L4 知识工程引擎

> 职责：多源知识采集、深层语义抽取、多源冲突融合、知识推理、知识版本演化  
> 输入：PDF/视频/网页/教材  
> 输出：结构化知识图谱 + 知识版本仓库

---

## 1. 核心数据模型：知识元组

### 1.1 概念节点

```python
Concept = TypedDict('Concept', {
    'id': str,                       # 全局唯一 ID，如 "gaoshu-v8:1.2.3:limit_epsilon_delta"
    'names': List[str],              # 多语言名称列表
    'category': Literal['definition', 'theorem', 'formula', 'method', 'property', 'axiom', 'lemma', 'corollary'],
    'definition': str,               # 核心定义文本
    'informal_description': str,     # 通俗解释
    'attributes': Dict[str, Any],    # 非定义属性
    'classification': {              # 分类学信息
        'bloom_level': Literal['remember', 'understand', 'apply', 'analyze', 'evaluate', 'create'],
        'abstract_level': float,     # 0.0(完全具体) ~ 1.0(高度抽象)
        'domain': str,               # "高等数学/极限论"
        'cross_domain_tags': List[str],  # "线性代数/向量", "物理/运动学"
    },
    'difficulty': {                  # 认知复杂度向量
        'prereq_count': int,         # 前置概念数量
        'prereq_max_depth': int,     # 最长前置链深度
        'formula_density': float,    # 单位文本公式数量
        'coupling': float,           # 与其他概念的耦合度
        'cognitive_load_estimate': float,   # 预估认知负荷
        'typical_learning_time_min': int,   # 典型学习时间（分钟）
    },
    'examples': List[Example],       # 正例
    'counter_examples': List[Example],  # 反例
    'common_misconceptions': List[str],  # 常见误解
    'linguistic_signals': {          # 语言学特征（用于摘要/语义搜索）
        'keywords': List[str],
        'embedding': Optional[List[float]],  # 768-dim concept embedding
    },
    'sources': List[SourceRef],      # 出处（教材页码、视频时间戳等）
    'confidence': float,             # 提取置信度
})
```

### 1.2 12 种语义关系

```python
SemanticRelation = Literal[
    'is_a',                 # A 是 B 的子类（极限→函数极限）
    'part_of',              # A 是 B 的组成部分（偏导数→全微分）
    'prerequisite_strong',  # 不会 A 则 B 绝对无法理解（函数→极限→导数）
    'prerequisite_weak',    # 不会 A 则 B 较难理解但不是绝对
    'analogous_to',         # A 与 B 类比（多元极限↔一元极限）
    'contradicts',          # A 与 B 部分矛盾（来源冲突）
    'generalizes',          # A 是 B 的推广（多元函数→一元函数）
    'instantiates',         # A 是 B 的特例
    'proves',               # A 定理用于证明 B
    'computed_from',        # B 公式由 A 推导（泰勒展开←导数定义）
    'common_pitfall',       # A 概念常引起对 B 的误解
    'historical_origin',    # A 概念从 B 演化而来（历史脉络）
]

Relation = TypedDict('Relation', {
    'from_id': str,
    'to_id': str,
    'type': SemanticRelation,
    'weight': float,               # 关系强度 0.0~1.0
    'explanation': str,            # 为什么存在这个关系
    'sources': List[SourceRef],
    'confidence': float,
})
```

### 1.3 知识图谱版本

```python
KnowledgeGraph = TypedDict('KnowledgeGraph', {
    'kg_id': str,
    'subject_id': str,
    'version': str,                 # "v1.0", "v2.0-dual-credit-update"
    'created_at': datetime,
    'source_corpora': List[str],    # 使用的语料库 ID
    'node_count': int,
    'edge_count': int,
    'quality_report': QualityReport,
    'nodes': Dict[str, Concept],
    'edges': List[Relation],
    'embedding_matrix': Optional[ndarray],  # nodes × 768
})
```

---

## 2. 知识抽取流水线

```
原始 Markdown
  │
  ├──[1] Passage Splitter ─────────────────────── 语义段落切分
  │    输入: raw_md
  │    输出: List[Passage(chunk_id, content, type="definition|example|theorem|exercise")]
  │    算法: 启发式（标题层级、空行、数学公式块）+ LLM 边界校验
  │
  ├──[2] Concept Detector ─────────────────────── 概念识别
  │    输入: passage
  │    输出: List[ConceptCandidate]
  │    算法: 规则（"定义/定理/公式/称作/记为"模式匹配）+ LLM 抽取
  │    后处理: 同名消歧、指代消解（"该定理"→具体定理名）
  │
  ├──[3] Relation Extractor ───────────────────── 关系抽取
  │    输入: corpus + detected_concepts
  │    输出: List[Relation]
  │    算法: LLM 抽取 + 结构化约束验证
  │    验证: ① 边的两端节点必须在 detected_concepts 集中
  │          ② prerequisite_strong 不能形成有向环
  │          ③ 排除自环
  │
  ├──[4] Difficulty Scorer ────────────────────── 难度评分
  │    输入: concept + full_graph
  │    输出: DifficultyVector
  │    算法: 基于图特征的回归（前置数量、前置深度、公式密度、概念耦合度）
  │
  ├──[5] Embedding Indexer ────────────────────── 语义索引
  │    输入: concept.definition
  │    输出: embedding(768d)
  │    算法: 轻量 embedding 模型（如 all-MiniLM-L6-v2）或调用 LLM API
  │
  └──[6] Quality Gate ─────────────────────────── 质量门
       输入: full_graph
       检查规则:
       ① 无孤立节点（degree > 0）
       ② 无 prerequisite 循环
       ③ 章节覆盖率 ≥ 85%（每个章节至少 1 个概念）
       ④ 定义/定理/公式 类别分布合理
       ⑤ 每个概念有 ≥ 1 个示例（关键概念 > 3 个示例）
       ⑥ 每个概念有 ≥ 1 个语义关系
       不通过 → 标记问题 → 调用 LLM 修复 → 重入 Gate
```

---

## 3. 知识融合引擎

### 3.1 多源对齐

```python
def align_concepts(source_a: KnowledgeGraph, source_b: KnowledgeGraph) -> AlignmentMatrix:
    """
    返回: 对齐矩阵 M[i][j] ∈ {same, part_of, contradicts, unrelated}
    
    算法:
    1. 名称相似度: Levenshtein + 领域词典
    2. 定义相似度: embedding cosine similarity > 0.85 → 候选匹配
    3. LLM 最终判定: 对候选匹配做二分类
    """
```

### 3.2 冲突检测与仲裁

```python
Conflict = TypedDict('Conflict', {
    'type': Literal['contradictory_definition', 'reversed_prerequisite', 
                    'different_example', 'missing_relation'],
    'concept_a': str,
    'concept_b': str,
    'source_a': SourceRef,
    'source_b': SourceRef,
    'description': str,
    'resolution': Optional[str],   # 仲裁结果
    'resolved_by': Literal['auto', 'manual'],
})

def detect_conflicts(merged_graph: KnowledgeGraph) -> List[Conflict]:
    """
    检测模式:
    - 两个来源对同一概念的定义有本质不同
    - A来源: A→B(prerequisite) vs B来源: B→A(prerequisite)
    - 一个来源有某关系，另一个缺失
    """
    
def resolve_conflicts(conflicts: List[Conflict], strategy='auto') -> List[Conflict]:
    """
    auto 策略:
    - 教材来源 > 视频来源 > 网页来源（来源权重）
    - 定义冲突: 取两个定义的交集部分，标记差异供用户查看
    - prerequisite 冲突: 保守（两个方向都保留，标记为弱依赖）
    
    manual 策略:
    - 对每个 conflict 调用 LLM 生成裁决建议
    - 封装为 MCP tool resolve_conflicts → 返回给用户决定
    """
```

---

## 4. KG 版本管理

```
knowledge_graph_store/
├── gaoshu-v8/
│   ├── v1.0/                       # 首次构建
│   │   ├── triples.jsonl           # 每行一个三元组 (JSONL)
│   │   ├── concepts.json           # 所有概念（含 embedding）
│   │   ├── graph.gml               # GML 格式图文件
│   │   ├── embeddings.npy          # 概念向量矩阵
│   │   └── manifest.json           # 构建参数、数据源、质量评分
│   ├── v2.0/                       # 增量更新（新教材版本）
│   │   ├── delta.json              # 仅变更：added/removed/modified
│   │   ├── triples.jsonl           # 全量快照
│   │   └── manifest.json
│   └── latest → v2.0/              # symlink
├── gaoshu-v9/
│   └── v1.0/
└── ...
```

### 增量更新算法

```python
def delta_update(old_kg: KnowledgeGraph, new_corpus: Corpus) -> Delta:
    """
    1. 对新 corpus 运行抽取流水线 → new_kg
    2. 概念对齐（名称 + embedding）
       - new 且 align=unrelated → added
       - 存在于 old 但不在 new → removed（可能，但标记而非删除）
       - aligned → modified（检测 attribute 变化）
    3. 关系对齐:
       - new 且两端都存在 → added
       - old 有 new 无 → removed（降权而非删除）
    4. 生成 delta.json + 全量快照
    """
```

---

## 5. MCP Tool 签名（L7 交互层使用）

详见 [L7-interaction-layer.md](./L7-interaction-layer.md) 中 `knowledge-mcp` 部分。

---

## 6. 实现路线

### Phase 1: 最小可用（3 周）

| 周 | 任务 |
|----|------|
| 1 | Passage Splitter + Concept Detector（规则版） |
| 2 | Relation Extractor + Difficulty Scorer + Quality Gate |
| 3 | Multi-source fusion（align + conflict detect）+ Versioned storage |

### Phase 2: 增强（后续）

- Concept Detector 升级 LLM 版
- Embedding-based 语义搜索
- 增量更新算法
- 自动冲突仲裁（LLM）
