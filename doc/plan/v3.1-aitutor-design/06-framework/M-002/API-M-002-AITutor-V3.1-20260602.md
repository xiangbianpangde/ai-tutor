# API-M-002-AITutor-V3.1-20260602 — M-002 API 网关 + WS 接口注释清单

> 负责模块: M-002 API 网关 + WS
> 关联接口契约: IC-001 / IC-002 / IC-004 / IC-008
> 来源标注: [DD-001:IC-001/002/004/008] + [DD-001:MD-M-002] + [DD-M推断]

---

## 一、HTTP 路由清单

### IC-001 服务启动 → GET /api/v1/health/live, /ready

| 接口编号 | HTTP 方法 | 路径 | 关联文件 | 函数 | 实现状态 |
|---------|---------|------|---------|------|---------|
| IC-001-R1 | GET | /api/v1/health/live | v1/health.py | liveness_endpoint | 框架就绪 |
| IC-001-R2 | GET | /api/v1/health/ready | v1/health.py | readiness_endpoint | 框架就绪 |

### IC-002 学习回合 → POST/GET/DELETE /api/v1/session, /turn

| 接口编号 | HTTP 方法 | 路径 | 关联文件 | 函数 | 实现状态 |
|---------|---------|------|---------|------|---------|
| IC-002-R1 | POST | /api/v1/session | v1/session.py | create_session_endpoint | 框架就绪 |
| IC-002-R2 | GET | /api/v1/session/{id} | v1/session.py | get_session_endpoint | 框架就绪 |
| IC-002-R3 | DELETE | /api/v1/session/{id} | v1/session.py | delete_session_endpoint | 框架就绪 |
| IC-002-R4 | PATCH | /api/v1/session/{id} | v1/session.py | update_session_endpoint | 框架就绪 |
| IC-002-R5 | POST | /api/v1/session/{id}/turn | v1/turn.py | execute_turn_endpoint | 框架就绪（核心）|
| IC-002-R6 | GET | /api/v1/session/{id}/turn/{turn_id} | v1/turn.py | get_turn_endpoint | 框架就绪 |

### IC-004 数据入库 → POST /api/v1/ingest

| 接口编号 | HTTP 方法 | 路径 | 关联文件 | 函数 | 实现状态 |
|---------|---------|------|---------|------|---------|
| IC-004-R1 | POST | /api/v1/ingest | v1/ingest.py | ingest_pdf_endpoint | 框架就绪 |
| IC-004-R2 | GET | /api/v1/ingest/{doc_id} | v1/ingest.py | get_ingest_status_endpoint | 框架就绪 |
| IC-004-R3 | GET | /api/v1/ingest | v1/ingest.py | list_documents_endpoint | 框架就绪 |
| IC-004-R4 | DELETE | /api/v1/ingest/{doc_id} | v1/ingest.py | delete_document_endpoint | 框架就绪 |

### IC-008 WS 推送 → WS /api/v1/ws

| 接口编号 | 类型 | 路径 | 关联文件 | 函数 | 实现状态 |
|---------|------|------|---------|------|---------|
| IC-008-R1 | WS | /api/v1/ws | v1/ws.py | websocket_endpoint | 框架就绪（核心）|

---

## 二、核心函数签名注释（节选）

### verify_token（核心鉴权）

```python
def verify_token(token: str) -> UserContext:
    """
    解析 Bearer Token 并返回 UserContext（AuthDependency.__call__ 包装）。

    [关联接口契约] IC-002 学习回合 / IC-008 WS 推送

    Args:
        token: Bearer Token 字符串（不含 "Bearer " 前缀），
               JWT 格式 HS256

    Returns:
        UserContext: 当前用户上下文
            - user_id: 32hex
            - username: str
            - role: "user" | "admin"
            - jti: Token 唯一标识
            - exp: 过期时间戳

    Raises:
        HTTPException 401: 签名错 / 过期 / 吊销（错误码 E00203）
        HTTPException 503: TokenStore 不可用

    Example:
        >>> ctx = verify_token("eyJhbGciOiJIUzI1...")
        >>> ctx.user_id
        'a1b2c3d4e5f6...'

    [性能约束] ≤ 5ms
    [幂等性] 是
    [并发安全] 是
    [来源标注] [DD-001:IC-002] + [DD-001:EX-002/003]
    """
```

### check_rate_limit（核心限流）

```python
async def check_rate_limit(user_id: str) -> bool:
    """
    校验用户当前是否触发限流（不修改计数）。

    [关联接口契约] IC-002 学习回合

    Args:
        user_id: 用户 ID，32hex 字符串

    Returns:
        bool: True=通过 / False=触发限流
              False 时调用方应返回 429 + Retry-After 头

    Raises:
        RateLimitExceededError: QPS 或 concurrent_turns 超限（错误码 E00204）

    Example:
        >>> await check_rate_limit("a1b2c3d4...")
        True

    [性能约束] ≤ 1ms
    [幂等性] 是（不修改计数）
    [并发安全] 是（asyncio.Lock 保护）
    [来源标注] [DD-001:IC-002] + [DD-001:EX-008]
    """
```

### ws_connect（核心 WS）

```python
async def ws_connect(
    ws: WebSocket,
    session_id: str,
    token: str,
) -> None:
    """
    注册 WebSocket 连接（含 Token 校验 + 限流）。

    [关联接口契约] IC-008 WS 推送

    Args:
        ws: FastAPI WebSocket 实例
        session_id: 关联 session ID，UUIDv4 字符串
        token: Bearer Token（连接时校验）

    Returns:
        None

    Raises:
        ConnectionLimitExceeded: 连接数 > 1000（错误码 E00202）
        TokenInvalidError: Token 无效（错误码 E00203，立即关闭连接）
        HTTPException 401: 鉴权失败

    Example:
        >>> await ws_connect(websocket, "uuid", "eyJ...")

    [状态机] NEW → AUTHED → ACTIVE → CLOSED
    [性能约束] 连接建立 ≤ 50ms
    [幂等性] 否（每个 session_id 唯一）
    [并发安全] 是（asyncio.Lock 保护连接表）
    [来源标注] [DD-001:IC-008] + [DD-001:EX-002] + [DD-001:DD洞察-004]
    """
```

### ws_broadcast（核心 WS 广播）

```python
async def ws_broadcast(event: WSEvent) -> None:
    """
    广播 WS 事件到所有活跃连接（事件总线入口）。

    [关联接口契约] IC-008 WS 推送

    Args:
        event: WS 事件
            - event_type: "pipeline_stage" | "llm_chunk" | "fsrs_update" | "rest_prompt" | "error"
            - payload: dict
            - ts: int 毫秒时间戳
            - trace_id: 32hex

    Returns:
        None

    Raises:
        SerializationError: payload 序列化失败（错误码 E00205，跳过 + WARN）

    Example:
        >>> await ws_broadcast(WSEvent("llm_chunk", {"text": "Hi"}, ts, trace_id))

    [性能约束] 端到端 ≤ 1s (P95)
    [幂等性] N/A（事件流）
    [并发安全] 是（asyncio.Lock 保护连接表）
    [来源标注] [DD-001:IC-008] + [DD-001:MD-M-002]
    """
```

---

## 三、接口契约注释化覆盖

| IC 编号 | 出参完整 | 入参完整 | 错误码覆盖 | 时序明确 | 前置后置 | 幂等性 | 注释化状态 |
|---------|---------|---------|-----------|---------|---------|--------|-----------|
| IC-001 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 完全注释化 |
| IC-002 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 完全注释化 |
| IC-004 | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | 完全注释化 |
| IC-008 | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | 完全注释化 |

**接口契约注释化覆盖率 = 4/4 = 100%**

来源标注: [DD-001:IC-001/002/004/008] + [DD-001:MD-M-002]
