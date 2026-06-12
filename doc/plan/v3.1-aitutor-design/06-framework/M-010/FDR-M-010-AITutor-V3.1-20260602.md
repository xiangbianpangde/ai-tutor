# 框架决策记录 (FDR) — M-010 费曼评分

> 作者: DD-M-010-20260602
> 来源标注: [DD-001:MD-010] + [DD-001:CS] + [DD-M-010 推断]

---

## FDR-M-010-001 评分结果使用 frozen dataclass 而非 Pydantic BaseModel

- **决策编号**：FDR-M-010-001
- **决策标题**：FeynmanScore / ParsedScore 采用 `@dataclass(frozen=True, slots=True)`
- **决策状态**：已接受
- **决策内容**：M-010 内部值对象（FeynmanScore / ParsedScore）使用标准库 dataclass 而非 Pydantic BaseModel
- **决策理由**：
  1. 这两类是模块内部不可变值对象，无需 Pydantic 的 schema 校验/JSON Schema 序列化能力
  2. dataclass + slots 内存占用比 BaseModel 减半，与 IC-002 P95 ≤5s 性能预算契合
  3. frozen=True 提供并发安全（不可变 = 线程安全）
- **拒绝的替代方案**：
  - **方案 B：Pydantic BaseModel** — 拒绝理由：跨进程 JSON 序列化对本模块无必要，且引入运行时校验开销 ~30μs/次，对单回合 5s 预算虽小但累积可观
- **影响范围**：scorer.py / parser.py 两文件 + 测试
- **相关 FDR**：无
- **来源标注**：[DD-001:CS 7 性能与并发] + [DD-M推断:依据=值对象语义]

---

## FDR-M-010-002 解析器三层容错并保留 fallback 不抛异常

- **决策编号**：FDR-M-010-002
- **决策标题**：ScoreParser 采用「JSON → Regex → fallback」三层，fallback 不抛异常
- **决策状态**：已接受
- **决策内容**：
  - 容错层 1：严格 JSON 解析
  - 容错层 2：正则提取（兼容 "score: N" / "评分: N"）
  - 容错层 3：fallback 固定返回 score=0 + DEFAULT_REASONING + strategy="fallback"
  - 三层全失败仍返回 ParsedScore（不抛异常），由调用方 Scorer 决定是否重试
- **决策理由**：
  1. MD-010 E01002 要求"重试 1 次"，将"是否重试"的决策权放在 Scorer 而非 Parser
  2. Parser 永远返回可用结果，避免双层异常处理复杂度
  3. strategy 字段提供可观测性，便于审计 LLM 输出质量
- **拒绝的替代方案**：
  - **方案 B：fallback 抛 ScoreParseError，由 Scorer catch 后兜底** — 拒绝理由：异常控制流复杂；strategy 字段无法保留可观测信息
- **影响范围**：parser.py（核心实现）+ scorer.py（重试逻辑）
- **相关 FDR**：FDR-M-010-003（degraded 字段）
- **来源标注**：[DD-001:MD-010 E01002] + [DD-M推断:依据=异常控制流最小化]

---

## FDR-M-010-003 FeynmanScore 新增 degraded 字段标记兜底

- **决策编号**：FDR-M-010-003
- **决策标题**：FeynmanScore 增加 `degraded: bool` 字段
- **决策状态**：已接受
- **决策内容**：FeynmanScore 在 [DD-001:MD-010] 隐含返回类型基础上增加 degraded 字段
- **决策理由**：
  1. IC-002 E00901 要求 M-009 在「LLM 评分失败」时走 FSM 兜底 10%
  2. 若仅返回 score=0，M-009 无法区分「真实 0 分」与「LLM 不可用兜底的 0 分」
  3. degraded=True 提供显式信号，M-009 据此决定是否触发 FSM 兜底
- **拒绝的替代方案**：
  - **方案 B：用 score=-1 表示兜底** — 拒绝理由：违反 score_range=(0, 5) 契约；类型不安全
  - **方案 C：抛 LLMUnavailableError 让 M-009 catch** — 拒绝理由：跨模块异常耦合；增加 M-009 负担
- **影响范围**：scorer.py FeynmanScore + 跨模块 API 协议（M-009 需识别该字段）
- **相关 FDR**：FDR-M-010-002
- **来源标注**：[DD-001:IC-002 E00901] + [DD-M推断:依据=显式信号优于隐式约定]

---

## FDR-M-010-004 Prompt 注入防御使用分隔符 + 转义双重保护

- **决策编号**：FDR-M-010-004
- **决策标题**：FeynmanPromptBuilder.\_sanitize 采用 USER_INPUT_DELIMITER 包裹 + 关键词转义
- **决策状态**：已接受
- **决策内容**：在 build() 中通过 _sanitize 对 user_answer 做两层防御
- **决策理由**：
  1. CS 8 安全规范要求用户输入必须校验/清洗
  2. LLM prompt injection 是 2025-2026 行业普遍威胁
  3. 单纯转义可被 unicode 变体绕过；单纯分隔符可被「忽略以上指令」语义绕过
- **拒绝的替代方案**：
  - **方案 B：仅做长度截断不清洗** — 拒绝理由：安全性不足
  - **方案 C：调用 LLM 做内容审核** — 拒绝理由：引入额外 LLM 调用开销，违反 IC-002 性能预算
- **影响范围**：prompt.py（核心）+ test_prompt.py（专项测试）
- **相关 FDR**：无
- **来源标注**：[DD-001:CS 8] + [DD-M推断:依据=LLM 安全最佳实践]

---

## FDR-M-010-005 引入 build_feynman_scorer 工厂函数

- **决策编号**：FDR-M-010-005
- **决策标题**：在 `__init__.py` 暴露 `build_feynman_scorer` 工厂
- **决策状态**：已接受
- **决策内容**：除 re-export 三个类外，额外提供工厂函数封装依赖装配
- **决策理由**：
  1. MD-010 三类相互依赖（Scorer ← PromptBuilder + Parser），调用方装配繁琐
  2. M-009 作为下游不应感知 Strategy 内部装配细节（信息隐藏）
  3. 工厂函数便于在测试中替换为 mock 实例
- **拒绝的替代方案**：
  - **方案 B：要求 M-009 直接调用 FeynmanScorer(...)** — 拒绝理由：跨模块耦合内部结构
- **影响范围**：__init__.py
- **相关 FDR**：无
- **来源标注**：[DD-M推断:依据=信息隐藏 + DI 友好]

---

## FDR 统计

| 状态 | 数量 |
|------|------|
| 已接受 | 5 |
| 已拒绝 | 0 |
| 已取代 | 0 |
| **合计** | **5** |

**全部 5 条 FDR 均含明确决策内容 + 决策理由 + ≥1 个被拒绝的替代方案，符合 [soul 3.7 FDR 模板]。**

来源标注：[DD-001:MD-010] + [DD-001:CS] + [DD-001:IC-002] + [DD-M-010 推断]
