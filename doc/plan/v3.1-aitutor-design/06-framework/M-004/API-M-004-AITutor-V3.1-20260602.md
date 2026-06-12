# 接口注释清单 — M-004 Session (AITutor V3.1)

> 负责模块：M-004 Session
> 关联契约：IC-002（学习回合 — session_id 强校验）/ IC-007（长期记忆 — user_id 强校验共用）
> 来源标注：[DD-001:IC-002/IC-007] + [DD-M推断:依据=MD-004 函数签名]

---

## 接口契约 ↔ 函数映射

| 接口契约 | 关联函数 | 实现文件 | 函数签名注释 | 参数说明 | 返回值说明 | 错误码说明 |
|---------|---------|---------|------------|---------|-----------|-----------|
| IC-002 | `SessionService.create_session` | service.py | 完整 | 完整 | 完整 | E00403 |
| IC-002 | `SessionService.get_session` | service.py | 完整 | 完整 | 完整 | E00401 |
| IC-002 | `SessionService.transition_state` | service.py | 完整 | 完整 | 完整 | E00401/E00402/E00403 |
| IC-002 | `SessionService.update_session_state` | service.py | 完整 | 完整 | 完整 | E00401/E00403 |
| IC-002 | `SessionRepository.create` | repository.py | 完整 | 完整 | 完整 | E00403 |
| IC-002 | `SessionRepository.get` | repository.py | 完整 | 完整 | 完整 | E00401（service 层翻译）|
| IC-002 | `SessionRepository.update` | repository.py | 完整 | 完整 | 完整 | E00403 |
| IC-002 | `SessionStateMachine.transition` | state_machine.py | 完整 | 完整 | 完整 | E00402 |
| IC-002 | `SessionStateMachine.get_state` | state_machine.py | 完整 | 完整 | 完整 | N/A |
| IC-002 | `SessionStateMachine.can_transition` | state_machine.py | 完整 | 完整 | 完整 | N/A |
| IC-002 | `Session.activate/suspend/close/mark_expired` | models.py | 完整 | 完整 | 完整 | E00402 |

---

## 函数签名注释详情

### API-001 / IC-002 / `SessionService.create_session`

```python
async def create_session(self, user_id: str) -> Session:
    """创建新会话（user_id 32hex 强校验）。

    [函数名] create_session
    [职责] 为指定用户创建 Session（user_id 32hex 强校验）
    [关联接口契约] IC-002（学习回合前置：session 必须存在）
    [参数说明]
      参数1: user_id str 必填 32hex 强校验（防 CE-003 串号）
    [返回值]
      类型: Session
      描述: 创建的会话（state=NEW）
      特殊值: 成功始终返回 Session；失败抛异常
    [错误码]
      错误码1: E00403 含义: DB 写失败 触发: 仓储层重试 1 次仍失败
    [前置条件] user_id 通过 32hex 强校验
    [后置条件] 数据库新增一行；id 全局唯一
    [并发安全] 是
    [幂等性] 否（每次生成新 UUID）
    [性能约束] 单写 ≤50ms（P95）
    [来源标注] [DD-001:MD-004]
    """
```

### API-002 / IC-002 / `SessionService.get_session`

```python
async def get_session(self, session_id: str) -> Session:
    """查询会话（不存在抛 SessionNotFoundError → E00401）。

    [函数名] get_session
    [职责] 根据 session_id 查询会话；未找到时翻译为业务异常 E00401
    [关联接口契约] IC-002
    [参数说明]
      参数1: session_id str 必填 UUIDv4
    [返回值]
      类型: Session
      描述: 找到的会话实体
      特殊值: 不存在时抛 SessionNotFoundError
    [错误码]
      错误码1: E00401 含义: session 不存在
    [并发安全] 是
    [幂等性] 是
    [性能约束] ≤30ms（P95）
    [来源标注] [DD-001:MD-004]
    """
```

### API-003 / IC-002 / `SessionService.transition_state`

```python
async def transition_state(self, session_id: str, event: str) -> str:
    """FSM 事件驱动的状态转换。

    [函数名] transition_state
    [职责] 通过事件触发状态转换，校验合法性后持久化
    [关联接口契约] IC-002
    [参数说明]
      参数1: session_id str 必填 UUIDv4
      参数2: event str 必填 ∈ {activate, suspend, close, timeout}
    [返回值]
      类型: str
      描述: 转换后的状态值
    [错误码]
      错误码1: E00401 含义: session 不存在
      错误码2: E00402 含义: 状态转换非法
      错误码3: E00403 含义: DB 写失败
    [前置条件] session 存在
    [后置条件] 数据库 state 字段已更新
    [并发安全] 是（asyncio.Lock + SQLite WAL）
    [幂等性] 半幂等
    [性能约束] ≤80ms（P95，含 DB 写）
    [来源标注] [DD-001:MD-004]
    """
```

### API-004 / IC-002 / `SessionStateMachine.transition`

```python
def transition(self, session: Session, event: str) -> str:
    """执行状态转换。

    [函数名] transition
    [职责] 在转换表中查找 (from, event) → to，修改 session
    [关联接口契约] IC-002
    [参数说明]
      参数1: session Session 必填
      参数2: event str 必填 ∈ {activate, suspend, close, timeout}
    [返回值]
      类型: str
      描述: 转换后状态值
    [错误码]
      错误码1: E00402 含义: 状态转换非法
    [并发安全] 是
    [幂等性] 否
    [性能约束] O(1) 字典查找
    [来源标注] [DD-001:MD-004]
    """
```

---

## 错误码覆盖

| 错误码 | 含义 | 触发函数 | 触发条件 | 处理 |
|--------|------|---------|---------|------|
| E00401 | session 不存在 | `SessionService.get_session` | repository.get 返回 None | 抛 SessionNotFoundError → 404 |
| E00402 | 状态转换非法 | `SessionStateMachine.transition` / `Session.activate/suspend/close/mark_expired` | FSM 中无 (from, event) 规则 | 抛 StateTransitionError → 422 + trace_id |
| E00403 | DB 写失败 | `SessionRepository.create/update/delete` / `SessionService.*` 写路径 | OperationalError 重试 1 次仍失败 | 抛 StorageError → 5xx |

**接口契约覆盖率：3/3 = 100%**

## 来源标注
[DD-001:IC-002/IC-007] + [DD-M推断:依据=MD-004 函数签名 + EX-010 错误码翻译]
