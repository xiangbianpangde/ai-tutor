"""fsrs - FSRS 间隔重复调度模块

> 对应模块: M-011（FSRS 调度）
> 关联接口: IC-002（学习回合，含 fsrs_update 事件）/ API-008（WS 推送 fsrs_update）
> 关联选型: TS-007 py-fsrs==1.0.0
> 关联设计: Singleton 模式（FSRSScheduler 全进程唯一）
> 来源标注: [DD-001:FS-M-011] + [DD-001:MD-M-011] + [DD-M推断:依据=py-fsrs 官方 Singleton 最佳实践]

[文件路径] src/aitutor/fsrs/__init__.py
[文件职责] M-011 模块初始化，导出 FSRS 调度的公共接口（FSRSScheduler/AgainThrottle）
[所属模块] M-011（来自 DD-001）
[关联设计规范] FS-M-011 / MD-M-011（来自 DD-001）
[功能描述]
  功能1: 导出 FSRSScheduler 单例接口（schedule_card/update_card/get_due_cards）
  功能2: 导出 AgainThrottle 节流接口（is_throttled/record_again/reset_throttle）
  功能3: 定义模块级异常类型 E01101（数据损坏）/ E01102（节流触发）
[输入输出]
  输入: 无（仅作为命名空间与导出声明）
  输出: 对外可见的类与异常类型
[依赖关系]
  依赖文件: ./scheduler.py / ./throttle.py / ../shared/exceptions.py
  被依赖文件: M-009 教学编排（schedule_card）/ M-013 长期记忆（节流审计引用）
[注意事项]
  注意1: 本模块不对外暴露 py-fsrs 内部细节（避免 py-fsrs 升级影响调用方）
  注意2: FSRSScheduler 必须 Singleton（FSRS 内部状态如 desired_retention 全进程共享）
  注意3: 导出列表保持精简（仅 2 类 + 2 异常），避免命名空间污染
[代码风格] 遵循 CS-AITutor-V3.1（4空格缩进、Google Docstring、snake_case）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-011 - 初始模块导出声明
[作者] DD-M-011-20260602
[来源标注] [DD-001:FS-M-011] + [DD-M推断:依据=M-004/M-010 公共接口导出范式]
"""

# 标准库
# （无标准库导入）

# 第三方库
# （无第三方库导入，避免在 __init__ 直接绑定第三方依赖）

# 本地模块 - 子模块导入
from aitutor.fsrs.scheduler import FSRSScheduler, FSRSCard
from aitutor.fsrs.throttle import AgainThrottle, ThrottleRecord

# 异常类型（来自 shared 层，避免 fsrs 模块内部重新定义）
from aitutor.shared.exceptions import FSRSCorruptedError, AgainThrottledError

# 公共导出列表（白名单控制，防止意外泄露内部实现）
__all__ = [
    "FSRSScheduler",
    "FSRSCard",
    "AgainThrottle",
    "ThrottleRecord",
    "FSRSCorruptedError",
    "AgainThrottledError",
]
