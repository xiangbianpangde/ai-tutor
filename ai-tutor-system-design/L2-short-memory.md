# L2 短期记忆

> 职责：维护单个学习会话的上下文、当前聚焦、中断恢复能力  
> 接口：为 L6 教学引擎提供"当前讲到哪了"的状态管理，为 L7 交互层提供中断/恢复能力

---

## 1. 核心数据结构

```python
SessionContext = {
    'session_id': str,
    'user_id': str,
    'subject_id': str,
    'status': Literal['active', 'interrupted', 'completed', 'abandoned'],
    
    # 当前教学位置
    'current': {
        'teaching_plan_id': str,          # 当前教学计划
        'current_concept_id': str,        # 当前正在讲的概念
        'position_in_plan': int,          # 计划中的位置索引
        'current_strategy': str,          # 当前使用的策略原语
        'current_strategy_state': str,    # 策略状态机当前状态
    },
    
    # 中断保存点
    'interrupt_checkpoint': Optional[{
        'saved_at': datetime,
        'current_state': dict,            # 完整当前状态快照
        'pending_action': Optional[str],  # 未完成的教学动作
        'pending_question': Optional[str],# 未等待回答的提问
    }],
    
    # 对话历史（最近 N 轮，用于上下文理解）
    'recent_history': List[{
        'role': Literal['system', 'student'],
        'content': str,
        'action_type': str,               # 教学动作类型
        'timestamp': datetime,
    }],
    
    # 当前聚焦
    'focus': {
        'primary_concept': str,           # 主讲概念
        'supporting_concepts': List[str], # 辅助概念（刚引用过）
        'last_action_type': str,          # 上一个教学动作类型
        'expected_next_action': str,      # 预期的下一个动作
    },
    
    # 会话元数据
    'meta': {
        'started_at': datetime,
        'total_elapsed_min': float,       # 总经过时长
        'active_time_min': float,         # 实际学习时长（扣除中断）
        'interrupt_count': int,           # 被打断次数
        'checkpoint_count': int,          # 阶段性总结次数
        'current_cognitive_load': float,  # 当前认知负荷（缓存的L5值）
    },
    
    # 累积的学习统计（会话期内）
    'session_stats': {
        'concepts_covered': List[str],
        'concepts_mastered': List[str],   # mastery > 0.85
        'total_questions_asked': int,
        'correct_rate': float,            # 本次会话正确率
        'errors_by_type': Dict[str, int], # 错误类型分布
    },
}
```

---

## 2. 内存模型

### 2.1 三层缓存架构

```
┌─────────────────────────────────────┐
│  L1 进程内存（最快）                  │
│  当前活动会话的完整 SessionContext     │
│  TTL: 进程存活期内                    │
├─────────────────────────────────────┤
│  L2 Redis（快）                       │
│  所有活跃会话 + 最近结束的会话         │
│  TTL: 30 分钟无活动后 expire           │
│  用途: 跨进程/跨重启恢复              │
├─────────────────────────────────────┤
│  L3 SQLite/Postgres（持久）           │
│  所有已结束会话的归档记录              │
│  用途: 学习分析、画像数据源           │
└─────────────────────────────────────┘
```

### 2.2 Redis 键设计

```
# 会话状态
session:{session_id}:state        → JSON (SessionContext)
session:{session_id}:history      → LIST (最近100条对话)
session:{session_id}:focus         → JSON (当前聚焦)
session:{session_id}:interrupt     → JSON (中断快照)

# 用户维度
user:{user_id}:active_sessions     → SET (session_id列表)
user:{user_id}:last_session        → STRING (session_id)
user:{user_id}:session_count       → INT

# TTL 管理
EXPIRE session:{session_id}:state  1800   # 30分钟
# 每次 L6 更新状态时 RENEW TTL
```

---

## 3. 聚焦管理

### 3.1 聚焦切换

当 L6 切换到新概念时，L2 更新聚焦：

```python
def switch_focus(session: SessionContext, 
                 new_concept_id: str, 
                 reason: str):
    """
    更新当前聚焦:
    1. 把旧概念移入 supporting_concepts（保留上下文）
    2. 设置 primary_concept = new_concept_id
    3. 如果 supporting_concepts 超过 5 个，弹出最老的
    4. 记录 reason（用于中断后的上下文恢复提示）
    
    例如:
    switch_focus(session, "multivariable_chain_rule", 
                 "完成偏导数后进入链式法则")
    → focus: {primary: "多元链式法则", 
              supporting: ["偏导数定义", "一元链式法则"]}
    """
```

### 3.2 上下文窗口

```python
def get_context_window(session: SessionContext, 
                      window_size: int = 6) -> List[Dict]:
    """
    获取最近的 N 轮对话作为上下文窗口。
    用于:
    - L6 决策: "学生刚才问过什么？我上次说了什么？"
    - 中断恢复: "我们在讲什么来着？"
    - 错误诊断: "学生今天第几次在这个概念上犯错了？"
    """
    return session.recent_history[-window_size:]
```

---

## 4. 中断/恢复协议

### 4.1 保存断点

```python
def save_checkpoint(session: SessionContext):
    """
    在以下时机自动保存:
    - L6 每次状态转换（INTRO→EXPLAIN, CHECK→PRACTICE等）
    - 学生主动打断
    - 每 5 分钟定时保存
    - 认知负荷超过阈值时
    """
    
    checkpoint = {
        'saved_at': datetime.now(),
        'current_state': {
            'concept_id': session.current.current_concept_id,
            'position': session.current.position_in_plan,
            'strategy': session.current.current_strategy,
            'strategy_state': session.current.current_strategy_state,
        },
        'focus': session.focus,
        'pending_action': session.get('pending_action'),
        'pending_question': session.get('pending_question'),
        'context_tail': session.recent_history[-3:],  # 最近3轮对话
        'cognitive_load_at_save': session.meta.current_cognitive_load,
    }
    
    # 写入 Redis: session:{id}:interrupt
    # TTL: 24小时（允许隔天回来继续）
```

### 4.2 恢复

```python
def restore_from_checkpoint(session_id: str) -> Optional[SessionContext]:
    """
    从 Redis 或 Postgres 加载断点，重建会话上下文。
    
    返回恢复提示给 L7 交互层:
    "欢迎回来！上次我们讲到[概念]，当时正在[活动]。
    你当时的掌握度是[X]%，错误主要集中在[Y]类型。
    要继续吗？"
    """
```

---

## 5. 会话生命周期

```
CREATE (新建会话)
  → ACTIVE (教学中)
    → INTERRUPTED (被打断)
      → ACTIVE (恢复)
      → COMPLETED (主动结束)
      → ABANDONED (超时 24h 未恢复)
  → COMPLETED (正常完成教学计划)
  → ABANDONED (用户放弃)
```

---

## 6. 实现要点

- Redis 用于热数据（活跃会话），不存全量历史
- 每个 session state 序列化为 JSON < 64KB
- 中断恢复时，先从 Redis 找，miss 则从 Postgres 加载
- 会话结束时，完整 SessionContext 写入 Postgres，作为 L5 画像数据源
- PHP 不需要；Python `redis` + `sqlalchemy` 即可

---

## 7. 与 L6/L7 的接口

```python
# L7 调用:
L2.create_session(user_id, subject_id) → session_id
L2.get_session(session_id) → SessionContext
L2.save_checkpoint(session_id)
L2.restore_session(user_id) → Optional[SessionContext]

# L6 调用:
L2.update_state(session_id, new_state)
L2.append_history(session_id, message)
L2.switch_focus(session_id, new_concept_id)
```
