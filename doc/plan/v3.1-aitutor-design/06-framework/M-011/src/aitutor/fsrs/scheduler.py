"""scheduler - FSRS 算法封装（Singleton）

> 对应模块: M-011
> 关联接口: IC-002（学习回合，grade 取值 1~4，对应 Again/Hard/Good/Easy）
> 关联选型: TS-007 py-fsrs==1.0.0
> 关联设计: Singleton（FSRSScheduler 全进程唯一，调度参数全进程一致）
> 关联异常: E01101（FSRS 数据损坏 → 重建卡 + ERROR 日志）
> 来源标注: [DD-001:MD-M-011/FS-M-011] + [DD-001:EX-018] + [DD-M推断:依据=py-fsrs Singleton 最佳实践]

[文件路径] src/aitutor/fsrs/scheduler.py
[文件职责] 封装 py-fsrs 算法，对外提供 schedule/update/get_due 接口（Singleton）
[所属模块] M-011（来自 DD-001）
[关联设计规范] MD-M-011 / FS-M-011（来自 DD-001）
[功能描述]
  功能1: FSRSScheduler 单例类，封装 py-fsrs.Scheduler 实例
  功能2: schedule_card 根据 grade(1~4) 计算 next_due/difficulty/stability
  功能3: update_card 更新已有卡片的 FSRS 参数（用于 FSM REVIEW 阶段）
  功能4: get_due_cards 过滤出 next_due<=now 的待复习卡
  功能5: 处理 E01101 数据损坏异常（重建卡 + ERROR 日志）
[输入输出]
  输入: FSRSCard（卡片状态）/ grade（1=Again, 2=Hard, 3=Good, 4=Easy）
  输出: 更新后的 FSRSCard（含 next_due 字段）
[依赖关系]
  依赖文件: py-fsrs（第三方）/ aitutor.shared.exceptions / aitutor.monitor.logger
  被依赖文件: M-009 教学编排（schedule_fsrs）/ FS-M-011 __init__.py
[注意事项]
  注意1: Singleton 实例由 get_default_scheduler() 工厂方法返回，禁止直接实例化
  注意2: grade 越界（<1 或 >4）必须抛出 FSRSCorruptedError，不允许默默修正
  注意3: schedule_card 是无状态函数（仅修改入参 card 副本并返回），不修改原对象
  注意4: py-fsrs Scheduler 内部状态由 Singleton 持有，跨请求共享
  注意5: FSRSCard 字段对齐 py-fsrs Card schema（防止 py-fsrs 升级 schema 漂移）
[代码风格] 遵循 CS-AITutor-V3.1（Google Docstring + type hints + 4空格缩进）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-011 - 初始文件框架注释
[作者] DD-M-011-20260602
[来源标注] [DD-001:MD-M-011/FS-M-011] + [DD-M推断:依据=Singleton 模式]
"""

# 标准库
import datetime
from typing import List, Optional

# 第三方库
import fsrs  # TS-007 py-fsrs==1.0.0
from fsrs import Scheduler as _PyFsrsScheduler
from fsrs import Card as _PyFsrsCard
from fsrs import Rating  # 1=Again, 2=Hard, 3=Good, 4=Easy

# 本地模块
from aitutor.shared.exceptions import FSRSCorruptedError
from aitutor.shared.types import TraceId
from aitutor.monitor.logger import get_logger

# 模块级 logger（structlog，遵循 EX-018 审计日志规范）
_logger = get_logger(__name__)


# ============================================================
# 类注释
# ============================================================

# [类名] FSRSCard
# [职责] FSRS 卡片数据载体（包装 py-fsrs Card）
# [关联设计规范] MD-M-011（来自 DD-001）
# [属性]
#   属性1: card_id str 卡片唯一 ID（UUIDv4）
#   属性2: py_card _PyFsrsCard py-fsrs 内部 Card 对象
#   属性3: last_grade Optional[int] 上次评分（1~4）
#   属性4: last_review_at Optional[datetime] 上次复习时间
#   属性5: next_due datetime 下次到期时间（schedule_card 后填充）
#   属性6: review_count int 累计复习次数
# [方法列表]
#   方法1: to_dict() -> dict - 序列化为 dict（用于持久化）
#   方法2: from_dict(data: dict) -> FSRSCard - 从 dict 反序列化（用于持久化恢复）
# [异常处理]
#   异常1: FSRSCorruptedError - 卡片数据反序列化失败
# [来源标注] [DD-001:MD-M-011] + [DD-M推断:依据=py-fsrs Card schema]
class FSRSCard:
    """FSRS 卡片（py-fsrs Card 的语义层封装）"""

    def __init__(
        self,
        card_id: str,
        py_card: _PyFsrsCard,
        last_grade: Optional[int] = None,
        last_review_at: Optional[datetime.datetime] = None,
        review_count: int = 0,
    ) -> None:
        """初始化 FSRS 卡片。"""

    def to_dict(self) -> dict:
        """序列化为 dict（用于 SQLite 持久化）。"""

    @classmethod
    def from_dict(cls, data: dict) -> "FSRSCard":
        """从 dict 反序列化。"""


# [类名] FSRSScheduler（Singleton）
# [职责] FSRS 算法单例封装，提供 schedule_card/update_card/get_due_cards
# [关联设计规范] MD-M-011（来自 DD-001）
# [属性]
#   属性1: _instance Optional[FSRSScheduler] Singleton 实例持有
#   属性2: _scheduler _PyFsrsScheduler py-fsrs Scheduler 内部实例
#   属性3: _default_retention float 期望保留率（默认 0.9）
#   属性4: _enable_fuzzing bool 是否启用时间抖动（防聚集）
# [方法列表]
#   方法1: schedule_card(card: FSRSCard, grade: int) -> FSRSCard - 计算下次到期
#   方法2: update_card(card: FSRSCard, grade: int) -> FSRSCard - 更新卡片参数
#   方法3: get_due_cards(cards: List[FSRSCard], now: datetime) -> List[FSRSCard] - 过滤到期卡
#   方法4: get_default_scheduler() -> FSRSScheduler - Singleton 工厂（类方法）
# [状态机] N/A（无状态机，FSRS 算法本身无显式状态转换）
# [异常处理]
#   异常1: FSRSCorruptedError - grade 越界 / card 字段损坏
#   异常2: ValueError - 入参 None 校验
# [并发安全] 是（Singleton 实例 + 内部 py-fsrs Scheduler 线程安全；py-fsrs 1.0+ 文档保证）
# [来源标注] [DD-001:MD-M-011] + [DD-M推断:依据=Singleton 模式]
class FSRSScheduler:
    """FSRS 调度器（Singleton）

    封装 py-fsrs 算法，对外暴露稳定接口，屏蔽 py-fsrs 版本升级影响。
    全进程唯一实例由 get_default_scheduler() 返回。
    """

    _instance: Optional["FSRSScheduler"] = None
    _default_retention: float = 0.9
    _enable_fuzzing: bool = True

    def __init__(self) -> None:
        """私有初始化（外部请使用 get_default_scheduler）。"""

    # [函数名] schedule_card
    # [职责] 根据 grade(1~4) 计算卡片的 next_due/difficulty/stability
    # [关联接口契约] IC-002（学习回合，grade 参数）
    # [参数说明]
    #   参数1: card FSRSCard 必填 待调度的卡片
    #   参数2: grade int 必填 1=Again, 2=Hard, 3=Good, 4=Easy [校验: 1<=grade<=4]
    #   参数3: now datetime 可选 默认 datetime.utcnow() 调度基准时间
    # [返回值]
    #   类型: FSRSCard
    #   描述: 新卡片（next_due 字段已更新）
    #   特殊值: 异常时抛出 FSRSCorruptedError
    # [错误码]
    #   错误码1: E01101 含义: 卡片数据损坏 触发: grade 越界 / card 字段为 None
    # [前置条件] Singleton 实例已初始化
    # [后置条件] 返回的 FSRSCard.next_due > now
    # [并发安全] 是
    # [幂等性] 否（相同输入 + 不同时间 → 不同 next_due；同输入同时间 → 幂等）
    # [性能约束] ≤10ms（py-fsrs 内部 O(1) 调度）
    # [来源标注] [DD-001:MD-M-011] + [DD-001:EX-018]
    def schedule_card(
        self,
        card: FSRSCard,
        grade: int,
        now: Optional[datetime.datetime] = None,
    ) -> FSRSCard:
        """根据评分调度卡片的下次到期时间。"""

    # [函数名] update_card
    # [职责] 更新卡片 FSRS 参数（不重置 next_due，供 FSM REVIEW 阶段使用）
    # [关联接口契约] IC-002（学习回合）
    # [参数说明]
    #   参数1: card FSRSCard 必填 待更新的卡片
    #   参数2: grade int 必填 1=Again, 2=Hard, 3=Good, 4=Easy [校验: 1<=grade<=4]
    # [返回值]
    #   类型: FSRSCard
    #   描述: 更新后的卡片（difficulty/stability/review_count 变化）
    # [错误码]
    #   错误码1: E01101 含义: 卡片数据损坏 触发: grade 越界
    # [前置条件] card 已 schedule_card 过一次
    # [后置条件] card.review_count += 1
    # [并发安全] 是
    # [幂等性] 否（review_count 单调递增）
    # [性能约束] ≤5ms
    # [来源标注] [DD-001:MD-M-011] + [DD-M推断:依据=FSRS 内部语义]
    def update_card(
        self,
        card: FSRSCard,
        grade: int,
    ) -> FSRSCard:
        """更新卡片 FSRS 内部参数（difficulty/stability/review_count）。"""

    # [函数名] get_due_cards
    # [职责] 过滤出 next_due<=now 的待复习卡列表
    # [关联接口契约] IC-002（学习回合，FSRS due 事件）
    # [参数说明]
    #   参数1: cards List[FSRSCard] 必填 候选卡池
    #   参数2: now datetime 可选 默认 datetime.utcnow() 基准时间
    # [返回值]
    #   类型: List[FSRSCard]
    #   描述: 过滤后的待复习卡（按 next_due 升序）
    #   特殊值: 无到期卡时返回 []
    # [错误码] 无
    # [前置条件] cards 列表非 None
    # [后置条件] 返回列表按 next_due 升序
    # [并发安全] 是（纯函数）
    # [幂等性] 是（相同输入 + 相同 now → 相同结果）
    # [性能约束] 1000 卡 ≤50ms
    # [来源标注] [DD-001:MD-M-011] + [DD-M推断:依据=IC-002 fsrs_update 事件]
    def get_due_cards(
        self,
        cards: List[FSRSCard],
        now: Optional[datetime.datetime] = None,
    ) -> List[FSRSCard]:
        """过滤出到期卡片。"""

    # [函数名] get_default_scheduler
    # [职责] Singleton 工厂方法，返回全进程唯一 FSRSScheduler 实例
    # [关联接口契约] N/A（模块级工厂）
    # [参数说明] 无
    # [返回值]
    #   类型: FSRSScheduler
    #   描述: Singleton 实例（首次调用创建，后续调用直接返回）
    # [错误码] 无
    # [前置条件] 无
    # [后置条件] 模块级 _instance 不为 None
    # [并发安全] 是（双重检查锁，DD-M 推断）
    # [幂等性] 是（重复调用返回同一对象）
    # [性能约束] ≤1ms
    # [来源标注] [DD-M推断:依据=Singleton 模式双重检查锁]
    @classmethod
    def get_default_scheduler(cls) -> "FSRSScheduler":
        """返回 Singleton 实例。"""
