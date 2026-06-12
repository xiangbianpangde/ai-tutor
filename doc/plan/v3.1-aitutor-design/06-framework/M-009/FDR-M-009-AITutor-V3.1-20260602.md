# FDR-M-009 框架决策记录 — AITutor V3.1

> [模块编号] M-009
> [负责实例] DD-M-009
> [来源标注] [DD-001:MD-009] + [DD-M推断:依据=Mediator+FSM 组合模式]

---

## FDR-M-009-001 FSM 与 Mediator 职责切分

[决策编号] FDR-M-009-001
[决策标题] FSM 仅做状态推进、Mediator 仅做动作分派
[决策状态] 已接受
[决策内容] TeachingStateMachine 只负责状态转换合法性；ActionDispatcher 只负责 action→handler 映射；TeachingOrchestrator 作为外壳组合两者
[决策理由]
  - 符合单一职责：FSM 关注"何时转换"，Mediator 关注"转换做什么"
  - 易于单测：FSM 单测无需 mock handler，Mediator 单测无需 mock FSM
  - 横向扩展：新增 action 只改 dispatcher.register，不动 FSM
[拒绝的替代方案]
  方案A: FSM 内置 handler 调用——状态机职责过重、难以单测
  方案B: Mediator 包含状态推进——职责扩散、违反 OCP
[影响范围] orchestrator.py、state_machine.py、dispatcher.py
[相关FDR] -
[来源标注] [DD-001:MD-009] + [DD-M推断:依据=Mediator 模式最佳实践]

---

## FDR-M-009-002 Mediator 注册表运行期只读

[决策编号] FDR-M-009-002
[决策标题] ActionDispatcher handlers 运行期禁止修改
[决策状态] 已接受
[决策内容] handlers 在启动期装配，运行期只允许查询（dispatch）；register/unregister 仅启动期调用
[决策理由]
  - 避免运行期 handler 漂移导致 audit 困难
  - 提升并发安全：dispatch 无需加锁
  - 与 V3.1 单进程 asyncio 模型匹配
[拒绝的替代方案] 方案A: 运行期动态注册——增加并发复杂度与 bug 概率
[影响范围] dispatcher.py、tests/unit/test_teaching/test_dispatcher.py
[相关FDR] FDR-M-009-001
[来源标注] [DD-M推断:依据=FSM+Mediator 组合的并发安全考量]

---

## FDR-M-009-003 通配态仅 stage_change

[决策编号] FDR-M-009-003
[决策标题] STAGE_ADJUST 通配边仅接受 stage_change 事件
[决策状态] 已接受
[决策内容] 5 个常规态（IDLE/LEARN/REVIEW/PRACTICE/REST）均接受 stage_change → STAGE_ADJUST；但 STAGE_ADJUST 自身不接受 stage_change（避免自环）
[决策理由]
  - 阶段校准是横切关注点，任一态都可能被触发
  - 防止 STAGE_ADJUST 自身重复触发校准
  - 与 M-012 阶段校准的 hysteresis 2 天设计匹配
[拒绝的替代方案]
  方案A: STAGE_ADJUST 不接受 stage_change——但其他态可自由进入，不一致
  方案B: 全部态都接受全部事件——转换合法性失效
[影响范围] state_machine.py
[相关FDR] -
[来源标注] [DD-001:MD-009] + [DD-M推断:依据=FSM 转换表设计]

---

## FDR-M-009-004 跨模块依赖通过委托注入

[决策编号] FDR-M-009-004
[决策标题] M-009 对 M-010/M-011/M-012 的依赖通过 Mediator 委托
[决策状态] 已接受
[决策内容] orchestrator.teach_feynman/schedule_fsrs 不直接 import M-010/M-011 的具体类；而是通过 dispatcher 委托，由启动期注入
[决策理由]
  - 避免 M-009 → M-010/M-011/M-012 的强耦合
  - 符合 Import Linter 架构边界（service → 业务模块）
  - 便于 M-010/M-011 单独 mock 测试
[拒绝的替代方案]
  方案A: orchestrator 直接 import M-010/011——强耦合、违反 Import Linter
  方案B: 引入抽象接口层——V3.1 不必要，增加 3 文件
[影响范围] orchestrator.py、dispatcher.py
[相关FDR] -
[来源标注] [DD-001:FS-009] + [DD-M推断:依据=Import Linter 架构边界]

---

## FDR-M-009-005 测试用例参数化

[决策编号] FDR-M-009-005
[决策标题] 合法转换单测采用 @pytest.mark.parametrize
[决策状态] 已接受
[决策内容] test_state_machine.py 中 6 条合法转换测试合并为单 parametrize 装饰器，减少冗余
[决策理由]
  - pytest parametrize 减少样板代码
  - 测试结果清晰定位是哪条 (state, event) 失败
  - 与 CS-AITutor-V3.1 测试规范一致
[拒绝的替代方案] 方案A: 6 个独立 test 函数——冗余、CS-006 不推荐
[影响范围] tests/unit/test_teaching/test_state_machine.py
[相关FDR] -
[来源标注] [DD-M推断:依据=pytest 最佳实践]

---

## 来源标注

[DD-001:MD-009/FS-009/IC-002] + [DD-M推断:依据=Mediator+FSM 组合模式]
