"""fallback - Pipeline 兜底策略

> 对应模块: M-007
> 关联接口: IC-002（学习回合）
> 关联选型: TS-001 Python
> 来源标注: [DD-001:FS-M-007/MD-M-007/IC-002]

[文件职责]  Pipeline 整体失败 / FSM 卡死时的 10% LLM 兜底
[所属模块]  M-007（Pipeline 调度）
[关联设计规范]  MD-M-007 异常处理 E00702/E00703 / 状态机 *→[error]→LLM_FALLBACK
[功能描述]
  功能1: 触发条件判定（FSM 卡死 / 整体失败 / 任一阶段 5s 超时）
  功能2: 调用 LLM 直答（无 RAG 上下文）
  功能3: 标记 fsm_fallback=True
[输入输出]
  输入: query / state / 失败原因
  输出: PipelineResult（fsm_fallback=True）
[依赖关系]
  依赖文件: ./state.py、./stages/llm.py、aitutor.monitor.logger
  被依赖文件: ./orchestrator.py
[注意事项]
  注意1: 兜底必须经 audit_log 记录原因
  注意2: 兜底场景禁止递归触发兜底（避免死循环）
[代码风格]  CS-AITutor-V3.1-20260602
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-007 - 初始框架注释
[作者]  DD-M-007-20260602
[来源标注]  [DD-001:MD-M-007 异常处理 E00702]
"""
import time
from dataclasses import dataclass
from typing import Optional

from aitutor.monitor.logger import StructuredLogger
from aitutor.pipeline.state import PipelineStage, PipelineState
from aitutor.pipeline.stages.llm import LLMStage
from aitutor.shared.types import PipelineResult


# ============================================================
# 类注释
# ============================================================

@dataclass
class FallbackStrategy:
    """[类名] FallbackStrategy

    [职责]  Pipeline 兜底策略（10% 触发）
    [关联设计规范]  MD-M-007 异常处理 E00702/E00703 / 状态机 *→[error]→LLM_FALLBACK

    [属性]
      属性1: llm_stage LLMStage - LLM 阶段实例（用于直答）
      属性2: logger StructuredLogger - 结构化日志
      属性3: audit_enabled bool - 是否写 audit_log（默认 True）
      属性4: max_retry int - 兜底重试上限（默认 1）

    [方法列表]
      方法1: should_fallback(state) -> bool - 是否触发兜底
      方法2: execute_fallback(query, state) -> PipelineResult - 执行兜底
      方法3: write_audit(state, reason) -> None - 写 audit_log

    [状态机]
      任意状态 → [should_fallback=True] → LLM_FALLBACK

    [异常处理]
      异常1: E00702 PipelineFallbackError - 整体失败
      异常2: E00703 PipelineStuckError - FSM 卡死

    [来源标注]  [DD-001:MD-M-007 异常处理 E00702 行] + [DD-001:MD-M-007 状态机 *→[error]→LLM_FALLBACK 行]
    """
    llm_stage: Optional[LLMStage] = None
    logger: Optional[StructuredLogger] = None
    audit_enabled: bool = True
    max_retry: int = 1


# ============================================================
# 函数注释
# ============================================================

def should_fallback(state: PipelineState) -> bool:
    """[函数名] should_fallback

    [职责]  判定是否触发兜底
    [关联接口契约]  无

    [参数说明]
      参数1: state PipelineState 必填 管线状态

    [返回值]
      类型:  bool
      描述:  True = 触发兜底（FSM 卡死 / round>3 / 阶段超时累计 ≥2）
      特殊值:  False = 正常继续

    [错误码]
      错误码1: 无

    [前置条件]  state 非空
    [后置条件]  无副作用
    [并发安全]  是
    [幂等性]  是
    [性能约束]  O(1)
    [示例]
      ```python
      if should_fallback(state):
          result = await execute_fallback(query, state)
      ```
    [来源标注]  [DD-001:MD-M-007 异常处理 E00702] + [DD-001:MD-M-007 状态机 *→[error]→LLM_FALLBACK]
    """
    # [DD-001:MD-M-007 状态机] 任意状态可转 LLM_FALLBACK
    # [DD-001:MD-M-007 异常处理 E00703] 卡死触发
    # [DD-M推断:依据=IC-002 性能约束] 累计超时触发
    pass


async def execute_fallback(query: str, state: PipelineState) -> PipelineResult:
    """[函数名] execute_fallback

    [职责]  执行 LLM 兜底（无 RAG 上下文）
    [关联接口契约]  IC-002（学习回合）

    [参数说明]
      参数1: query str 必填 用户问题
      参数2: state PipelineState 必填 管线状态（用于 audit_log）

    [返回值]
      类型:  PipelineResult
      描述:  含 answer（LLM 直答）、fsm_fallback=True、sources=[]
      特殊值:  None 表示兜底也失败

    [错误码]
      错误码1: E00702 PipelineFallbackError - 兜底也失败（极少见）

    [前置条件]  LLM Provider 可达
    [后置条件]  audit_log 写入（fallback_reason）
    [并发安全]  是
    [幂等性]  是
    [性能约束]  ≤4s
    [示例]
      ```python
      result = await execute_fallback(query, state)
      ```
    [来源标注]  [DD-001:MD-M-007 异常处理 E00702 行]
    """
    # [DD-001:MD-M-007 异常处理 E00702] 整体失败兜底
    # [DD-001:IC-002 出参 fsm_fallback] 标记 True
    # [DD-M推断:依据=IC-002 audit_log] 写 audit
    # [DD-M推断:依据=IC-002 sources] 兜底无 sources
    pass


def write_audit(state: PipelineState, reason: str) -> None:
    """[函数名] write_audit

    [职责]  写 audit_log 记录兜底原因
    [关联接口契约]  无

    [参数说明]
      参数1: state PipelineState 必填 管线状态
      参数2: reason str 必填 兜底原因（FSM 卡死 / 整体失败 / 超时）

    [返回值]
      类型:  None
      描述:  写入 aitutor_monitor.audit_log
      特殊值:  无

    [错误码]
      错误码1: AuditLogWriteError - 写失败（不阻塞主流程，仅 WARN）

    [前置条件]  state.trace_id 非空
    [后置条件]  audit_log 持久化
    [并发安全]  是（SQLite WAL）
    [幂等性]  是
    [性能约束]  ≤50ms
    [示例]
      ```python
      write_audit(state, "FSM stuck at RETRIEVE")
      ```
    [来源标注]  [DD-001:MD-M-007 异常处理 E00703 行] + [DD-001:IC-002 audit_log]
    """
    # [DD-001:MD-M-007 异常处理 E00703] 兜底写 audit
    # [DD-001:IC-002 后置条件] audit_log 记录
    # [DD-M推断:依据=SQLite WAL] 持久化策略
    pass
