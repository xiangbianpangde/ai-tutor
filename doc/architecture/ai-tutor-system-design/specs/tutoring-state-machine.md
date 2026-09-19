# 教学会话状态机

> 完整定义 tutoring-mcp 中教学会话的顶级状态转换，以及会话与 L6 策略状态机的衔接

---

## 一、会话级状态机

```
                              ┌──────────────┐
                              │   EXPIRED    │── 24h无活动
                              └──────────────┘
                                    ▲
                                    │ timeout
                                    │
┌─────────┐  start_session  ┌───────┴───────┐
│  IDLE   │───────────────▶│    ACTIVE     │
└─────────┘                └───────┬───────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │ interrupt          │                    │
              ▼                    │                    │
     ┌────────────────┐            │           ┌──────────────┐
     │  INTERRUPTED   │            │           │   COMPLETED  │
     └───────┬────────┘            │           └──────────────┘
             │                     │                    ▲
    ┌────────┴────────┐            │                    │
    │                  │            │              finish_session
    ▼                  ▼            │
┌─────────┐      ┌──────────┐      │
│ RESUME  │      │ EXPLORE  │      │
│(回原流程)│      │(跟进打断)│      │
└────┬────┘      └────┬─────┘      │
     │                │            │
     └────────┬───────┘            │
              │ explore_done       │
              ▼                    │
        ACTIVE ◀───────────────────┘
```

### 状态说明

| 状态 | 含义 | L2 存储位置 |
|------|------|------------|
| `IDLE` | 无会话，等待创建 | — |
| `ACTIVE` | 正常教学中，L6 策略状态机运行 | Redis + 进程内存 |
| `INTERRUPTED` | 学生打断，保存了断点，等待恢复 | Redis (24h TTL) |
| `RESUME` | 从断点恢复原教学流程 | 过渡态，短暂 |
| `EXPLORE` | 正在跟进学生的打断问题 | 过渡态 |
| `COMPLETED` | 正常完成教学计划或学生主动结束 | Postgres 归档 |
| `EXPIRED` | 24h 未恢复的 INTERRUPTED 会话 | Postgres 归档 |

---

## 二、ACTIVE 状态内的 L6 策略嵌套

当会话处于 `ACTIVE` 状态时，内部运行 L6 策略状态机：

```
ACTIVE
  ├── 策略: ReductionOfOrder (PLAN → INTRO → EXPLAIN → CHECK → PRACTICE → NEXT)
  ├── 策略: FeynmanTechnique (PROMPT → WAIT → EVALUATE → PASS/CORRECT/SIMPLIFY)
  ├── 策略: SocraticMethod (QUESTION → WAIT → ANALYZE → NUDGE/HINT/REVEAL)
  ├── 策略: PBL (ASSIGN → PLAN_REVIEW → MILESTONE_CHECK → FEEDBACK)
  ├── 策略: AnalogousBridging (ESTABLISH → DRAW → APPLY → LIMITS → TRANSITION)
  └── 策略: SpacedRepetition (RECALL → FOCUSED → INTERLEAVED → CONSOLIDATE)

策略切换不改变会话状态（仍为 ACTIVE），仅在 L6 引擎内部跳转。
```

---

## 三、会话内数据流

```
L7 (MCP tool)
  │
  ├─ start_learning_session() ──▶ L2.create_session()
  │                                L6.build_teaching_path()
  │                                L5.get_teaching_context()
  │                                → 返回首步 action
  │
  ├─ next_action(session_id) ──▶ L6.teaching_loop.next()
  │                               L5.update_context()
  │                               L3.get_review_suggestion()
  │                               → 返回 TeachingAction
  │
  ├─ respond(session_id, answer) ──▶ L6.analyze_response()
  │                                   L5.tracer.update()
  │                                   L3.record_interaction()
  │                                   → 返回 ResponseResult + next_action
  │
  ├─ interrupt(session_id, q) ──▶ L2.save_checkpoint()
  │                                L6.handle_interrupt()
  │                                → 返回 InterruptResult
  │
  ├─ checkpoint(session_id) ──▶ L2.save_checkpoint()
  │                               L5.snapshot()
  │                               L3.update_forgetting_curve()
  │                               → 返回 CheckpointResult
  │
  └─ (session end) ──▶ L2.archive_to_db()
                        L5.profile.persist()
                        L3.generate_review_plan()
```

---

## 四、中断处理详细流程

```
学生调用 interrupt(session_id, question)
  │
  ├─[1] L2.save_checkpoint()
  │      保存: current_state, focus, pending_action, context_tail
  │      会话状态: ACTIVE → INTERRUPTED
  │
  ├─[2] L6.handle_interrupt()
  │      ├─ classify_interrupt_intent(question, session, kg)
  │      │   意图 = concept_question | process_question | prereq_gap |
  │      │         example_request | pace_complaint | distraction |
  │      │         cognitive_overload | explore_connection
  │      │
  │      └─ dispatch(意图):
  │           ├─ concept_question → context_aware_answer
  │           ├─ process_question → step_by_step_explanation
  │           ├─ prereq_gap → detect + mini_tutorial
  │           ├─ pace_complaint → pace_adjustment
  │           ├─ distraction → gentle_redirect
  │           ├─ cognitive_overload → break_suggestion + simplify
  │           └─ explore_connection → answer + record_to_knowledge_network
  │
  ├─[3] 返回 InterruptResult
  │     {
  │       type: "...",
  │       content: "...",
  │       checkpoint_saved: true,
  │       suggested_action: "resume" | "explore_further" | "change_topic"
  │     }
  │
  └─[4] 等待用户选择:
         ├─ "继续" → resume_from_interrupt()
         │            L2.restore_checkpoint()
         │            会话状态: INTERRUPTED → ACTIVE
         │
         ├─ "继续问" → 回到 [2] 处理跟进问题
         │             会话状态: EXPLORE → INTERRUPTED
         │
         └─ "换个话题" → 进入探索模式 (临时脱离教学计划)
                         记录探索内容到 session_stats
```

---

## 五、会话结束流程

```
触发条件之一:
- 教学计划全部完成
- 学生调用 checkpoint(finish)
- 学生调用 learning_insight (视为会话结束)
- 会话超时 24h 未恢复

结束流程:
  ├─ L5.snapshot() → 保存最终知识状态
  ├─ L3.generate_review_plan() → 生成复习计划
  ├─ L5.ProfileEvolver.evolve() → 更新画像
  ├─ L3.ForgettingCurve.fit_all() → 重拟所有遗忘曲线
  ├─ L2.archive_to_db() → Redis → Postgres
  └─ 返回: 学习报告 + 复习计划 + 下次建议
```

---

## 六、异常处理

| 异常 | 处理 |
|------|------|
| Redis 不可用 | 降级到进程内存（单进程模式），WARNING 日志 |
| Postgres 不可用 | 仅使用 Redis（数据不持久化），ERROR 日志，30min 重试 |
| LLM API 超时 | 重试 1 次，仍失败则返回 fallback 响应（"请稍等..."） |
| 策略状态机卡死 | 超时 30s → 重置到上一安全状态点 |
| 学生长时间无响应 | 5min 后发送 ping；10min 后自动保存断点并标记 idle |
