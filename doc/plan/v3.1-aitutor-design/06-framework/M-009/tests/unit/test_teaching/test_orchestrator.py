"""test_orchestrator - TeachingOrchestrator 单元测试

[文件路径] tests/unit/test_teaching/test_orchestrator.py
[文件职责] 教学编排器单测：覆盖 next_step/dispatch_action/teach_feynman/schedule_fsrs
[所属模块] M-009 测试（来自 DD-001）
[关联设计规范] MD-009（来自 DD-001）
[测试场景与断言]
  场景1: 正常 LEARN 推进
    断言: next_step 返回 next_action="feynman" 且 next_state="LEARN"
    Mock: state_machine、dispatcher（M-010/M-011/M-012 mock）
  场景2: FSM 卡死
    断言: 抛出 TeachingFSMStuckError（E00902）
    Mock: state_machine 强制无转换
  场景3: Feynman 评分失败兜底
    断言: 返回 success=False、error_code="E00901"
    Mock: feynman.scorer 抛 FeynmanScoreError
  场景4: FSRS 版本低提示
    断言: 返回 error_code="E00903"
    Mock: fsrs.scheduler 抛 FSRSVersionError
  场景5: 并发 next_step 同 session
    断言: 无 race condition，最终状态一致
    Mock: 注入 asyncio 抖动
  场景6: 空 user_id
    断言: 抛 ValidationError
    Mock: 无
  场景7: 兜底 LLM 路径
    断言: fsm_fallback=True
    Mock: dispatcher 走 fallback
[Mock 策略] unittest.mock / pytest-mock；外部依赖用 MagicMock 注入
[代码风格] 遵循 CS-AITutor-V3.1
[创建日期] 2026-06-02
[作者] DD-M-M-009-20260602
[来源标注] [DD-001:MD-009] + [DD-M推断:依据=M-009 测试策略 15 用例]
"""

from __future__ import annotations

import pytest

# 预留：DD-S 将补全 from aitutor.teaching.orchestrator import TeachingOrchestrator
# 预留：from aitutor.teaching.state_machine import TeachingStateMachine, TeachingFSMStuckError


class TestTeachingOrchestratorNextStep:
    """TeachingOrchestrator.next_step 测试集"""

    def test_next_step_idle_to_learn_normal(self) -> None:
        """[测试场景] 场景1 正常 LEARN 推进
        [断言] next_action="feynman" 且 next_state="LEARN"
        [Mock] state_machine、dispatcher"""
        # TODO: DD-S 将在此填充实现
        pytest.skip("DD-S 待实现")

    def test_next_step_fsm_stuck_raises(self) -> None:
        """[测试场景] 场景2 FSM 卡死
        [断言] 抛出 TeachingFSMStuckError（E00902）
        [Mock] state_machine 强制无转换"""
        # TODO: DD-S 将在此填充实现
        pytest.skip("DD-S 待实现")


class TestTeachingOrchestratorDispatch:
    """TeachingOrchestrator.dispatch_action 测试集"""

    def test_dispatch_feynman_failure_fallback(self) -> None:
        """[测试场景] 场景3 Feynman 评分失败兜底
        [断言] success=False、error_code="E00901"
        [Mock] feynman.scorer 抛 FeynmanScoreError"""
        # TODO: DD-S 将在此填充实现
        pytest.skip("DD-S 待实现")

    def test_dispatch_fsrs_version_low(self) -> None:
        """[测试场景] 场景4 FSRS 版本低提示
        [断言] error_code="E00903"
        [Mock] fsrs.scheduler 抛 FSRSVersionError"""
        # TODO: DD-S 将在此填充实现
        pytest.skip("DD-S 待实现")

    def test_dispatch_unknown_action_falls_back(self) -> None:
        """[测试场景] 场景7 兜底 LLM 路径
        [断言] fsm_fallback=True
        [Mock] dispatcher 走 fallback"""
        # TODO: DD-S 将在此填充实现
        pytest.skip("DD-S 待实现")


class TestTeachingOrchestratorConcurrency:
    """TeachingOrchestrator 并发与边界测试集"""

    def test_concurrent_next_step_same_session(self) -> None:
        """[测试场景] 场景5 并发 next_step 同 session
        [断言] 无 race condition，最终状态一致
        [Mock] 注入 asyncio 抖动"""
        # TODO: DD-S 将在此填充实现
        pytest.skip("DD-S 待实现")

    def test_empty_user_id_raises(self) -> None:
        """[测试场景] 场景6 空 user_id
        [断言] 抛 ValidationError
        [Mock] 无"""
        # TODO: DD-S 将在此填充实现
        pytest.skip("DD-S 待实现")
