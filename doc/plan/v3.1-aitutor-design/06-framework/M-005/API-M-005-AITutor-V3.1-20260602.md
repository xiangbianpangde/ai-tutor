# 接口注释清单 — M-005 Cache 中间件

> 对应模块: M-005
> 项目代号: AITutor
> 版本: V3.1
> 日期: 2026-06-02
> 作者: DD-M-005
> 来源标注: [DD-001:IC-001/002/003] + [DD-001:MD-005] + [DD-M推断]

---

## 接口契约覆盖

| 关联 IC | 接口名称 | M-005 涉及点 | 实现文件 |
|---------|---------|-------------|---------|
| IC-001 | 服务启动 | 启动期 healthcheck() | proxy.py (CacheProxy.healthcheck) |
| IC-002 | 学习回合 | cache hit/miss 路径 + wrap 装饰器 | proxy.py / semantic.py |
| IC-003 | RAG 检索 | NLI 评分缓存写入（TTL 1h） | proxy.py (set with ttl=3600) |

## API-001 CacheProxy.healthcheck

- **接口编号**: API-001-M005
- **关联契约**: IC-001（服务启动 — 启动期 validate）
- **实现文件**: `aitutor/cache/proxy.py`
- **函数签名**:
  ```python
  def healthcheck(self) -> bool:
      """后端健康检查。
      
      Returns:
          bool: True=健康 / False=不健康
      
      Note:
          IC-001 启动期校验；E00501 时返回 False
      """
  ```
- **参数说明**: 无
- **返回值**: bool — True 表示后端可用
- **错误码**:
  - E00501 含义: 后端不可用 触发: Redis 不可达 处理: 返回 False + WARN
- **来源标注**: [DD-001:IC-001] + [DD-001:MD-005]

## API-002 CacheProxy.wrap

- **接口编号**: API-002-M005
- **关联契约**: IC-002（学习回合 — cache 装饰器路径）
- **实现文件**: `aitutor/cache/proxy.py`
- **函数签名**:
  ```python
  def wrap(self, key: str, ttl: int = 3600) -> "CacheWrapper":
      """装饰器入口 — 包装可调用，自动读写缓存。
      
      Args:
          key: 缓存键模板
          ttl: TTL 秒数（默认 3600）
      
      Returns:
          CacheWrapper: 装饰器实例
      """
  ```
- **参数说明**:
  - 参数1: key str 必填 缓存键模板 校验规则 长度 [1, 256]
  - 参数2: ttl int 可选 默认 3600 校验规则 [1, 86400]
- **返回值**: CacheWrapper — 装饰器实例
- **错误码**:
  - E00501 含义: 后端不可用 触发: 写时失败 处理: 跳过缓存写 + WARN
  - E00502 含义: 序列化失败 触发: pickle/json 异常 处理: 跳过 + ERROR
- **来源标注**: [DD-001:IC-002] + [DD-001:MD-005]

## API-003 CacheProxy.get

- **接口编号**: API-003-M005
- **关联契约**: IC-002（学习回合 — cache 读取）
- **实现文件**: `aitutor/cache/proxy.py`
- **函数签名**:
  ```python
  def get(self, query: str) -> Optional[CacheEntry]:
      """缓存读取（语义匹配 + 精确匹配）。
      
      Args:
          query: 原始 query
      
      Returns:
          Optional[CacheEntry]: 命中条目或 None
      """
  ```
- **参数说明**:
  - 参数1: query str 必填 校验规则 长度 [1, 2000]
- **返回值**: Optional[CacheEntry] — 命中返回 CacheEntry
- **错误码**: E00501/E00502
- **来源标注**: [DD-001:IC-002] + [DD-001:MD-005]

## API-004 CacheProxy.set

- **接口编号**: API-004-M005
- **关联契约**: IC-002 + IC-003（NLI 评分缓存 TTL 1h）
- **实现文件**: `aitutor/cache/proxy.py`
- **函数签名**:
  ```python
  def set(self, query: str, response: str, ttl: int) -> None:
      """缓存写入。
      
      Args:
          query: 原始 query
          response: LLM 响应
          ttl: TTL 秒数
      """
  ```
- **参数说明**:
  - 参数1: query str 必填
  - 参数2: response str 必填 校验规则 长度 [1, 100000]
  - 参数3: ttl int 必填 校验规则 [1, 86400]
- **返回值**: None
- **错误码**: E00502/E00503
- **来源标注**: [DD-001:IC-002] + [DD-001:IC-003] + [DD-001:MD-005]

## API-005 LRUEvictionPolicy.evict

- **接口编号**: API-005-M005
- **关联契约**: IC-002（容量保护）
- **实现文件**: `aitutor/cache/lru.py`
- **函数签名**:
  ```python
  def evict(self) -> int:
      """执行淘汰并返回淘汰数。
      
      Returns:
          int: 实际淘汰的条目数
      """
  ```
- **错误码**: E00503
- **来源标注**: [DD-001:MD-005] + [DD-001:IC-002]

## API-006 select_backend

- **接口编号**: API-006-M005
- **关联契约**: IC-001（启动期后端选择）
- **实现文件**: `aitutor/cache/backend.py`
- **函数签名**:
  ```python
  def select_backend(env: str) -> BaseCacheBackend:
      """按 env 选择后端实现。
      
      Args:
          env: 运行环境标识 (dev|test|prod)
      
      Returns:
          BaseCacheBackend: 后端实例
      """
  ```
- **错误码**: E00501
- **来源标注**: [DD-001:MD-005] select_backend 函数签名

## API 覆盖率统计

| 类别 | 数量 | 覆盖率 |
|------|------|--------|
| DD-001 涉及 IC | 3 | IC-001/IC-002/IC-003 |
| M-005 公开 API | 6 | API-001 ~ API-006 |
| 函数签名注释 | 6/6 | 100% |
| 参数说明 | 6/6 | 100% |
| 返回值说明 | 6/6 | 100% |
| 错误码说明 | 6/6 | 100% |

## 来源标注

- [DD-001:IC-001] 服务启动
- [DD-001:IC-002] 学习回合
- [DD-001:IC-003] RAG 检索
- [DD-001:MD-005] 模块细化方案
- [DD-M推断:依据=Proxy/Flyweight 模式] API 设计
