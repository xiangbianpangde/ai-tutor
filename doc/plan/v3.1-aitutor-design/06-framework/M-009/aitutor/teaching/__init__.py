"""teaching - 教学编排模块入口

> 对应模块: M-009 教学编排（FSM + Mediator）
> 关联接口: IC-002 学习回合
> 关联选型: TS-001 Python / TS-007 py-fsrs
> 关联上游模块: M-007 Pipeline / M-010 费曼评分 / M-011 FSRS 调度 / M-012 阶段校准
> 来源标注: [DD-001:MD-009/FS-009] + [DD-M推断:依据=模块化分包最佳实践]
"""

from aitutor.teaching.orchestrator import TeachingOrchestrator
from aitutor.teaching.state_machine import TeachingStateMachine
from aitutor.teaching.dispatcher import ActionDispatcher, TeachingContext

__all__ = [
    "TeachingOrchestrator",
    "TeachingStateMachine",
    "ActionDispatcher",
    "TeachingContext",
]

__version__ = "3.1.0"
__module_id__ = "M-009"
