# 文件框架结构 — M-013 长期记忆

> 模块编号: M-013
> 模块名称: 长期记忆（Repository + LRU）
> 负责实例: DD-M-013
> 来源: [DD-001:FS-NNN/MD-013] + [DD-M推断:依据=FS-NNN 5项合规检查]

---

## 文件框架

```
src/aitutor/memory/                    ← [职责：M-013 长期记忆包]
├── __init__.py                        ← [职责：模块初始化，导出公共接口]
├── models.py                          ← [职责：数据模型定义，含类注释]
│   - [类注释] Memory
│   - [类注释] FactExtractionRequest
│   - [类注释] FactExtractionResult
│   - [类注释] MemoryQueryResult
│   - [类注释] LRUVictim
├── repository.py                      ← [职责：Repository 数据访问层]
│   - [类注释] MemoryRepository
│   - [函数注释] compute_content_hash
├── lru.py                             ← [职责：LRU 淘汰策略]
│   - [类注释] LRUEviction
│   - [函数注释] build_lru_evictor
├── extractor.py                       ← [职责：LLM 事实提取]
│   - [类注释] FactExtractor
└── service.py                         ← [职责：业务编排入口]
    - [类注释] MemoryService
    - [函数注释] build_memory_service

tests/unit/test_memory/                ← [职责：M-013 单元测试]
├── __init__.py
├── conftest.py                        ← [职责：共享 fixture（内存 SQLite / Mock）]
├── test_models.py                     ← [职责：Memory 实体与 DTO 测试]
│   - [测试场景1: 正常创建] [断言: 字段正确] [Mock: 无]
│   - [测试场景2: importance 越界] [断言: ValidationError] [Mock: 无]
│   - [测试场景3: content 超长] [断言: ValidationError] [Mock: 无]
│   - [测试场景4: extra 字段] [断言: ValidationError] [Mock: 无]
│   - [测试场景5: frozen] [断言: 属性赋值异常] [Mock: 无]
├── test_repository.py                 ← [职责：Repository 测试]
│   - [测试场景1: save 成功] [断言: 返回 Memory] [Mock: 内存 SQLite]
│   - [测试场景2: 幂等] [断言: 重复 save 返回已存在] [Mock: 内存 SQLite]
│   - [测试场景3: query] [断言: 重要性排序] [Mock: 内存 SQLite]
│   - [测试场景4: 空查询] [断言: 空列表] [Mock: 内存 SQLite]
│   - [测试场景5: count] [断言: 计数一致] [Mock: 内存 SQLite]
│   - [测试场景6: 容量触发] [断言: check_capacity=True] [Mock: 内存 SQLite]
│   - [测试场景7: 批量淘汰] [断言: 返回淘汰数] [Mock: 内存 SQLite]
│   - [测试场景8: DB 失败] [断言: StorageError] [Mock: SQLite 异常]
├── test_lru.py                        ← [职责：LRU 淘汰测试]
│   - [测试场景1: 候选选择] [断言: 最旧 N 条] [Mock: 内存 SQLite]
│   - [测试场景2: 不触发] [断言: current<max] [Mock: 无]
│   - [测试场景3: 触发] [断言: current>=max] [Mock: 无]
│   - [测试场景4: 完整 run] [断言: 淘汰 10%] [Mock: 内存 SQLite]
│   - [测试场景5: 删除失败] [断言: StorageError] [Mock: Repository 异常]
├── test_extractor.py                  ← [职责：FactExtractor 测试]
│   - [测试场景1: 抽取成功] [断言: facts 非空] [Mock: respx]
│   - [测试场景2: 重试 1 次] [断言: 第二次成功] [Mock: respx 500→200]
│   - [测试场景3: 重试仍败] [断言: LLMUnavailableError] [Mock: respx 持续 500]
│   - [测试场景4: 解析失败] [断言: ValidationError] [Mock: respx 非 JSON]
│   - [测试场景5: prompt 填充] [断言: 占位符替换] [Mock: 无]
└── test_service.py                    ← [职责：Service 编排测试]
    - [测试场景1: save 正常] [断言: Extractor+Repository 调用] [Mock: 全 Mock]
    - [测试场景2: save 触发 LRU] [断言: 容量满调 LRU] [Mock: Repository 满]
    - [测试场景3: save 抽取失败] [断言: LLMUnavailableError] [Mock: Extractor 异常]
    - [测试场景4: query 正常] [断言: 返回结果] [Mock: Repository]
    - [测试场景5: query 性能] [断言: ≤200ms] [Mock: Repository]
    - [测试场景6: evict] [断言: 返回淘汰数] [Mock: LRUEviction]
    - [测试场景7: action=save] [断言: 路由 save_fact] [Mock: 全 Mock]
    - [测试场景8: action=query] [断言: 路由 query_facts] [Mock: 全 Mock]
    - [测试场景9: action=evict] [断言: 路由 evict_lru] [Mock: 全 Mock]
```

---

## 文件间依赖关系

```
service.py
  ├──→ models.py        (Memory / FactExtractionRequest)
  ├──→ repository.py    (MemoryRepository)
  ├──→ lru.py           (LRUEviction)
  └──→ extractor.py     (FactExtractor)

repository.py
  ├──→ models.py        (Memory / MemoryQueryResult)
  └──→ shared/          (types / exceptions)  [来自 shared 包]

lru.py
  ├──→ models.py        (LRUVictim / Memory)
  └──→ repository.py    (MemoryRepository)

extractor.py
  ├──→ models.py        (FactExtractionRequest / FactExtractionResult)
  └──→ shared/          (types / exceptions)

models.py
  └──→ shared/types.py  (TraceIdType / UserIdType)

tests/unit/test_memory/  →  src/aitutor/memory/
```

---

## 关键约束（Import Linter 强制，来自 CS-NNN .importlinter.toml contract:3）

| 层级 | 允许依赖 | 禁止依赖 |
|------|---------|---------|
| `aitutor.memory.service` | repository + models + lru + extractor + shared | api |
| `aitutor.memory.repository` | models + storage + shared | api + service |
| `aitutor.memory.lru` | models + repository | api + service |
| `aitutor.memory.extractor` | models + shared | api + service + repository |
| `aitutor.memory.models` | shared/types | 任何业务模块 |

---

## 来源标注

- [DD-001:FS-NNN] 文件结构规范
- [DD-001:MD-013] 模块细化方案
- [DD-001:IC-007] 接口契约定义
- [DD-001:CS-NNN] 代码风格指南
- [DD-001:DDR-003] 并发控制三重保护
- [DD-M推断:依据=FS-NNN 5项合规检查 + Python src layout 最佳实践]
