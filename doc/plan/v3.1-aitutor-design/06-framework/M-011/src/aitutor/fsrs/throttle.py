"""throttle - Again 频繁触发的 5min/卡 节流

> 对应模块: M-011
> 关联接口: IC-002（学习回合，Again 节流保护）
> 关联选型: TS-007 py-fsrs 周边
> 关联设计: 节流 = 时间窗口（300s）+ 计数上限（>3 写 audit_log）
> 关联异常: E01102（节流触发 → 计数 + 拒绝）
> 来源标注: [DD-001:MD-M-011] + [DD-001:EX-018] + [DD-001:SEC-013]

[文件路径] src/aitutor/fsrs/throttle.py
[文件职责] 防止同一张卡在 5min 内被 Again 评分轰炸，记录节流审计
[所属模块] M-011（来自 DD-001）
[关联设计规范] MD-M-011 / EX-018（来自 DD-001）
[功能描述]
  功能1: AgainThrottle 类，对单卡 5min 窗口内 Again 调用做节流
  功能2: ThrottleRecord 内部记录：card_id / last_again_ts / again_count
  功能3: is_throttled 查询是否在节流窗口内
  功能4: record_again 记录一次 Again 事件并更新计数
  功能5: 计数>3 触发 audit_log 写入（与 EX-018 配合）
[输入输出]
  输入: card_id (str) / 调取时间（datetime）
  输出: 是否节流（bool）/ 节流统计（ThrottleStats）
[依赖关系]
  依赖文件: aitutor.shared.types / aitutor.monitor.logger
  被依赖文件: M-009 教学编排（is_throttled 判定）/ FS-M-011 __init__.py
[注意事项]
  注意1: 节流窗口 300s（5min）是 EX-018 硬约束，不允许调整
  注意2: 进程内内存持有（不持久化，重启清空；如需跨进程应改用 Redis，但 M-011 暂不依赖）
  注意3: ThrottleRecord 字典大小需要监控（防内存膨胀 → 后续可加 LRU）
  注意4: 计数>3 写 audit_log 属于「预期行为告警」，不阻塞流程
[代码风格] 遵循 CS-AITutor-V3.1
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-011 - 初始文件框架注释
[作者] DD-M-011-20260602
[来源标注] [DD-001:MD-M-011/EX-018] + [DD-M推断:依据=SEC-013 审计]
"""

# 标准库
import datetime
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

# 本地模块
from aitutor.shared.types import TraceId
from aitutor.monitor.logger import get_logger

# 模块级 logger
_logger = get_logger(__name__)

# 常量（节流硬约束，EX-018）
_COOLDOWN_SECONDS: int = 300
_AGAIN_ALERT_THRESHOLD: int = 3


# ============================================================
# 数据类注释
# ============================================================

# [类名] ThrottleRecord
# [职责] 单卡节流记录数据载体
# [关联设计规范] MD-M-011
# [属性]
#   属性1: card_id str 卡片 ID
#   属性2: last_again_ts datetime 最近一次 Again 触发时间
#   属性3: again_count int 累计 Again 触发次数（仅统计节流窗口外的累计，超 3 写 audit_log 后仍递增）
#   属性4: first_again_ts datetime 首次 Again 时间（用于统计持续节流时长）
# [来源标注] [DD-M推断:依据=EX-018 节流计数需求]
@dataclass
class ThrottleRecord:
    """Again 节流记录（内存持有）。"""

    card_id: str
    last_again_ts: datetime.datetime
    again_count: int = 1
    first_again_ts: datetime.datetime = field(default_factory=datetime.datetime.utcnow)


# [类名] ThrottleStats
# [职责] 节流统计聚合（监控埋点）
# [关联设计规范] MD-M-011 + EX-018
# [属性]
#   属性1: total_again_events int 累计 Again 事件数
#   属性2: throttled_count int 累计被节流次数
#   属性3: alerted_count int 累计触发 audit_log 告警次数
#   属性4: tracked_cards int 当前追踪的卡数
# [来源标注] [DD-M推断:依据=Prom 监控埋点]
@dataclass
class ThrottleStats:
    """节流统计聚合对象。"""

    total_again_events: int = 0
    throttled_count: int = 0
    alerted_count: int = 0
    tracked_cards: int = 0


# ============================================================
# 类注释
# ============================================================

# [类名] AgainThrottle
# [职责] Again 节流控制（5min/卡 + 计数告警）
# [关联设计规范] MD-M-011 + EX-018
# [属性]
#   属性1: _records Dict[str, ThrottleRecord] 卡片节流记录表
#   属性2: _stats ThrottleStats 全局统计
#   属性3: _lock threading.Lock 写并发保护
#   属性4: _cooldown_seconds int 冷却窗口（默认 300）
#   属性5: _alert_threshold int 告警阈值（默认 3）
# [方法列表]
#   方法1: is_throttled(card_id, now) -> bool - 查询是否在节流窗口
#   方法2: record_again(card_id, now) -> None - 记录 Again 事件
#   方法3: reset_throttle(card_id) -> None - 重置单卡节流记录
#   方法4: get_throttle_stats() -> ThrottleStats - 拉取统计
# [状态机] N/A
# [异常处理]
#   异常1: AgainThrottledError - 节流命中（EX-018 业务异常，调用方应捕获并 skip）
# [并发安全] 是（threading.Lock 保护 _records 字典读写）
# [来源标注] [DD-001:MD-M-011/EX-018]
class AgainThrottle:
    """Again 评分节流器（5min/卡，>3 计数告警）

    防止用户对同一张卡在短时间反复「Again」触发 FSRS 频繁重置，
    同时统计 again 频率写入 audit_log。
    """

    def __init__(
        self,
        cooldown_seconds: int = _COOLDOWN_SECONDS,
        alert_threshold: int = _AGAIN_ALERT_THRESHOLD,
    ) -> None:
        """初始化节流器（cooldown 与 threshold 可由测试覆盖）。"""

    # [函数名] is_throttled
    # [职责] 查询指定卡片是否处于节流窗口
    # [关联接口契约] IC-002（学习回合，Again 节流）
    # [参数说明]
    #   参数1: card_id str 必填 卡片 ID [校验: UUIDv4]
    #   参数2: now datetime 可选 默认 datetime.utcnow() 基准时间
    # [返回值]
    #   类型: bool
    #   描述: True=在节流窗口（应拒绝）/ False=不在窗口（可处理）
    #   特殊值: 卡片无记录返回 False
    # [错误码] 无
    # [前置条件] card_id 非空
    # [后置条件] 无副作用
    # [并发安全] 是（读锁）
    # [幂等性] 是
    # [性能约束] ≤1ms（字典查询 O(1)）
    # [来源标注] [DD-001:EX-018] + [DD-001:MD-M-011]
    def is_throttled(
        self,
        card_id: str,
        now: Optional[datetime.datetime] = None,
    ) -> bool:
        """判断卡片是否处于节流窗口。"""

    # [函数名] record_again
    # [职责] 记录一次 Again 事件，更新节流记录与统计
    # [关联接口契约] IC-002
    # [参数说明]
    #   参数1: card_id str 必填 卡片 ID
    #   参数2: now datetime 可选 默认 datetime.utcnow()
    #   参数3: trace_id TraceId 可选 用于 audit_log 关联
    # [返回值]
    #   类型: None
    #   描述: 无返回值；副作用：更新 _records / _stats / 可能写 audit_log
    # [错误码]
    #   错误码1: E01102 含义: 节流触发（仅日志，无异常）触发: count 累计
    # [前置条件] card_id 非空
    # [后置条件] _records 字典新增或更新对应 entry
    # [并发安全] 是（写锁）
    # [幂等性] 否（每次调用都累加计数）
    # [性能约束] ≤2ms
    # [来源标注] [DD-001:EX-018] + [DD-001:SEC-013]
    def record_again(
        self,
        card_id: str,
        now: Optional[datetime.datetime] = None,
        trace_id: Optional[TraceId] = None,
    ) -> None:
        """记录一次 Again 触发事件。"""

    # [函数名] reset_throttle
    # [职责] 清除单卡的节流记录（用于管理员手动重置 / 单元测试清理）
    # [参数说明]
    #   参数1: card_id str 必填 卡片 ID
    # [返回值]
    #   类型: None
    # [错误码] 无
    # [并发安全] 是（写锁）
    # [幂等性] 是（不存在的 card_id 静默 no-op）
    # [性能约束] ≤1ms
    # [来源标注] [DD-M推断:依据=EX-018 节流可清理]
    def reset_throttle(self, card_id: str) -> None:
        """重置单卡节流记录。"""

    # [函数名] get_throttle_stats
    # [职责] 拉取节流统计快照（监控埋点）
    # [参数说明] 无
    # [返回值]
    #   类型: ThrottleStats
    #   描述: 当前聚合统计
    # [并发安全] 是（原子快照）
    # [幂等性] 是
    # [性能约束] ≤1ms
    # [来源标注] [DD-M推断:依据=EX-018 监控需求]
    def get_throttle_stats(self) -> ThrottleStats:
        """返回节流统计快照。"""
