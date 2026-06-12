"""test_throttle - AgainThrottle 节流 + 计数 + 审计日志测试

> 对应模块: M-011
> 关联测试策略: 单元测试 5+ 用例（核心 2 + 边界 2 + 异常 1）
> 关联异常: EX-018（Again 节流）/ E01102
> 来源标注: [DD-001:MD-M-011 测试策略] + [DD-001:EX-018]

[文件路径] tests/unit/test_fsrs/test_throttle.py
[文件职责] 覆盖 AgainThrottle 节流窗口、计数告警、reset、统计
[所属模块] M-011
[关联设计规范] MD-M-011 / EX-018
[功能描述]
  功能1: 5min 窗口内 is_throttled=True 验证
  功能2: 5min 窗口外 is_throttled=False 验证
  功能3: 计数超过 3 写 audit_log 验证
  功能4: 多卡隔离验证
  功能5: reset_throttle 清理验证
[输入输出]
  输入: card_id + 时间
  输出: is_throttled bool / 副作用（_records/_stats 更新）
[依赖关系]
  依赖文件: aitutor.fsrs.throttle / aitutor.monitor.logger(mocker) / pytest fixtures
[注意事项]
  注意1: 冻结时间使用 freezegun 或 clock fixture（避免 time.sleep）
  注意2: 计数>3 写 audit_log 的验证需要 mock logger
  注意3: 进程内 _records 不持久化，每个 case 必须 new AgainThrottle()
[代码风格] 遵循 CS-AITutor-V3.1
[创建日期] 2026-06-02
[作者] DD-M-011-20260602
[来源标注] [DD-001:EX-018] + [DD-001:MD-M-011 测试策略]
"""

# 标准库
import datetime

# 第三方库
import pytest

# 本地模块
from aitutor.fsrs.throttle import AgainThrottle


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def fresh_throttle() -> AgainThrottle:
    """每个 case 重新构造 AgainThrottle（_records 不持久化）。"""


@pytest.fixture
def clock() -> datetime.datetime:
    """固定基准时间 fixture。"""


# ============================================================
# 测试场景注释
# ============================================================

# [测试场景1: 5min 内重复 Again]
# [断言: 第一次 record_again 后第二次 is_throttled=True]
# [Mock: 无（基于真实时间窗口）]
# [来源标注: DD-001:EX-018 + MD-M-011]
def test_is_throttled_within_5min(fresh_throttle: AgainThrottle) -> None:
    """5min 内重复 Again 触发节流。"""


# [测试场景2: 5min 后允许]
# [断言: 推进时间到 5min 后 is_throttled=False]
# [Mock: 时钟注入（freezegun 或 clock fixture）]
# [来源标注: DD-001:EX-018]
def test_is_throttled_expires_after_cooldown(
    fresh_throttle: AgainThrottle,
    clock: datetime.datetime,
) -> None:
    """5min 后节流窗口失效。"""


# [测试场景3: 计数>3 触发 audit_log]
# [断言: 第 4 次 record_again 触发 audit_log 写入（mock 验证）]
# [Mock: aitutor.monitor.logger.get_logger]
# [来源标注: DD-001:EX-018 + SEC-013]
def test_audit_log_triggered_when_count_exceeds_threshold(
    fresh_throttle: AgainThrottle,
    mocker: pytest.MockerFixture,
) -> None:
    """Again 计数>3 触发 audit_log 写入。"""


# [测试场景4: 多卡隔离]
# [断言: card_A 节流不影响 card_B]
# [Mock: 无]
# [来源标注: [DD-M推断:依据=EX-018 多卡隔离]]
def test_multi_card_isolation(fresh_throttle: AgainThrottle) -> None:
    """不同卡片节流记录互不影响。"""


# [测试场景5: reset_throttle 清理]
# [断言: reset_throttle 后 is_throttled=False + _records 不含该 card]
# [Mock: 无]
# [来源标注: [DD-M推断:依据=节流可重置]]
def test_reset_throttle_clears_record(fresh_throttle: AgainThrottle) -> None:
    """reset_throttle 清除单卡节流记录。"""


# [测试场景6: get_throttle_stats 统计]
# [断言: 多次 record_again 后 stats.throttled_count / tracked_cards 正确]
# [Mock: 无]
# [来源标注: [DD-M推断:依据=监控埋点]]
def test_get_throttle_stats_aggregates(fresh_throttle: AgainThrottle) -> None:
    """ThrottleStats 聚合正确。"""
