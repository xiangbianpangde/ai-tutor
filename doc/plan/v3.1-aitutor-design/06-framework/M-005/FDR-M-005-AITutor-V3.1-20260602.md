# 框架决策记录（FDR）— M-005 Cache 中间件

> 对应模块: M-005
> 项目代号: AITutor
> 版本: V3.1
> 日期: 2026-06-02
> 作者: DD-M-005
> 来源标注: [DD-001:MD-005] + [DD-M推断:依据=Proxy/Flyweight 模式]

---

## FDR-001: 选择 Proxy + Flyweight 模式

- **决策编号**: FDR-001-M005
- **决策标题**: M-005 设计模式选择（Proxy + Flyweight）
- **决策状态**: 已接受
- **决策内容**: CacheProxy 统一入口 + Flyweight 共享策略实例
- **决策理由**:
  - Proxy: 统一封装 backend/lru/semantic，对外只暴露 CacheProxy
  - Flyweight: 多个请求/会话可共享同一 LRUEvictionPolicy + backend 实例，减少内存占用
  - DD-001 MD-005 明确指定 Proxy + Flyweight
- **拒绝的替代方案**:
  - 方案A: 仅使用 Singleton — 无法支持多租户后端切换
  - 方案B: 仅使用 Decorator — 缺少统一代理入口，难以管理降级逻辑
- **影响范围**: 全部 M-005 文件（proxy.py 为核心）
- **相关FDR**: 无
- **来源标注**: [DD-001:MD-005] + [DD-001:DP-002]

## FDR-002: 双后端选型（SQLite 默认 + Redis 可选）

- **决策编号**: FDR-002-M005
- **决策标题**: 缓存后端双实现选型
- **决策状态**: 已接受
- **决策内容**: 默认 SQLite（单进程），可选 Redis（分布式），env 切换
- **决策理由**:
  - SQLite 零依赖，开箱即用，符合 V3.1 单进程默认
  - Redis 适用于 V3.5+ 分布式部署
  - select_backend 工厂按 env 切换
- **拒绝的替代方案**:
  - 方案A: 仅 SQLite — 不支持分布式
  - 方案B: 仅 Redis — 增加部署复杂度（V3.1 不必要）
  - 方案C: 引入 Memcached — 生态不如 Redis 活跃
- **影响范围**: cache/backend.py + cache/__init__.py
- **相关FDR**: FDR-003
- **来源标注**: [DD-001:MD-005] + [DD-001:TS-005]

## FDR-003: Redis 不可用自动降级 SQLite

- **决策编号**: FDR-003-M005
- **决策标题**: 后端降级策略（E00501）
- **决策状态**: 已接受
- **决策内容**: Redis 抛 ConnectionError 时自动切到 SQLite，WARN 日志
- **决策理由**:
  - DD-001 MD-005 异常处理 E00501 明确要求
  - 优先保证缓存可用性，性能降级可接受
  - 启动期 healthcheck 配合 E00501 判定
- **拒绝的替代方案**:
  - 方案A: 失败即崩溃 — 影响服务可用性
  - 方案B: 失败重试 N 次 — 引入阻塞延迟
- **影响范围**: cache/proxy.py (_handle_backend_failure)
- **相关FDR**: FDR-002
- **来源标注**: [DD-001:MD-005] E00501

## FDR-004: LRU 淘汰比例 10%

- **决策编号**: FDR-004-M005
- **决策标题**: LRU eviction_ratio 默认值
- **决策状态**: 已接受
- **决策内容**: 默认淘汰比例 0.1（每次淘汰 10%）
- **决策理由**:
  - DD-001 MD-005 LRUEvictionPolicy 属性明定 eviction_ratio=0.1
  - 10% 兼顾避免频繁淘汰 + 不阻塞写入
- **拒绝的替代方案**:
  - 方案A: 5% — 频繁淘汰，CPU 开销大
  - 方案B: 20% — 一次性淘汰多，缓存命中率下降
- **影响范围**: cache/lru.py (LRUEvictionPolicy.__init__)
- **相关FDR**: 无
- **来源标注**: [DD-001:MD-005]

## FDR-005: 语义缓存阈值区间 [0.85, 0.95]

- **决策编号**: FDR-005-M005
- **决策标题: 语义相似度阈值上下限
- **决策状态**: 已接受
- **决策内容**: threshold_low=0.85 / threshold_high=0.95
- **决策理由**:
  - DD-001 MD-005 SemanticCache 属性明定
  - [0.85, 0.95] 区间：低相似度可能误命中，高相似度可能漏命中
- **拒绝的替代方案**:
  - 方案A: 单一阈值 0.9 — 缺乏灵活性
  - 方案B: 阈值 0.7 — 误命中风险高
- **影响范围**: cache/semantic.py
- **相关FDR**: 无
- **来源标注**: [DD-001:MD-005]

## FDR-006: TTL Jitter 抖动 20%

- **决策编号**: FDR-006-M005
- **决策标题: TTL 抖动系数
- **决策状态**: 已接受
- **决策内容**: ttl_jitter=0.2（TTL ±20% 随机抖动）
- **决策理由**:
  - DD-001 MD-005 ttl_jitter 属性明定
  - 防止缓存雪崩：避免大量 key 同时过期
- **拒绝的替代方案**:
  - 方案A: 无 jitter — 雪崩风险
  - 方案B: jitter=0.5 — 抖动过大，TTL 不可预测
- **影响范围**: cache/semantic.py (apply_jitter)
- **相关FDR**: FDR-005
- **来源标注**: [DD-001:MD-005]

## FDR-007: 跨模块 encoder 依赖通过 DI 注入

- **决策编号**: FDR-007-M005
- **决策标题: 向量编码器跨模块依赖解耦
- **决策状态**: 已接受
- **决策内容**: SemanticCache 不直接 import M-008 RAG，encoder 由调用方注入
- **决策理由**:
  - 避免循环依赖（M-005 与 M-008 互不引用）
  - Import Linter contract 5 保护 shared 不依赖业务模块
  - 测试可注入 mock encoder
- **拒绝的替代方案**:
  - 方案A: 直接 import M-008 — 循环依赖
  - 方案B: 在 M-005 内置 encoder — 重复实现 + 维护成本
- **影响范围**: cache/semantic.py (encoder 属性)
- **相关FDR**: 无
- **来源标注**: [DD-M推断:依据=Import Linter + DI 最佳实践]

## FDR-008: CacheProxy.wrap 装饰器入口

- **决策编号**: FDR-008-M005
- **决策标题: 装饰器接口
- **决策状态**: 已接受
- **决策内容**: CacheProxy.wrap(key, ttl) 返回装饰器
- **决策理由**:
  - DD-001 MD-005 CacheProxy.wrap 方法明定
  - 装饰器模式可透明地给函数加缓存，业务代码侵入小
- **拒绝的替代方案**:
  - 方案A: 强制手动 get/set — 代码侵入大
  - 方案B: 切面编程（AOP）— Python 生态不友好
- **影响范围**: cache/proxy.py (wrap)
- **相关FDR**: FDR-001
- **来源标注**: [DD-001:MD-005] + [DD-001:DP-002]

## FDR 状态汇总

| FDR | 标题 | 状态 | 影响文件 |
|-----|------|------|----------|
| FDR-001 | Proxy + Flyweight 模式 | 已接受 | proxy.py |
| FDR-002 | 双后端选型 | 已接受 | backend.py |
| FDR-003 | Redis 降级 SQLite | 已接受 | proxy.py |
| FDR-004 | LRU 淘汰比例 10% | 已接受 | lru.py |
| FDR-005 | 语义阈值 [0.85, 0.95] | 已接受 | semantic.py |
| FDR-006 | TTL Jitter 20% | 已接受 | semantic.py |
| FDR-007 | encoder DI 注入 | 已接受 | semantic.py |
| FDR-008 | wrap 装饰器 | 已接受 | proxy.py |

**FDR 覆盖率: 8/8 关键决策 = 100%**

## 来源标注

- [DD-001:MD-005] 模块细化方案
- [DD-001:DP-001~007] 设计模式选型
- [DD-001:TS-005] Redis 技术选型
- [DD-M推断:依据=Proxy/Flyweight/DI 最佳实践] 架构决策
