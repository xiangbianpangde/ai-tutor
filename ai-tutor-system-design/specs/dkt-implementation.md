# DKT 模型实现方案

> 深度学习知识追踪（Deep Knowledge Tracing）的具体实现、训练数据和冷启动策略  
> 注：DKT 是 L5 的增强组件，非 Phase 1 必做。BKT 兜底即可。

---

## 一、模型选型

### 推荐：PyTorch + 简化 DKT 变体

不使用原版 LSTM-DKT（需要大量训练数据），使用 **DKT+ （带特征增强的轻量变体）**：

```
输入层: concept_embedding(64d) + interaction_sequence(最近20次)
编码器: 2层 GRU (hidden=128)  ← 比LSTM更快，效果相近
输出层: Dense(128) → Dense(64) → Dense(1, sigmoid)
输出: p(correct | concept, history)
```

### 为什么不选其他方案

| 方案 | 拒绝原因 |
|------|---------|
| 原版 LSTM-DKT | 需要 >10000 学生数据才收敛 |
| Transformer-DKT | 计算开销大，单用户场景过度设计 |
| sklearn 纯规则 | 无法捕捉序列模式 |
| 纯 BKT | 已有（Phase 1），BKT+DKT 互补 |

### DKT 与 BKT 的分工

```
BKT (Phase 1, 必做):
  - 每个概念独立建模
  - 可解释（p_learn/p_guess/p_slip）
  - 不需要训练数据，贝叶斯更新
  - 用于: 实时教学反馈、"为什么这个学生不会"的解释

DKT (Phase 3, 增强):
  - 跨概念联合建模（懂得导数的学生 → 积分也更容易）
  - 预测 "下一个交互的正确率"
  - 需要训练数据
  - 用于: 预测最佳下一步、检测异常答题模式（当DKT和BKT分歧 >0.2）
```

---

## 二、训练数据

### 数据来源

```
训练数据 = 同科目其他用户的历史交互序列
每一条样本:
  {
    "user_id": "...",
    "interaction_sequence": [
      {"concept_id": "...", "correct": true, "response_time_sec": 12.5},
      {"concept_id": "...", "correct": false, "response_time_sec": 25.0},
      ...  # 最近20次交互
    ],
    "target_concept_id": "...",
    "target_correct": true,   # label
  }
```

### 冷启动方案（无其他用户数据时）

```
冷启动三个梯队:

Tier 1 (零数据): 用 BKT 的 p_mastery 初始化 DKT 的隐状态
  - BKT 运行 3 次更新后 → 为每个概念产出 p_mastery
  - 用 p_mastery 构造伪交互序列 → 预训练 DKT（自监督）
  - 效果: DKT 初始预测 ≈ BKT，但能捕捉跨概念模式

Tier 2 (有 1 个用户的 50+ 交互): 
  - 用该用户的 BKT 参数生成 1000 条伪标注数据
  - 微调 DKT
  - 效果: 对该用户个性化

Tier 3 (有 ≥10 个用户):
  - 用真实交互数据训练
  - 跨用户泛化
```

### 伪标注数据生成（Tier 1/2）

```python
def generate_pseudo_labels(bkt_params: Dict[str, BKTParams], 
                          kg: KnowledgeGraph,
                          n_samples: int = 1000) -> List[TrainingSample]:
    """
    对每个概念:
    - 用 BKT p_mastery 作为 ground-truth
    - 采样交互序列: p_mastery > 0.8 → 正确(0.85概率)
    - 引入噪声: 10% 的标签翻转（模拟 BKT p_guess/p_slip）
    """
    samples = []
    for _ in range(n_samples):
        concept = random.choice(list(kg.nodes.keys()))
        bkt = bkt_params[concept]
        
        # 用BKT参数生成真实标签
        if random.random() < bkt.p_mastery:
            correct = random.random() > bkt.p_slip  # 会了但可能犯错
        else:
            correct = random.random() < bkt.p_guess  # 不会但可能猜对
        
        # 构造历史序列（同类概念的正确率与当前概念一致）
        history = generate_history_for_concept(concept, bkt.p_mastery, kg)
        
        samples.append({
            "history": history,
            "target_concept_id": concept,
            "target_correct": correct,
        })
    return samples
```

---

## 三、模型架构（具体代码骨架）

```python
# ai-tutor/servers/tutoring_mcp/dkt_model.py

import torch
import torch.nn as nn

class DKTModel(nn.Module):
    def __init__(self, 
                 n_concepts: int,           # KG 中概念总数
                 concept_embed_dim: int = 64,
                 hidden_dim: int = 128,
                 n_layers: int = 2):
        super().__init__()
        self.concept_embedding = nn.Embedding(n_concepts, concept_embed_dim)
        self.gru = nn.GRU(
            input_size=concept_embed_dim + 2,  # embedding + correct + response_time
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
        )
        self.output = nn.Sequential(
            nn.Linear(hidden_dim + concept_embed_dim, 64),  # + target_concept_embed
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )
    
    def forward(self, 
                history_concept_ids: torch.Tensor,    # (batch, seq_len)
                history_correct: torch.Tensor,         # (batch, seq_len)
                history_rt: torch.Tensor,              # (batch, seq_len) normalized
                target_concept_id: torch.Tensor,       # (batch,)
                ) -> torch.Tensor:                     # (batch, 1) → p(correct)
        # Embed history concepts
        hist_emb = self.concept_embedding(history_concept_ids)  # (B, S, 64)
        
        # Concatenate features
        correct_feat = history_correct.unsqueeze(-1)            # (B, S, 1)
        rt_feat = history_rt.unsqueeze(-1)                      # (B, S, 1)
        gru_input = torch.cat([hist_emb, correct_feat, rt_feat], dim=-1)  # (B, S, 66)
        
        # GRU encode
        _, h_n = self.gru(gru_input)                   # h_n: (2, B, 128)
        hidden = h_n[-1]                                # (B, 128)
        
        # Target concept embed
        target_emb = self.concept_embedding(target_concept_id)  # (B, 64)
        
        # Predict
        combined = torch.cat([hidden, target_emb], dim=-1)      # (B, 192)
        return self.output(combined).squeeze(-1)                # (B,)
```

### 模型文件大小

```
概念数 800, embed_dim=64, hidden=128, 2层GRU
参数量: ~100K
模型文件: < 2MB
单次推理: < 5ms (CPU)
```

---

## 四、训练策略

### Phase 3 的训练流程

```python
# 1. 冷启动检查
if n_users < 10:
    # Tier 1/2: 用 BKT 参数生成伪标注数据
    train_data = generate_pseudo_labels(bkt_params, kg, n_samples=2000)
else:
    # Tier 3: 用真实数据
    train_data = load_real_interactions(subject_id)

# 2. 训练
model = DKTModel(n_concepts=len(kg.nodes))
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
criterion = nn.BCELoss()

for epoch in range(50):
    for batch in dataloader:
        pred = model(...)
        loss = criterion(pred, batch.target_correct)
        loss.backward()
        optimizer.step()

# 3. 验证
val_auc = evaluate_auc(model, val_data)
if val_auc < 0.65:
    # 数据不足，DKT 不可靠 → 纯BKT模式
    model = None

# 4. 保存
torch.save(model.state_dict(), f"models/dkt_{subject_id}_{user_id}.pt")
```

### 增量更新

```python
# 每收集 50 个新交互 → 微调
def online_update(model, new_interactions):
    """
    用新交互做 5 个 epoch 的 fine-tuning
    学习率降低到 0.0001
    防止灾难性遗忘: Elastic Weight Consolidation (EWC) 正则化 ✓
    """
```

---

## 五、部署模式

| 模式 | 场景 | 依赖 |
|------|------|------|
| **纯 BKT** | Phase 1-2, 零用户 | 无 |
| **BKT + 伪标注 DKT** | Phase 3, 单用户 50+ 交互 | PyTorch CPU |
| **BKT + 真实训练 DKT** | Phase 3+, 多用户 | PyTorch + 训练数据 |
| **纯 BKT 兜底** | DKT 模型文件缺失 或 val_auc < 0.65 | 无 |

```python
class KnowledgeTracer:
    def __init__(self):
        self.bkt = BKTEngine()
        self.dkt_model: Optional[DKTModel] = None
        self.dkt_available = False
    
    def predict(self, user_id, concept_id, history) -> DKTOutput:
        bkt_result = self.bkt.predict(concept_id)
        
        if not self.dkt_available:
            return DKTOutput(
                mastery_prob=bkt_result.p_mastery,
                uncertainty=0.3,  # BKT的内在不准确性
                ...
            )
        
        dkt_result = self.dkt_model.predict(concept_id, history)
        
        # 分歧检测
        if abs(bkt_result.p_mastery - dkt_result.mastery_prob) > 0.2:
            # 标记异常，回退 BKT
            return DKTOutput(mastery_prob=bkt_result.p_mastery, ...)
        
        return dkt_result
```
