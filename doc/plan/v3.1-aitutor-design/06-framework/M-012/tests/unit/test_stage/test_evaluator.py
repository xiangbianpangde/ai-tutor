"""test_evaluator - M-012 StageEvaluator / evaluate_stage 单元测试

> 对应模块: M-012 阶段校准（evaluator）
> 关联选型: TS-017 pytest
> 测试策略: 8 用例（核心 4 + 边界 3 + 异常 1）/ 覆盖率≥80%
> 来源标注: [DD-001:MD-012 测试策略] + [DD-M推断:依据=M-012 测试场景拆分]

[文件职责] 阶段评估器测试：覆盖正常/边界/异常三类场景
[所属模块] M-012（来自DD-001）
[关联设计规范] MD-012 / FS-012（来自DD-001）
[输入输出]
  输入: pytest 框架调用（无显式入参）
  输出: 测试结果报告
[依赖关系]
  依赖文件: src/aitutor/stage/evaluator.py
  被依赖文件: 无
[注意事项]
  注意1: 使用 freezegun 或构造 date 序列避免日期相关 flaky
  注意2: Mock 策略：mock Performance 对象即可，无需 patch 时间
  注意3: 测试场景与 M-012 测试策略对齐（核心/边界/异常）
[代码风格] 遵循CS-AITutor-V3.1
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-012 - 初始版本
[作者] DD-M-012-2026-06-02
[来源标注] [DD-001:MD-012] + [DD-M推断:依据=M-012 测试策略]
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from aitutor.stage.evaluator import (
    DailySample,
    Performance,
    StageEvaluator,
    evaluate_stage,
)


# ---------- Fixtures ----------

@pytest.fixture
def high_perf() -> Performance:
    """[fixture] high_perf - 高表现用户（应升档）"""
    today = date(2026, 6, 1)
    samples = [
        DailySample(day=today - timedelta(days=i), score=0.95)
        for i in range(7)
    ]
    return Performance(
        user_id="u_high",
        accuracy=0.95,
        avg_response_seconds=10.0,
        retention_rate=0.90,
        samples=samples,
        current_stage=3,
    )


@pytest.fixture
def low_perf() -> Performance:
    """[fixture] low_perf - 低表现用户（应降档）"""
    today = date(2026, 6, 1)
    samples = [
        DailySample(day=today - timedelta(days=i), score=0.20)
        for i in range(7)
    ]
    return Performance(
        user_id="u_low",
        accuracy=0.30,
        avg_response_seconds=55.0,
        retention_rate=0.20,
        samples=samples,
        current_stage=3,
    )


@pytest.fixture
def insufficient_perf() -> Performance:
    """[fixture] insufficient_perf - 数据不足用户"""
    return Performance(
        user_id="u_insufficient",
        accuracy=0.8,
        avg_response_seconds=15.0,
        retention_rate=0.7,
        samples=[],  # 无样本 → 触发 E01201
        current_stage=2,
    )


# ---------- 核心测试场景 ----------

# [测试场景1: 正常流程-高表现升档] [断言: 返回档位 >= current_stage] [Mock: 无]
def test_evaluate_high_performance_upgrades_stage(high_perf: Performance) -> None:
    """[测试场景] 高表现用户评估应升档
    [断言] 返回值 > 3（current_stage=3 时升档）
    [Mock] 无（纯函数逻辑）
    [来源标注] [DD-001:MD-012 测试策略 核心 4]
    """
    evaluator = StageEvaluator()
    new_stage = evaluator.evaluate(high_perf)
    assert new_stage > high_perf.current_stage
    assert 1 <= new_stage <= 5


# [测试场景2: 正常流程-低表现降档] [断言: 返回档位 < current_stage] [Mock: 无]
def test_evaluate_low_performance_downgrades_stage(low_perf: Performance) -> None:
    """[测试场景] 低表现用户评估应降档
    [断言] 返回值 < 3
    [Mock] 无
    [来源标注] [DD-001:MD-012 测试策略 核心 4]
    """
    evaluator = StageEvaluator()
    new_stage = evaluator.evaluate(low_perf)
    assert new_stage < low_perf.current_stage
    assert 1 <= new_stage <= 5


# [测试场景3: 正常流程-默认参数] [断言: evaluate_stage 与 StageEvaluator().evaluate 一致] [Mock: 无]
def test_evaluate_stage_top_level_equivalent(high_perf: Performance) -> None:
    """[测试场景] 顶层函数 evaluate_stage 与 StageEvaluator 默认行为一致
    [断言] 两次调用结果相同
    [Mock] 无
    [来源标注] [DD-001:MD-012 测试策略 核心 4]
    """
    result_top = evaluate_stage(high_perf)
    result_class = StageEvaluator().evaluate(high_perf)
    assert result_top == result_class


# [测试场景4: 正常流程-综合得分聚合] [断言: to_score 输出在 [0,1]] [Mock: 无]
def test_performance_to_score_in_range(high_perf: Performance) -> None:
    """[测试场景] Performance.to_score 综合得分聚合
    [断言] 0 <= score <= 1
    [Mock] 无
    [来源标注] [DD-001:MD-012 测试策略 核心 4]
    """
    score = high_perf.to_score()
    assert 0.0 <= score <= 1.0


# ---------- 边界测试场景 ----------

# [测试场景5: 边界-数据不足] [断言: 返回 current_stage, 不抛异常] [Mock: 无]
def test_evaluate_insufficient_data_keeps_current(insufficient_perf: Performance) -> None:
    """[测试场景] 数据不足时保持当前档位（E01201）
    [断言] 返回 current_stage=2
    [Mock] 无
    [来源标注] [DD-001:MD-012 异常处理 E01201]
    """
    evaluator = StageEvaluator()
    assert evaluator.evaluate(insufficient_perf) == 2


# [测试场景6: 边界-滞回防抖] [断言: 单次高分但最近 2 天低于阈值，保持原档] [Mock: 无]
def test_evaluate_hysteresis_prevents_jitter() -> None:
    """[测试场景] Hysteresis 2 天窗口防抖
    [断言] 当 tail 不满足阈值时不转换
    [Mock] 无
    [来源标注] [DD-001:MD-012 hysteresis=2d] + [DD-M推断:依据=防抖场景]
    """
    today = date(2026, 6, 1)
    # 前 5 天高分，最近 2 天低分
    samples = (
        [DailySample(day=today - timedelta(days=i), score=0.9) for i in range(2, 7)]
        + [DailySample(day=today - timedelta(days=1), score=0.3)]
        + [DailySample(day=today, score=0.3)]
    )
    perf = Performance(
        user_id="u_jitter",
        accuracy=0.85,
        avg_response_seconds=15.0,
        retention_rate=0.8,
        samples=samples,
        current_stage=3,
    )
    evaluator = StageEvaluator()
    new_stage = evaluator.evaluate(perf)
    # 由于最近 2 天不满足升档阈值，应保持 current_stage
    assert new_stage == 3


# [测试场景7: 边界-accuracy 越界] [断言: 抛 ValueError] [Mock: 无]
def test_performance_invalid_accuracy_raises() -> None:
    """[测试场景] accuracy 超出 [0,1] 应抛 ValueError
    [断言] 抛出 ValueError
    [Mock] 无
    [来源标注] [DD-M推断:依据=__post_init__ 校验]
    """
    with pytest.raises(ValueError, match="accuracy 越界"):
        Performance(
            user_id="u",
            accuracy=1.5,
            avg_response_seconds=10.0,
            retention_rate=0.5,
            samples=[],
            current_stage=1,
        )


# ---------- 异常测试场景 ----------

# [测试场景8: 异常-StageEvaluator 构造参数非法] [断言: 抛 ValueError] [Mock: 无]
def test_evaluator_invalid_window_raises() -> None:
    """[测试场景] StageEvaluator 构造参数非法
    [断言] window<1 时抛 ValueError
    [Mock] 无
    [来源标注] [DD-M推断:依据=__init__ 校验]
    """
    with pytest.raises(ValueError, match="window 必须 >= 1"):
        StageEvaluator(window=0)


# [测试场景9: 异常-滞回参数非法] [断言: 抛 ValueError] [Mock: 无]
def test_evaluator_invalid_hysteresis_raises() -> None:
    """[测试场景] hysteresis 越界
    [断言] 抛 ValueError
    [Mock] 无
    [来源标注] [DD-M推断:依据=__init__ 校验]
    """
    with pytest.raises(ValueError, match="hysteresis 必须在"):
        StageEvaluator(window=5, hysteresis=5)
