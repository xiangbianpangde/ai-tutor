# 框架决策记录（FDR）— M-004 Session (AITutor V3.1)

> 负责模块：M-004 Session
> 记录时间：2026-06-02
> 来源标注：[DD-M推断:依据=MD-004 设计 + soul 3.7 模板]

---

## FDR-001 Session 模块文件拆分（4 个源文件 + 4 个测试文件）

[决策编号] FDR-001
[决策标题] Session 模块文件拆分 4+4 模式
[决策状态] 已接受
[决策内容] 将 M-004 Session 拆分为 4 个源文件（models / repository / state_machine / service）+ 4 个测试文件（test_models / test_repository / test_state_machine / test_service）+ 1 个 conftest
[决策理由]
  1. MD-004 已显式定义 3 个核心类（Session / SessionRepository / SessionStateMachine）+ service 层入口，单类一文件符合 FS-004 单一职责
  2. 14 用例测试策略按层切分：实体（3）/ 仓储（3）/ FSM（4）/ 服务（3）/ 共享 fixture（conftest）
  3. 4 源文件 + 1 公共导出（__init__）符合 Python src layout 最佳实践
[拒绝的替代方案]
  方案 A（备选）：单文件 session.py（聚合所有类与函数）— 拒绝理由：违反单一职责；超过 soul 4.2 单文件 20 函数上限；不便于 DD-S 分层实现
  方案 B：拆为 6 文件（models 拆 entity/enum/exception）— 拒绝理由：过度拆分，FS-004 5/5 通过项已固定 models.py；4.2 限制最大 5 文件
[影响范围] M-004 全部 4 个源文件 + 4 个测试文件
[相关FDR] FDR-002
[来源标注] [DD-001:FS-004/MD-004] + [DD-M推断:依据=soul 4.7]

---

## FDR-002 状态机实现策略：模块级 TRANSITIONS 常量 + 实例可覆盖

[决策编号] FDR-002
[决策标题] FSM 转换表设计：模块级常量 + 实例可覆盖
[决策状态] 已接受
[决策内容] TRANSITIONS 字典定义在模块级（只读），SessionStateMachine 实例化时可注入自定义表（默认引用模块级）
[决策理由]
  1. 模块级常量便于单元测试时可热替换为测试专用转换表
  2. 实例可覆盖便于未来扩展（V3.5 引入新事件如"reset"）
  3. 避免每次实例化重建字典，节省内存
[拒绝的替代方案]
  方案 A：每次实例化复制 TRANSITIONS — 拒绝理由：内存浪费且修改全局规则需重启
  方案 B：TRANSITIONS 作为类属性 — 拒绝理由：与 Python 习惯不一致，模块级常量更符合 Enum/常量使用约定
[影响范围] state_machine.py
[相关FDR] FDR-001
[来源标注] [DD-001:MD-004 状态机定义] + [DD-M推断:依据=Python 模块级常量最佳实践]

---

## FDR-003 仓储层重试策略封装在 _execute_with_retry 私有方法

[决策编号] FDR-003
[决策标题] DB 写失败重试策略：私有辅助方法封装
[决策状态] 已接受
[决策内容] 在 SessionRepository 中提供私有方法 `_execute_with_retry(operation_name, coro_factory)`，统一处理 OperationalError 重试 1 次 + 翻译为 E00403
[决策理由]
  1. EX-011 明确写失败重试 1 次策略；统一封装避免各写方法重复实现
  2. coro_factory 模式避免 await 提前执行（参考 httpx 客户端惯例）
  3. 私有方法（_ 前缀）符合 CS-AITutor-V3.1 §1 私有成员命名
[拒绝的替代方案]
  方案 A：在每个写方法内联 try/except — 拒绝理由：代码重复 3 次以上；违反 DRY
  方案 B：使用 tenacity 装饰器 — 拒绝理由：增加额外依赖（未在 pyproject.toml 列出）；轻量需求用 12 行代码即可解决
[影响范围] repository.py
[相关FDR] FDR-001
[来源标注] [DD-001:EX-011] + [DD-M推断:依据=pyproject.toml 无 tenacity]

---

## FDR-004 跨模块依赖声明策略：注释形式 + 类型注解

[决策编号] FDR-004
[决策标题] 跨模块依赖声明：仅注释/类型注解形式
[决策状态] 已接受
[决策内容] 在 M-004 产出物中，对 M-017（storage）、M-006（monitor）、shared 的依赖仅以类型注解 + 注释形式存在，不实际 import 任何其他模块的实现
[决策理由]
  1. 严守 D7=100 模块边界硬约束（任何实际 import 都属于跨模块文件依赖）
  2. 下游 DD-S 实现代码骨架时按需 import（DD-S 跨模块协调由 DD-001 统筹）
  3. 类型注解使用前置类型（TYPE_CHECKING）模式可进一步减少运行时依赖
[拒绝的替代方案]
  方案 A：实际 import 其他模块实现 — 拒绝理由：触发 D7 违规；破坏 M-004 单模块隔离
  方案 B：使用 TYPE_CHECKING 守卫 — 拒绝理由：注释形式已足够清晰；待 DD-S 实现阶段再处理
[影响范围] 全部 4 个源文件（注释形式标注）
[相关FDR] 无
[来源标注] [DD-M推断:依据=soul 1.5 多实例隔离协议 + D7 模块边界硬约束]

---

## FDR-005 测试 fixture 拆分：conftest.py 共享 + 各 test_*.py 专属

[决策编号] FDR-005
[决策标题] 测试 Fixture 拆分：conftest 共享 + 各文件专属
[决策状态] 已接受
[决策内容] 共享 fixture（async_engine、session_repository、session_service）放 conftest.py；各 test_*.py 内的辅助 fixture（sample_user_id、sample_session）放 conftest 集中管理避免分散
[决策理由]
  1. CS-AITutor-V3.1 §6 明确"共享 fixture 放 conftest.py"
  2. 单一 conftest 集中管理便于 pytest 收集
  3. 4 个 test_*.py 文件仅含 test_* 函数 + 测试类，职责清晰
[拒绝的替代方案]
  方案 A：每个 test_*.py 单独建 conftest.py — 拒绝理由：过度拆分，pytest 仍会逐级查找
[影响范围] tests/unit/test_session/conftest.py
[相关FDR] FDR-001
[来源标注] [DD-001:CS-001 §6]

---

## FDR 状态汇总

| 决策 | 状态 | 影响文件 |
|------|------|---------|
| FDR-001 | 已接受 | 4 源 + 4 测试 |
| FDR-002 | 已接受 | state_machine.py |
| FDR-003 | 已接受 | repository.py |
| FDR-004 | 已接受 | 全部源文件 |
| FDR-005 | 已接受 | conftest.py |

**5/5 决策已记录（FDR 记录率 100%）**

## 来源标注
[DD-M推断:依据=MD-004 设计 + soul 3.7 模板 + CS-001 §6]
