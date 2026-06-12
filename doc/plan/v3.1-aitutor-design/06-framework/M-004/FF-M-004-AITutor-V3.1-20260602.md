# 文件框架结构 — M-004 Session (AITutor V3.1)

> 负责模块：M-004 Session
> 关联设计规范：FS-AITutor-V3.1 / MD-AITutor-V3.1 / IC-AITutor-V3.1 / CS-AITutor-V3.1 / EX-AITutor-V3.1
> 来源标注：[DD-001:FS-004/MD-004] + [DD-M推断:依据=soul 3.5 模板]

---

## [模块编号] M-004
## [模块名称] Session（会话管理）

## [设计模式] Repository + FSM

## [设计要点]
- 实体（Session）：id / user_id / created_at / last_active / state
- 仓储（SessionRepository）：AsyncEngine + SQLAlchemy 2.0 async
- 状态机（SessionStateMachine）：NEW/ACTIVE/SUSPENDED/EXPIRED/CLOSED 5 态
- 业务服务（SessionService）：编排 create/get/update/transition

## [文件框架]

```
M-004/
  src/
    aitutor/
      session/
        __init__.py           ← [职责：模块初始化，导出公共接口]
        models.py             ← [职责：Session 实体（Pydantic Model + State 枚举）]
          - Session 类注释
          - SessionState 枚举注释
          - StateTransitionError 异常注释
        repository.py         ← [职责：Session 数据访问层（SQLAlchemy 2.0 async）]
          - SessionRepository 类注释
          - create/get/update/delete/list_by_user 方法注释
          - map_row_to_entity 内部辅助函数注释
        state_machine.py      ← [职责：会话状态机（FSM）]
          - SessionStateMachine 类注释
          - transition 方法注释
          - get_state 方法注释
        service.py            ← [职责：业务逻辑编排层（编排 Repository + StateMachine）]
          - SessionService 类注释
          - create_session/get_session/update_session_state 方法注释
          - transition_state 状态转换方法注释
  tests/
    unit/
      test_session/
        __init__.py           ← [职责：测试包初始化]
        conftest.py           ← [职责：测试共享 Fixture（内存 SQLite、sample session）]
        test_models.py        ← [职责：Session 模型类测试]
          - 测试场景1：正常创建 Session
          - 测试场景2：Session 状态枚举值
          - 测试场景3：边界条件-空 user_id 校验
        test_repository.py    ← [职责：SessionRepository 数据访问层测试]
          - 测试场景1：CRUD 完整流程（create+get+update+delete）
          - 测试场景2：按 user_id 列表查询
          - 测试场景3：DB 写失败异常处理
        test_state_machine.py ← [职责：FSM 状态机测试]
          - 测试场景1：正常状态转换（NEW→ACTIVE）
          - 测试场景2：非法状态转换（ACTIVE→NEW）
          - 测试场景3：timeout 事件触发 EXPIRED
        test_service.py       ← [职责：SessionService 业务逻辑测试]
          - 测试场景1：端到端创建+查询+状态变更
          - 测试场景2：session 不存在（404）异常
          - 测试场景3：状态非法转换（422）异常
```

## [文件间依赖关系]

```
service.py → repository.py → models.py
        ↘   state_machine.py → models.py
        ↘   models.py
tests/test_session/ → [被测试文件: service / repository / state_machine / models]
```

依赖方向遵循：
- `service.py` 依赖 `repository.py`、`state_machine.py`、`models.py`
- `repository.py` 依赖 `models.py`
- `state_machine.py` 依赖 `models.py`
- `models.py` 不依赖任何业务模块（Import Linter contract 4）
- 任何上层（API 层）必须经 `service.py` 访问，禁止直接 import `repository.py`（Import Linter contract 1+3）

## [模块边界守护 — D7=100]
- 本 DD-M 实例仅操作 M-004 内的文件
- 跨模块文件操作数：0
- 未触碰：M-001/002/003/005~017 的任何文件
- 注释中跨模块引用仅以接口契约形式（如调用 M-002 API 网关）出现，不实际创建其他模块文件

## [D7 模块边界 5 项检查]

| 检查项 | 检查标准 | 通过情况 |
|--------|---------|---------|
| 仅操作 M-004 内的文件 | 路径前缀均为 `M-004/src/aitutor/session/` 或 `M-004/tests/unit/test_session/` | ✅ 100% |
| 未触碰其他模块文件 | 跨模块引用仅以注释/接口契约形式 | ✅ 0 个 |
| 跨模块依赖通过接口契约声明 | M-002 网关等仅以 IC-002 接口契约形式出现 | ✅ |
| 文件命名带 M-004 标识 | 产出物命名 FF/API/FC/FDR/FH-M-004-* | ✅ |
| 注释中标注模块编号 | 所有文件头注释 [作者] 字段含 M-004 标识 | ✅ |

## [来源标注] [DD-001:FS-004/MD-004] + [DD-M推断:依据=soul 3.5 模板]
