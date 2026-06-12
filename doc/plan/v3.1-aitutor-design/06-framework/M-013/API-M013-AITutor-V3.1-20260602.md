# 接口注释清单 — M-013 长期记忆

> 模块编号: M-013
> 接口契约: IC-007（长期记忆 API-007/IF-007）
> 来源: [DD-001:IC-007] + [DD-001:MD-013] + [DD-M推断:依据]

---

## 接口总览

| 接口编号 | 关联契约 | 实现文件 | 函数签名注释 | 参数说明 | 返回值说明 | 错误码说明 |
|---------|---------|---------|------------|---------|-----------|-----------|
| IC-007-save | IC-007 | service.py:save_fact | 有 | 有 | 有 | 有 |
| IC-007-query | IC-007 | service.py:query_facts | 有 | 有 | 有 | 有 |
| IC-007-evict | IC-007 | service.py:evict_lru | 有 | 有 | 有 | 有 |
| IC-007-handle | IC-007 | service.py:handle_action | 有 | 有 | 有 | 有 |
| IC-007-extract | IC-007 | extractor.py:extract | 有 | 有 | 有 | 有 |
| IC-007-repository-save | IC-007 | repository.py:save | 有 | 有 | 有 | 有 |
| IC-007-repository-query | IC-007 | repository.py:query | 有 | 有 | 有 | 有 |
| IC-007-lru-run | IC-007 | lru.py:run | 有 | 有 | 有 | 有 |

---

## 函数签名注释详情

### IC-007-save：保存事实

```python
async def save_fact(
    user_id: UserIdType,                    # [必填] 用户 ID（强校验，防 CE-003 串号）
    content: str,                            # [必填] 事实内容，长度 [1, 1000]
    *,
    importance: int = 1,                     # [可选] 重要性 [1, 5]，默认 1（V4.5）
    trace_id: TraceIdType | None = None,     # [可选] 32hex 追踪 ID，不传自动生成
) -> Memory:                                 # [返回] 已持久化的 Memory 实体
    """
    保存单条事实（含 LLM 抽取去重 + LRU 触发检查）。

    Args:
        user_id: 用户 ID（强校验，防 CE-003 串号）。
        content: 事实内容，1~1000 字符。
        importance: 重要性 [1, 5]，默认 1。
        trace_id: 追踪 ID（32hex），不传则自动生成。

    Returns:
        Memory: 已持久化的记忆实体。

    Raises:
        LLMUnavailableError: LLM 抽取失败（E01301，重试 1 次后仍败则丢弃）。
        StorageError: DB 写失败（E00403）。

    Note:
        - 幂等键：content_hash(SHA256)，重复 save 返回已存在。
        - 并发：asyncio.Semaphore 保护。
        - LRU 触发：保存后检查容量，超限则淘汰最旧 10%。
        - 性能：单写 ≤100ms（IC-007 性能约束）。

    Example:
        >>> memory = await save_fact("user-001", "用户喜欢 Python", importance=3)
        >>> memory.id
        UUID('...')
    """
```

### IC-007-query：检索事实

```python
async def query_facts(
    user_id: UserIdType,                    # [必填] 用户 ID
    query: str,                              # [必填] 检索关键字
    *,
    limit: int = 20,                         # [可选] 返回上限，默认 20
) -> MemoryQueryResult:                      # [返回] 命中结果与总数
    """
    检索用户记忆（关键字 + 重要性排序）。

    Args:
        user_id: 用户 ID。
        query: 检索关键字。
        limit: 返回上限，默认 20。

    Returns:
        MemoryQueryResult: 命中结果（memories）与总数（total）。

    Raises:
        StorageError: DB 读失败。

    Note:
        - 性能：单查 ≤200ms（IC-007 性能约束）。
    """
```

### IC-007-evict：强制淘汰

```python
async def evict_lru() -> int:                # [返回] 实际淘汰数
    """
    强制触发 LRU 淘汰（管理面调用）。

    Returns:
        int: 实际淘汰数。

    Raises:
        StorageError: 批量删除失败。

    Note:
        - 调用 audit_log 记录（IC-007 E01302 约束）。
    """
```

### IC-007-handle：统一入口

```python
async def handle_action(
    user_id: UserIdType,                                       # [必填] 用户 ID
    action: Literal["save", "query", "evict"],                 # [必填] 操作类型
    *,
    content: Optional[str] = None,                             # [可选] save 时必填
    query: Optional[str] = None,                               # [可选] query 时必填
    importance: int = 1,                                       # [可选] 重要性 [1, 5]
) -> dict:                                                     # [返回] IC-007 出参
    """
    IC-007 统一入口（action 分发）。

    Args:
        user_id: 用户 ID。
        action: 操作类型 [save, query, evict]。
        content: save 时必填。
        query: query 时必填。
        importance: 重要性 [1, 5]。

    Returns:
        dict: IC-007 出参
            - save: {saved_id, trace_id}
            - query: {memories, trace_id}
            - evict: {evicted_count, trace_id}
    """
```

### IC-007-extract：LLM 抽取

```python
async def extract(
    request: FactExtractionRequest,           # [必填] 抽取请求（conversation/user_id/max_facts）
) -> FactExtractionResult:                    # [返回] 抽取结果（facts/confidence/trace_id）
    """
    从对话中提取事实（httpx 异步 + 重试 + 解析）。

    Args:
        request: 抽取请求。

    Returns:
        FactExtractionResult: 抽取结果。

    Raises:
        LLMUnavailableError: LLM 调用失败（E01301，重试 1 次）。
        ValidationError: 响应解析失败。
    """
```

### IC-007-repository-save：Repository 保存

```python
async def save(
    memory: Memory,                            # [必填] 待保存的 Memory 实体
) -> Memory:                                   # [返回] 持久化后的 Memory（去重命中时返回已存在）
    """
    保存记忆（去重幂等 + 触发 LRU 检查）。

    Args:
        memory: 待保存的 Memory 实体。

    Returns:
        Memory: 持久化后的记忆。

    Raises:
        StorageError: DB 写失败（E00403）。

    Note:
        幂等键 = content_hash(SHA256)，重复 save 返回已存在。
    """
```

### IC-007-repository-query：Repository 检索

```python
async def query(
    user_id: UserIdType,                       # [必填] 用户 ID
    query: str,                                # [必填] 检索关键字
    *,
    limit: int = 20,                           # [可选] 返回上限
) -> MemoryQueryResult:                        # [返回] 命中结果与总数
    """
    检索用户记忆（基于 content 关键字匹配）。

    Args:
        user_id: 用户 ID。
        query: 检索关键字。
        limit: 返回上限（默认 20）。

    Returns:
        MemoryQueryResult: 命中结果与总数。

    Raises:
        StorageError: DB 读失败。
    """
```

### IC-007-lru-run：LRU 执行

```python
async def run() -> int:                        # [返回] 实际淘汰数
    """
    执行 LRU 淘汰流程。

    Returns:
        int: 实际淘汰数。

    Raises:
        StorageError: 批量删除失败。

    Note:
        调用方：MemoryService 在 save 前/后调用，需写入 audit_log。
    """
```

---

## 错误码映射（IC-007）

| 错误码 | 含义 | 触发条件 | 处理 | 来源 |
|--------|------|---------|------|------|
| E01301 | LLM 提取失败 | 提取异常 | 重试 1 次 / 失败丢弃 | [DD-001:IC-007] |
| E01302 | LRU 淘汰触发 | 容量超限 | 淘汰最旧 10% + audit_log | [DD-001:IC-007] |
| E01303 | 数据量超限 | 100k 记忆 | 强制 LRU | [DD-001:IC-007] |
| E00403 | DB 写失败 | 存储异常 | 5xx + 重试 | [DD-001:IC-007] |

---

## 性能约束（IC-007）

| 操作 | 性能约束 | 来源 |
|------|---------|------|
| save_fact 单写 | ≤100ms | [DD-001:IC-007] |
| query_facts 单查 | ≤200ms | [DD-001:IC-007] |

---

## 并发安全与幂等性

- 并发安全：是（SQLite WAL + asyncio + asyncio.Semaphore 业务级，DDR-003）
- 幂等性：是（幂等键 = content_hash，重复 save 去重）
- 幂等键有效期：持久（与记录同生命周期）

---

## 来源标注

- [DD-001:IC-007] 接口契约定义
- [DD-001:MD-013] 模块细化方案
- [DD-001:CS-NNN §3.2] Google 风格 Docstring
- [DD-001:DDR-003] 并发控制三重保护
- [DD-M推断:依据=Python asyncio + Repository + Factory 最佳实践]
