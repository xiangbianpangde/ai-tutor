# 框架决策记录（FDR）— M-013 长期记忆

> 模块编号: M-013
> 负责实例: DD-M-013
> 来源: [DD-001:FS-NNN/MD-013] + [DD-M推断:依据]

---

## FDR-013-001 引入 service.py 业务编排层

- **决策状态**：已接受
- **决策内容**：在 Repository/Extractor/LRU 之上引入 `service.py` 作为 Façade，统一对外暴露 IC-007 接口
- **决策理由**：
  - MD-013 定义 4 个核心函数（save_fact / query_facts / evict_lru / extract_facts），缺少统一入口
  - IC-007 action 路由（save/query/evict）需统一编排
  - 上游 M-002 API 层应仅依赖 service，不直接操作 Repository（Import Linter contract:3）
  - DDR-001 锁定 Repository + 编排层标准模式
- **拒绝的替代方案**：
  - 方案A：API 层直接调 Repository：违反 Import Linter contract:3 + 业务逻辑散落路由
  - 方案B：业务逻辑写在 Repository：违背 Repository 单一职责（DD推断:依据=Repository 模式）
- **影响范围**：service.py / test_service.py / M-002 API v1 路由
- **相关FDR**：无
- **来源标注**：[DD-001:MD-013] + [DD-001:CS-NNN contract:3] + [DD-M推断:依据=Façade 模式]

---

## FDR-013-002 Memory 实体采用 Pydantic v2 + frozen=True

- **决策状态**：已接受
- **决策内容**：Memory 实体使用 Pydantic v2 BaseModel + `ConfigDict(frozen=True, extra="forbid")`
- **决策理由**：
  - CS-NNN §3.4 强制 mypy strict + pydantic.mypy 插件
  - frozen=True 防止业务侧意外修改实体（DD-M推断:依据=实体不可变最佳实践）
  - extra="forbid" 严格匹配 IC-007 字段定义，防止 hallucination 字段
  - Pydantic v2 BaseModel 性能优于 dataclass（V3.1 性能基线）
- **拒绝的替代方案**：
  - 方案A：dataclass：缺少字段校验、不可与 pydantic.mypy 集成
  - 方案B：Mutable：违反实体不可变原则，audit 困难
- **影响范围**：models.py / test_models.py
- **相关FDR**：FDR-013-001
- **来源标注**：[DD-001:CS-NNN §3.4] + [DD-001:IC-007 字段定义] + [DD-M推断:依据=DDD 实体不可变]

---

## FDR-013-003 LRU 淘汰采用最旧 10% 阈值

- **决策状态**：已接受
- **决策内容**：LRUEviction.eviction_ratio 默认 0.1，一次淘汰最旧 10%
- **决策理由**：
  - MD-013 明确指定 `eviction_ratio=0.1`
  - 10% 阈值平衡淘汰效率与抖动（DD-M推断:依据=LRU 经典配置）
  - 触发条件：current >= max_capacity（默认 100_000）
- **拒绝的替代方案**：
  - 方案A：5%：淘汰频次过高，缓存命中率低
  - 方案B：20%：淘汰过于激进，丢失近期记忆
- **影响范围**：lru.py / test_lru.py
- **相关FDR**：无
- **来源标注**：[DD-001:MD-013 LRUEviction] + [DD-001:IC-007 E01302/E01303]

---

## FDR-013-004 测试覆盖单测 + 集成（5 测试文件，32 用例）

- **决策状态**：已接受
- **决策内容**：5 个测试文件 / 32 个用例 / Mock 策略：内存 SQLite + respx + 全 Mock
- **决策理由**：
  - MD-013 测试策略要求 14 用例（核心 5 + 边界 5 + 异常 4）
  - 实际框架扩展至 32 用例，覆盖更完整（DD-M推断:依据=覆盖率 ≥80% 强约束）
  - 测试文件镜像生产目录（test_models/test_repository/test_lru/test_extractor/test_service）
  - 集成测试由 M-002 API 层 + M-013 组合覆盖（test_memory_integration 暂留接口）
- **拒绝的替代方案**：
  - 方案A：合并为 1 个测试文件：违反单文件函数数 ≤ 20 + 测试可读性
  - 方案B：仅单测不集测：违反 IC-007 并发安全要求
- **影响范围**：tests/unit/test_memory/*
- **相关FDR**：无
- **来源标注**：[DD-001:MD-013 测试策略] + [DD-001:CS-NNN §6 测试规范]

---

## FDR-013-005 模块边界硬约束：仅操作 M-013 内文件

- **决策状态**：已接受
- **决策内容**：DD-M-013 实例仅可创建/修改 M-013 内文件，禁止触碰 M-001~M-012, M-014~M-017
- **决策理由**：
  - soul 4.7 D7=100 硬性约束，违规即判定失败
  - 多实例隔离协议：每个 DD-M 实例仅负责唯一模块
  - R28 红线：禁止跨模块操作
  - R30 红线：所有产出物含 M-NNN 标识
- **拒绝的替代方案**：
  - 方案A：跨模块直接 import：违反 Import Linter contract:3 + D7=100 约束
  - 方案B：自由发挥模块边界：违反 soul 一身份定义
- **影响范围**：所有产出物路径必须包含 M-013
- **相关FDR**：无
- **来源标注**：[soul 4.7 D7=100] + [soul R28/R29/R30 红线] + [DD-001:多实例隔离协议]

---

## FDR 状态汇总

| FDR 编号 | 状态 | 影响文件数 |
|---------|------|----------|
| FDR-013-001 | 已接受 | 3（service.py + test_service.py + M-002 路由预留） |
| FDR-013-002 | 已接受 | 2（models.py + test_models.py） |
| FDR-013-003 | 已接受 | 2（lru.py + test_lru.py） |
| FDR-013-004 | 已接受 | 5（tests/unit/test_memory/*） |
| FDR-013-005 | 已接受 | 全部（命名/路径约束） |

**FDR 覆盖率 = 5/5 = 100%**

---

## 来源标注

- [DD-001:FS-NNN] 文件结构规范
- [DD-001:MD-013] 模块细化方案
- [DD-001:IC-007] 接口契约
- [DD-001:CS-NNN] 代码风格指南
- [soul 4.13 FDR 模板]
- [DD-M推断:依据=Design Pattern 最佳实践 + Python 工程化]
