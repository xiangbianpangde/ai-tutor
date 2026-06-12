"""test_scheduler - FSRSScheduler 单例 + 调度逻辑测试

> 对应模块: M-011
> 关联测试策略: 单元测试 10 用例（核心 4 + 边界 4 + 异常 2）
> 覆盖率目标: ≥80%
> 来源标注: [DD-001:MD-M-011 测试策略] + [CS-AITutor-V3.1 §6 测试规范]

[文件路径] tests/unit/test_fsrs/test_scheduler.py
[文件职责] 覆盖 FSRSScheduler 单例、schedule_card、update_card、get_due_cards 全路径
[所属模块] M-011
[关联设计规范] MD-M-011
[功能描述]
  功能1: Singleton 工厂行为测试
  功能2: schedule_card 全 grade 取值（1~4）测试
  功能3: grade 越界异常测试（E01101）
  功能4: get_due_cards 时区/边界测试
[输入输出]
  输入: 构造好的 FSRSCard + grade
  输出: 调度后的 FSRSCard
[依赖关系]
  依赖文件: aitutor.fsrs.scheduler / aitutor.shared.exceptions / pytest fixtures(conftest)
[注意事项]
  注意1: Singleton 测试必须在每个 case 间调用 reset_singleton_fixture 防止污染
  注意2: py-fsrs 1.0+ Card 用 dataclass，构造需带完整字段
  注意3: Clock fixture 注入 now 参数，避免 datetime.utcnow() 不稳定
[代码风格] 遵循 CS-AITutor-V3.1
[创建日期] 2026-06-02
[作者] DD-M-011-20260602
[来源标注] [DD-001:MD-M-011 测试策略 10 用例]
"""

# 标准库
import datetime

# 第三方库
import pytest

# 本地模块
from aitutor.fsrs.scheduler import FSRSScheduler, FSRSCard
from aitutor.shared.exceptions import FSRSCorruptedError


# ============================================================
# Fixtures（[DD-M推断:依据=conftest 共享注入]）
# ============================================================

@pytest.fixture
def reset_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个 case 前重置 FSRSScheduler._instance，确保 Singleton 隔离。"""


@pytest.fixture
def clock() -> datetime.datetime:
    """固定基准时间 fixture，避免 datetime.utcnow() 不稳定。"""


# ============================================================
# 测试场景注释
# ============================================================

# [测试场景1: 正常 schedule（grade=3 Good）]
# [断言: 返回的 FSRSCard.next_due > now]
# [Mock: 无（py-fsrs 真实计算）]
# [来源标注: DD-001:MD-M-011 测试策略核心 1]
def test_schedule_card_grade_good() -> None:
    """Good 评分后 next_due 推进到未来。"""


# [测试场景2: Singleton 校验]
# [断言: 多次 get_default_scheduler() 返回同一对象（id 相同）]
# [Mock: 无]
# [来源标注: DD-001:MD-M-011 Singleton 设计 + [DD-M推断:依据=Singleton 模式]]
def test_singleton_returns_same_instance(reset_singleton: None) -> None:
    """FSRSScheduler 全进程唯一。"""


# [测试场景3: 数据损坏（grade=0 越界）]
# [断言: 抛出 FSRSCorruptedError（错误码 E01101）]
# [Mock: 无（依赖入参校验）]
# [来源标注: DD-001:EX-018 + MD-M-011 异常处理]
def test_schedule_card_grade_out_of_range_raises() -> None:
    """grade 越界触发 E01101。"""


# [测试场景4: grade 边界 1/4（Again/Easy）]
# [参数化: @pytest.mark.parametrize("grade", [1, 2, 3, 4])]
# [断言: schedule 返回的 card.review_count += 1 + 字段合法]
# [Mock: 无]
# [来源标注: DD-001:MD-M-011 测试策略边界 4]
@pytest.mark.parametrize("grade", [1, 2, 3, 4])
def test_schedule_card_all_grades(grade: int) -> None:
    """全 4 个 grade 取值均能正常调度。"""


# [测试场景5: get_due_cards 时区/边界]
# [断言: next_due <= now 的卡被过滤 + 列表按 next_due 升序]
# [Mock: Clock fixture 固定 now]
# [来源标注: DD-001:MD-M-011 测试策略 + [DD-M推断:依据=IC-002 fsrs_update 事件]]
def test_get_due_cards_filters_by_due_time(clock: datetime.datetime) -> None:
    """get_due_cards 仅返回到期卡，按 next_due 升序。"""


# [测试场景6: Singleton 跨线程并发]
# [断言: 多线程并发 get_default_scheduler 返回同一对象]
# [Mock: threading.Barrier 控制并发起点]
# [来源标注: [DD-M推断:依据=Singleton 并发安全]]
def test_singleton_thread_safety() -> None:
    """Singleton 在多线程下保持唯一。"""
