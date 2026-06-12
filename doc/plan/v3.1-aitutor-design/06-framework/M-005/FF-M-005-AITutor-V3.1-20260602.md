# 文件框架结构 — M-005 Cache 中间件

> 对应模块: M-005
> 项目代号: AITutor
> 版本: V3.1
> 日期: 2026-06-02
> 作者: DD-M-005
> 来源标注: [DD-001:FS-005] + [DD-001:MD-005] + [DD-001:CS-AITutor]

---

## [模块编号] M-005
## [模块名称] Cache 中间件（Proxy + Flyweight）
## [设计模式] Proxy（统一入口）+ Flyweight（共享策略实例）

## [文件框架]

```
产出物/07-文件框架/M-005/
├── FF-M-005-AITutor-V3.1-20260602.md        ← [职责：文件框架结构]
├── API-M-005-AITutor-V3.1-20260602.md       ← [职责：接口注释清单]
├── FC-M-005-AITutor-V3.1-20260602.md        ← [职责：文件结构合规报告]
├── FDR-M-005-AITutor-V3.1-20260602.md       ← [职责：框架决策记录]
├── FH-M-005-AITutor-V3.1-20260602.md        ← [职责：文件框架健康度仪表盘]
├── aitutor/
│   └── cache/
│       ├── __init__.py       ← [职责：模块入口，导出公共接口]
│       ├── semantic.py       ← [职责：语义缓存（向量相似度 0.85~0.95）]
│       ├── lru.py            ← [职责：LRU 容量淘汰策略（Flyweight）]
│       ├── backend.py        ← [职责：双后端（SQLite/Redis）]
│       └── proxy.py          ← [职责：缓存代理（Proxy 统一入口）]
└── tests/
    └── unit/
        └── test_cache/
            ├── __init__.py   ← [职责：测试包标识]
            ├── test_backend.py   ← [职责：双后端测试]
            ├── test_lru.py       ← [职责：LRU 策略测试]
            ├── test_semantic.py  ← [职责：语义缓存测试]
            └── test_proxy.py     ← [职责：CacheProxy 测试]
```

## [文件数统计]

| 类别 | 数量 | 文件列表 |
|------|------|---------|
| 主代码文件 | 5 | __init__.py / semantic.py / lru.py / backend.py / proxy.py |
| 测试文件 | 5 | __init__.py / test_backend.py / test_lru.py / test_semantic.py / test_proxy.py |
| 框架交付物 | 5 | FF / API / FC / FDR / FH |
| **合计** | **15** | 全部文件路径含 M-005 标识 |

## [文件职责]

| 文件 | 职责 | 依赖 | 公开 API |
|------|------|------|---------|
| `cache/__init__.py` | 模块入口，导出 CacheBackend/CacheProxy/SemanticCache/LRUEvictionPolicy | 无 | 5 个公共导出 + 2 个工厂函数 |
| `cache/backend.py` | 缓存后端抽象 + SQLite/Redis 双实现 | shared.exceptions | BaseCacheBackend / SQLiteCacheBackend / RedisCacheBackend / select_backend |
| `cache/lru.py` | LRU 容量淘汰（Flyweight 共享策略） | 无 | LRUEvictionPolicy / evict_lru / touch_key |
| `cache/semantic.py` | 语义级缓存（向量相似度匹配） | cache.backend | CacheEntry / SemanticCache / semantic_get / semantic_set |
| `cache/proxy.py` | 缓存统一代理（Proxy 入口 + 后端降级） | cache.backend/lru/semantic | CacheProxy / CacheWrapper / build_cache_proxy |

## [文件间依赖关系]

```
proxy.py
  ├─→ backend.py (BaseCacheBackend / CacheBackend)
  ├─→ lru.py (LRUEvictionPolicy)
  └─→ semantic.py (SemanticCache / CacheEntry)

semantic.py
  └─→ backend.py (BaseCacheBackend，类型注解)

__init__.py
  └─→ proxy.py / semantic.py / lru.py / backend.py (TYPE_CHECKING 延迟导入)

tests/unit/test_cache/*.py
  └─→ aitutor/cache/*.py
```

## [关键约束]

| 约束 | 描述 | 依据 |
|------|------|------|
| 受 Import Linter contract 2 保护 | service 不反向依赖 api | DD-001 CS-AITutor .importlinter.toml |
| 受 Import Linter contract 1 保护 | api 不直接访问 backend | DD-001 CS-AITutor .importlinter.toml |
| 跨模块依赖通过 DI 注入 | encoder 由 M-008 RAG 提供 | DD-M 推断 |
| Flyweight 共享 | 多请求共享同一 backend/lru 实例 | DD-001 MD-005 LRUEvictionPolicy |

## [来源标注]

- [DD-001:FS-005] 文件结构规范 M-005
- [DD-001:MD-005] 模块细化方案 M-005
- [DD-001:CS-AITutor] 代码风格指南
- [DD-M推断:依据=Python src layout + Proxy/Flyweight 模式] 文件组织
