"""orchestrator - 教学编排器（Teaching Orchestrator）

[文件路径] src/aitutor/teaching/orchestrator.py
[文件职责] 教学编排主类，串接 FSM 与 Dispatcher，输出 next_step
[所属模块] M-009 教学编排（来自 DD-001）
[关联设计规范] MD-009 / FS-009（来自 DD-001）
[功能描述]
  功能1: 根据 user_id/session_id 计算下一步教学动作（next_step）
  功能2: 对外暴露调度入口 dispatch_action
  功能3: 教学侧费曼打分（teach_feynman）与 FSRS 调度（schedule_fsrs）封装
[输入输出]
  输入: user_id、session_id、action、context_ids
  输出: NextStep / ActionResult / FeynmanResult / FSRSCard
[依赖关系]
  依赖文件: state_machine.py、dispatcher.py、feynman/scorer.py（M-010）、fsrs/scheduler.py（M-011）、stage/evaluator.py（M-012）
  被依赖文件: api/v1/turn.py（M-002 路由）、pipeline/orchestrator.py（M-007 在 LEARN 阶段回调）
[注意事项]
  注意1: 该类是 Mediator 中心，需避免在内部直接 import 业务实现，应通过 dispatcher 间接调用
  注意2: 状态机卡死时必须走 LLM 兜底并写 audit_log（E00902）
  注意3: 该类不持有任何 I/O 资源（FSRS 实例由 M-011 单例管理），可被多协程共享
[代码风格] 遵循 CS-AITutor-V3.1（来自 DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-009 - 初版文件头注释
[作者] DD-M-M-009-20260602
[来源标注] [DD-001:MD-009] + [DD-M推断:依据=Mediator 模式在 V3.1 的最佳实践]
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from aitutor.teaching.dispatcher import ActionDispatcher, TeachingContext
    from aitutor.teaching.state_machine import TeachingStateMachine
    from aitutor.feynman.scorer import FeynmanResult
    from aitutor.fsrs.scheduler import FSRSCard
    from aitutor.shared.types import NextStep, ActionResult


class TeachingOrchestrator:
    """[类名] TeachingOrchestrator
    [职责] 教学编排总入口，串联 FSM 与 Mediator
    [关联设计规范] MD-009（来自 DD-001 模块细化方案）
    [属性]
      属性1: state_machine TeachingStateMachine FSM 实例，持有当前状态
      属性2: dispatcher ActionDispatcher Mediator 实例，分发动作到具体处理器
      属性3: last_action Optional[str] 最近一次成功调度的动作名
    [方法列表]
      方法1: next_step(user_id, session_id) -> NextStep - 计算下一步教学动作
      方法2: dispatch_action(action, context) -> ActionResult - 通用动作分发
      方法3: teach_feynman(question) -> FeynmanResult - 教学侧费曼评分封装
      方法4: schedule_fsrs(card_id, grade) -> FSRSCard - FSRS 调度封装
    [状态机]
      状态1: IDLE - 初始态
      状态2: LEARN - 学习态
      状态3: REVIEW - 复习态
      状态4: PRACTICE - 练习态
      状态5: REST - 休息态
      状态6: STAGE_ADJUST - 阶段校准态
    [异常处理]
      异常1: TeachingFSMStuckError - FSM 卡死时抛出（E00902）
      异常2: FeynmanScoreError - 费曼评分失败时抛出（E00901）
      异常3: FSRSVersionError - FSRS 版本低时抛出（E00903）
    [来源标注] [DD-001:MD-009] + [DD-M推断:依据=Mediator+FSM 组合模式]
    """

    def __init__(
        self,
        state_machine: "TeachingStateMachine",
        dispatcher: "ActionDispatcher",
    ) -> None:
        """[函数名] __init__
        [职责] 初始化教学编排器
        [关联接口契约] IC-002 学习回合
        [参数说明]
          参数1: state_machine TeachingStateMachine 必填 FSM 实例
          参数2: dispatcher ActionDispatcher 必填 Mediator 实例
        [返回值]
          类型: None
        [错误码]
          错误码1: E00902 FSM 卡死 - 状态机初始化失败时
        [前置条件] state_machine 与 dispatcher 已实例化
        [后置条件] orchestrator 可被多协程共享调用
        [并发安全] 是（无 I/O 资源持有）
        [幂等性] 是
        [性能约束] 初始化 ≤10ms
        [来源标注] [DD-001:MD-009] + [DD-M推断:依据=Mediator 模式]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def next_step(self, user_id: str, session_id: str) -> "NextStep":
        """[函数名] next_step
        [职责] 计算下一步教学动作
        [关联接口契约] IC-002 学习回合（来自 DD-001）
        [参数说明]
          参数1: user_id str 必填 用户 ID，32hex 字符串，强校验
          参数2: session_id str 必填 会话 ID，UUIDv4 格式
        [返回值]
          类型: NextStep
          描述: 包含 next_action、next_state、expected_duration_s 字段
        [错误码]
          错误码1: E00902 含义 FSM 卡死 触发 状态机无转换 处理 LLM 兜底 + audit_log
          错误码2: E00401 含义 session 不存在 触发 会话过期 处理 404
        [前置条件] session 存在且 ACTIVE、user_id 强校验通过
        [后置条件] session.state 已更新、audit_log 记录
        [并发安全] 是（asyncio.Lock 保护 session 写）
        [幂等性] 是（基于 session.current_state 计算）
        [性能约束] 单次 ≤50ms（P95）
        [示例]
          ```
          result = orchestrator.next_step("u_abc123", "s_def456")
          # NextStep(next_action="feynman", next_state="LEARN", expected_duration_s=180)
          ```
        [来源标注] [DD-001:IC-002/MD-009]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def dispatch_action(self, action: str, context: "TeachingContext") -> "ActionResult":
        """[函数名] dispatch_action
        [职责] 通用动作分发（Mediator 入口）
        [关联接口契约] IC-002 学习回合
        [参数说明]
          参数1: action str 必填 动作名，可选[feynman/fsrs/stage_change/idle]
          参数2: context TeachingContext 必填 教学上下文，含 user_id/session_id 等
        [返回值]
          类型: ActionResult
          描述: 包含 success、payload、next_state 字段
        [错误码]
          错误码1: E00901 含义 LLM 评分失败 触发 评分异常 处理 走 FSM 兜底 10%
          错误码2: E00902 含义 FSM 卡死 触发 状态机无转换 处理 LLM 兜底
          错误码3: E00903 含义 FSRS 版本低 触发 schema 旧 处理 升级提示
        [前置条件] action ∈ 白名单
        [后置条件] 对应 handler 被调用、状态机已迁移
        [并发安全] 是
        [幂等性] 否（写入侧操作需 unique key）
        [性能约束] 单次 ≤200ms（P95）
        [来源标注] [DD-001:IC-002] + [DD-M推断:依据=Mediator 解耦设计]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def teach_feynman(self, question: str) -> "FeynmanResult":
        """[函数名] teach_feynman
        [职责] 教学侧费曼评分封装（委托 M-010）
        [关联接口契约] IC-002 学习回合（费曼段）
        [参数说明]
          参数1: question str 必填 长度 [1, 2000] 费曼问题
        [返回值]
          类型: FeynmanResult
          描述: 包含 score (0-5)、feedback、gaps 字段
        [错误码]
          错误码1: E01001 含义 LLM 不可用 触发 模型加载失败 处理 返回 0 + WARN
          错误码2: E01002 含义 响应解析失败 触发 解析异常 处理 重试 1 次
          错误码3: E00901 含义 LLM 评分失败 触发 评分异常 处理 走 FSM 兜底 10%
        [前置条件] M-010 FeynmanScorer 已注入
        [后置条件] 评分结果可被 FSRS 调度使用
        [并发安全] 是（httpx async 调用）
        [幂等性] 是（基于 question_hash 缓存）
        [性能约束] 单次 ≤3s（P95）
        [来源标注] [DD-001:MD-009/IC-002] + [DD-M推断:依据=Mediator 委托模式]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError

    def schedule_fsrs(self, card_id: str, grade: int) -> "FSRSCard":
        """[函数名] schedule_fsrs
        [职责] FSRS 间隔重复调度封装（委托 M-011）
        [关联接口契约] IC-002 学习回合（FSRS 段）
        [参数说明]
          参数1: card_id str 必填 FSRS 卡片 ID
          参数2: grade int 必填 规则 [0, 3] 评分（0=Again, 1=Hard, 2=Good, 3=Easy）
        [返回值]
          类型: FSRSCard
          描述: 包含 due、stability、difficulty、reps 字段
        [错误码]
          错误码1: E00903 含义 FSRS 版本低 触发 schema 旧 处理 升级提示
          错误码2: E01101 含义 FSRS 数据损坏 触发 持久化异常 处理 重建卡 + ERROR 日志
          错误码3: E01102 含义 节流触发 触发 Again 频繁 处理 计数 + 拒绝
        [前置条件] card_id 存在、grade 合法
        [后置条件] 卡片 due 已更新、FSRS 状态持久化
        [并发安全] 是（py-fsrs 单例 + SQLite WAL）
        [幂等性] 是（基于 card_id+grade 组合幂等键）
        [性能约束] 单次 ≤100ms（P95）
        [来源标注] [DD-001:MD-009/IC-002] + [DD-M推断:依据=py-fsrs 1.0 接口]
        """
        # TODO: DD-S 将在此填充实现
        raise NotImplementedError
