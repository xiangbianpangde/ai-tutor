# FF-M-009 文件框架结构 — AITutor V3.1

> [模块编号] M-009
> [模块名称] 教学编排（Teaching Orchestration）
> [设计模式] FSM + Mediator
> [负责实例] DD-M-009
> [来源标注] [DD-001:FS-009/MD-009] + [DD-M推断:依据=Mediator+FSM 组合]

---

## 文件框架

```
src/aitutor/teaching/
├── __init__.py                ← 职责：模块入口，导出 TeachingOrchestrator/TeachingStateMachine/ActionDispatcher/TeachingContext
├── orchestrator.py            ← 职责：教学编排主类（TeachingOrchestrator），串联 FSM 与 Mediator
│   - [类 TeachingOrchestrator 注释：属性 state_machine/dispatcher/last_action]
│   - [方法 next_step 注释：IC-002 关联]
│   - [方法 dispatch_action 注释：IC-002 关联]
│   - [方法 teach_feynman 注释：M-010 委托]
│   - [方法 schedule_fsrs 注释：M-011 委托]
├── state_machine.py           ← 职责：教学 FSM（TeachingStateMachine）+ 6 态 6 事件
│   - [枚举 TeachingState 注释：IDLE/LEARN/REVIEW/PRACTICE/REST/STAGE_ADJUST]
│   - [枚举 TeachingEvent 注释：USER_INPUT/FEYNMAN_DONE/FSRS_DUE/AGAIN_THRESHOLD/TIMER_DONE/STAGE_CHANGE]
│   - [异常 TeachingFSMStuckError 注释：E00902]
│   - [类 TeachingStateMachine 注释：属性 current_state/transitions/last_event]
│   - [方法 transition 注释：IC-002 关联]
│   - [方法 get_state 注释]
│   - [方法 reset 注释]
│   - [方法 can_transition 注释]
└── dispatcher.py              ← 职责：Mediator（ActionDispatcher）+ 上下文（TeachingContext）
    - [dataclass TeachingContext 注释：属性 user_id/session_id/action/context_ids/trace_id/extras]
    - [类 ActionResult 注释：Pydantic BaseModel]
    - [类型别名 TeachingHandler 注释]
    - [类 ActionDispatcher 注释：属性 handlers/fallback_handler]
    - [方法 register 注释]
    - [方法 unregister 注释]
    - [方法 dispatch 注释：IC-002 关联]
    - [方法 set_fallback 注释]

tests/unit/test_teaching/
├── __init__.py                ← 职责：测试包入口
├── test_orchestrator.py       ← 职责：TeachingOrchestrator 单测（7 用例）
│   - [场景1 正常 LEARN 推进]
│   - [场景2 FSM 卡死]
│   - [场景3 Feynman 评分失败兜底]
│   - [场景4 FSRS 版本低提示]
│   - [场景5 并发 next_step]
│   - [场景6 空 user_id]
│   - [场景7 兜底 LLM 路径]
├── test_state_machine.py      ← 职责：TeachingStateMachine 单测（10 用例，参数化）
│   - [场景1-5,7 合法转换]
│   - [场景6 通配 stage_change]
│   - [场景8 非法事件]
│   - [场景9 复位]
│   - [场景10 can_transition 守卫]
└── test_dispatcher.py         ← 职责：ActionDispatcher 单测（8 用例）
    - [场景1 注册并分派]
    - [场景2 重复注册覆盖]
    - [场景3 未注册 + fallback]
    - [场景4 未注册 + 无 fallback]
    - [场景5 注销后分派]
    - [场景6 handler 抛异常]
    - [场景7 异步 dispatch 并发]
    - [场景8 build 校验]
```

## 文件间依赖关系

```
orchestrator.py
  ↓ 依赖
state_machine.py  ←→  dispatcher.py
                       ↓ 跨模块委托
                  feynman/scorer.py   (M-010)
                  fsrs/scheduler.py   (M-011)
                  stage/evaluator.py  (M-012)

测试文件 → [被测试文件]
```

| 源文件 | 目标文件 | 依赖类型 |
|--------|---------|---------|
| orchestrator.py | state_machine.py | 内部模块依赖 |
| orchestrator.py | dispatcher.py | 内部模块依赖 |
| orchestrator.py | feynman/scorer.py (M-010) | 跨模块依赖（委托调用） |
| orchestrator.py | fsrs/scheduler.py (M-011) | 跨模块依赖（委托调用） |
| orchestrator.py | stage/evaluator.py (M-012) | 跨模块依赖（委托调用） |
| dispatcher.py | shared/types.py | 共享类型依赖 |
| state_machine.py | shared/exceptions.py | 共享异常依赖 |
| test_orchestrator.py | orchestrator.py | 测试依赖 |
| test_state_machine.py | state_machine.py | 测试依赖 |
| test_dispatcher.py | dispatcher.py | 测试依赖 |

**循环依赖检测**：未发现循环依赖 ✅

## 4.7 文件结构 5 项合规检查

| 检查项 | 检查标准 | 通过 | 说明 |
|--------|---------|------|------|
| 目录层级 | ≥2 层 | ✅ | teaching/ 2 层；tests/unit/test_teaching/ 3 层 |
| 文件命名 | snake_case | ✅ | orchestrator/state_machine/dispatcher/test_orchestrator 等 |
| 文件职责 | 单一明确 | ✅ | orchestrator=编排、state_machine=FSM、dispatcher=Mediator、tests=单测 |
| 依赖关系 | 无循环 | ✅ | 单向 orchestrator → state_machine + dispatcher |
| 最佳实践 | src layout | ✅ | src/aitutor/ 主包 + tests/unit/ 测试 |

**合规度判定**：5/5 通过 = 高

## 注释覆盖统计

| 文件 | 文件头 | 类 | 方法/函数 | 测试场景 |
|------|--------|-----|----------|---------|
| __init__.py | 100% | - | - | - |
| orchestrator.py | 100% | 100% (1) | 100% (4) | - |
| state_machine.py | 100% | 100% (3) | 100% (4) | - |
| dispatcher.py | 100% | 100% (3) | 100% (4) | - |
| test_orchestrator.py | 100% | 100% (3) | 100% (7) | 100% |
| test_state_machine.py | 100% | - | 100% (4) | 100% |
| test_dispatcher.py | 100% | 100% (4) | 100% (8) | 100% |

**注释覆盖率**：100%（7 个文件 / 18 个类 / 31 个方法含完整注释）

## 来源标注

[DD-001:FS-009] + [DD-001:MD-009] + [DD-001:IC-002] + [DD-M推断:依据=Mediator+FSM 组合模式最佳实践]
