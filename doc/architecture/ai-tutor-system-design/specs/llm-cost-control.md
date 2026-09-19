# LLM 调用成本控制

> 目标：在保证 KG 质量和教学效果的前提下，最小化 LLM API 费用  
> 核心原则：能用规则就不用 LLM，能用 cheap model 就不用 strong model

---

## 一、LLM 调用场景与分级

### 按优先级分级

| 优先级 | 场景 | 允许的 model tier | 原因 |
|--------|------|-------------------|------|
| P0 | 教学交互中的 respond（回答学生） | strong | 直接面对学生，必须高质量 |
| P0 | 中断处理（理解学生打断意图） | strong | 必须准确理解 |
| P1 | 知识抽取（Concept Detector） | cheap | 可批量、可重试 |
| P1 | 关系抽取（Relation Extractor） | cheap | 可批量、可验证 |
| P2 | 题目生成（design_exercise prompt） | cheap | 有标准答案可验证 |
| P2 | 错误诊断（diagnose_error） | cheap | BKT 提供约束，LLM 辅助 |
| P3 | 课件内容润色（digest-mcp） | cheap 或 local | 非实时、可缓存 |
| P3 | 复习计划文本生成 | cheap | 结构性内容 |

### Model Tier 定义

```python
MODEL_TIERS = {
    "strong": {
        "deepseek": "deepseek-reasoner",     # 推理模式
        "openai": "gpt-4o",
    },
    "cheap": {
        "deepseek": "deepseek-chat",         # 性价比模式
        "openai": "gpt-4o-mini",
    },
    "local": {
        # 未来: 本地小模型 Qwen2.5-7B / Llama 3.2-8B
        # 通过 Ollama 部署，零成本
    },
}
```

---

## 二、批处理策略

### 知识抽取批处理

```python
# ❌ 低效: 每个 passage 发一次 LLM 调用
for passage in passages:
    concepts = llm.extract_concepts(passage)  # 800次调用

# ✅ 高效: 批量发送
BATCH_SIZE = 10  # 每批10个passage
for batch in chunks(passages, BATCH_SIZE):
    concepts_batch = llm.extract_concepts_batch(batch)  # 80次调用
    # prompt: "请从以下10段教材内容中提取所有数学概念: [passage1]...[passage10]"
    # 返回 JSON: [{"passage_id": 1, "concepts": [...]}, ...]
```

### 关系抽取批处理

```python
# 把候选概念对打包，一次 LLM 调用判断 20 对
# prompt: "判断以下概念对之间是否存在语义关系: 
#   (极限, 函数), (偏导数, 全微分), ...
#  返回每对的 relation_type 和 confidence"
```

### 成本对比（以高数下册为例）

| 方法 | LLM调用次数 | 输入 tokens (估) | 费用 (deepseek-chat) |
|------|------------|-----------------|---------------------|
| 逐篇抽取 | ~800 | 8M | ~$1.12 |
| 批处理(10篇/批) | ~80 | 6M | ~$0.84 |
| 批处理(10篇/批) + cheap model | ~80 | 6M | ~$0.11 |
| **批处理 + cache 复用** | **~40** | **3M** | **~$0.06** |

---

## 三、缓存策略

### 三级缓存

```
L1: 内存 LRU Cache (进程内)
  - 键: sha256(prompt)
  - TTL: 进程存活
  - 命中: 0ms

L2: SQLite Cache (本地持久)
  - 键: sha256(prompt + model)
  - TTL: 30天
  - 命中: ~5ms

L3: 语义去重 (跨会话)
  - "微分中值定理有哪些性质？" ≈ "中值定理的性质有哪些？"
  - 用 embedding 相似度 > 0.95 判定
```

### 缓存命中场景

```
- 同一个教材版本被多个用户使用 → L2 命中知识抽取结果
- 同一概念被多次查询 → L1 命中
- 相似的教学中断提问 → L3 命中
- 复习计划每日生成 → L2 命中（主题相同）
```

### 实现

```python
# ai-tutor/shared/llm_cache.py

import hashlib
import json
from functools import lru_cache

class LLMCache:
    def __init__(self, db_path: str = "data/llm_cache.db"):
        self.mem_cache = {}                    # L1
        self.db = sqlite3.connect(db_path)     # L2
        self._init_db()
    
    def get(self, prompt: str, model: str) -> Optional[str]:
        key = self._hash(prompt, model)
        # L1
        if key in self.mem_cache:
            return self.mem_cache[key]
        # L2
        row = self.db.execute("SELECT response FROM cache WHERE key=?", (key,)).fetchone()
        if row:
            self.mem_cache[key] = row[0]
            return row[0]
        return None
    
    def set(self, prompt: str, model: str, response: str):
        key = self._hash(prompt, model)
        self.mem_cache[key] = response
        self.db.execute(
            "INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?)",
            (key, prompt[:200], model, response, datetime.now()),
        )
    
    def _hash(self, prompt: str, model: str) -> str:
        return hashlib.sha256(f"{prompt}|{model}".encode()).hexdigest()
```

---

## 四、Token 预算机制

```python
class LLMBudget:
    """
    按用户 + 科目设置 token 预算。
    预算用完后，自动降级到更便宜的策略。
    """
    
    DAILY_BUDGET = 500_000    # 每日输入 token 上限
    MONTHLY_BUDGET = 10_000_000
    
    def check(self, user_id: str, estimated_input_tokens: int) -> BudgetResult:
        daily_used = self.get_daily_usage(user_id)
        if daily_used + estimated_input_tokens > self.DAILY_BUDGET:
            return BudgetResult(
                allowed=False,
                reason=f"今日token预算已用{daily_used}/{self.DAILY_BUDGET}",
                fallback="请明天继续，或升级到付费计划",
            )
        return BudgetResult(allowed=True)
    
    def suggest_model(self, priority: str, usage_pct: float) -> str:
        """
        根据使用率建议 model tier:
        usage < 50%: 按 priority 正常选择
        50% ≤ usage < 80%: P1/P2/P3 降级到 cheap
        usage ≥ 80%: 全部降级到 cheap，P3 拒绝
        """
```

---

## 五、具体场景的成本估计

### 完整学习一个科目（高数下册）的总 LLM 费用

| 阶段 | 调用场景 | 估计费用 (deepseek) |
|------|---------|-------------------|
| 知识抽取 | 800 passage × 10/批 × cheap | ~$0.10 |
| 关系抽取 | 3200 关系 / 20/批 × cheap | ~$0.08 |
| 概念 embedding | 本地模型 (all-MiniLM) | $0 |
| 教学 38h | ~200 次 respond (strong) + ~500 次 其他 (cheap) | ~$1.50 |
| 课件生成 | ~20 次 (cheap) | ~$0.02 |
| 复习计划 | ~5 次/天 (cheap, 缓存) | ~$0.01 |
| **总计** | | **~$1.71** |

使用 DeepSeek 的 cheapest tier，一个完整科目 < $2。

---

## 六、降级与熔断

```python
class LLMResilience:
    """
    外部 LLM API 不可用时的降级策略
    """
    
    def call_with_fallback(self, prompt: str, tier: str) -> str:
        providers = self.get_providers(tier)  # [deepseek, openai]
        
        for provider in providers:
            try:
                return self._call(provider, prompt)
            except RateLimitError:
                continue                       # 试下一个
            except TimeoutError:
                if provider != providers[-1]:
                    continue
                return self._get_cached_or_default(prompt)  # 全部超时 → 缓存 or 默认
        
        # 全部失败
        raise TutorError(
            code="ALL_LLM_PROVIDERS_DOWN",
            message="所有LLM服务暂时不可用，请稍后重试",
            retryable=True,
        )
    
    def _get_cached_or_default(self, prompt: str) -> str:
        """返回缓存的结果或硬编码的默认回复"""
        cached = cache.get(prompt, "default")
        if cached:
            return cached
        return "抱歉，我暂时无法处理这个请求。你的学习进度已保存。"
```
