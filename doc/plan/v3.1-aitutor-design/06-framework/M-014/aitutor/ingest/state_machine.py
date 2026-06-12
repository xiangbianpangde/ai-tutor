"""state_machine - M-014 数据管线 FSM 状态机

> 对应模块: M-014
> 关联接口: IC-004（数据入库）
> 来源标注: [DD-001:MD-M014] + [DD-M推断:依据=FSM 经典实现]

[文件职责] 实现 M-014 数据管线运行阶段的状态机（7 节点 + 转移规则）
[所属模块] M-014
[关联设计规范] MD-M014 / IC-004
[功能描述]
  功能1: 定义 7 个状态节点（PENDING/TRANSLATING/CLEANING/CLEANING_PARTIAL/CHUNKING/INGESTING/READY/FAILED）
  功能2: 校验转移合法性（拒绝非法转移）
  功能3: 暴露 transition(event) 接口供 DataPipeline 驱动
  功能4: 暴露 is_terminal() 接口判断终态
[输入输出]
  输入: DataPipeline 调用 transition(event="start"/"done"/"fail")
  输出: 返回新的 PipelineStage；非法转移抛出 PipelineStateError
[依赖关系]
  依赖文件: aitutor/ingest/models.py（PipelineStage 枚举）
  被依赖文件: aitutor/ingest/pipeline.py（主调度驱动 FSM）
[注意事项]
  注意1: 状态机为单实例（每次 PDF 任务创建独立实例）
  注意2: 状态转移必须包含 trace_id 用于审计日志
  注意3: 终态（READY / FAILED）拒绝任何转移
  注意4: PENDING 状态只能由 [start] 事件转移（DD-001:MD-M014 状态机定义）
[代码风格] 遵循 CS-AITutor-V3.1（来自DD-001）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-014 - 初始版本
[作者] DD-M-014-20260602
[来源标注] [DD-001:MD-M014 状态机定义]
"""

# ================================
# 1. 标准库导入
# ================================
from typing import Dict, Literal, Optional, Set, Tuple

# ================================
# 2. 第三方库导入
# ================================
# (无)

# ================================
# 3. 本地模块导入
# ================================
from aitutor.ingest.exceptions import IngestError
from aitutor.ingest.models import PipelineStage


# ============================================================
# 自定义异常：状态机非法转移
# ============================================================


class PipelineStateError(IngestError):
    """FSM 非法转移异常

    [DD-M推断:依据=状态机通用异常类型]
    """

    def __init__(
        self,
        message: str,
        *,
        current_stage: PipelineStage,
        attempted_event: str,
        trace_id: Optional[str] = None,
    ) -> None:
        """初始化 PipelineStateError。

        Args:
            message: 异常描述
            current_stage: 当前状态
            attempted_event: 尝试触发的事件
            trace_id: 追踪 ID（32hex，可选）
        """
        ...


# ============================================================
# 状态机实现
# ============================================================


class PipelineStateMachine:
    """M-014 数据管线 FSM 状态机

    [类] PipelineStateMachine
    [职责] 管控 PDF 入库管线 7 阶段状态转移
    [关联设计规范] MD-M014（状态机定义）

    属性:
        current_stage: 当前状态
        trace_id: 追踪 ID（32hex）
        history: 状态历史（用于审计）
    状态机:
        PENDING → [start] → TRANSLATING
        TRANSLATING → [done] → CLEANING
        TRANSLATING → [fail] → CLEANING_PARTIAL
        CLEANING → [done] → CHUNKING
        CHUNKING → [done] → INGESTING
        INGESTING → [done] → READY
        * → [fail] → FAILED
    异常处理:
        异常1: PipelineStateError - 非法转移（终态拒绝事件）
    [来源标注] [DD-001:MD-M014]
    """

    # 状态转移表（DD-001:MD-M014 状态机定义）
    _TRANSITIONS: Dict[PipelineStage, Dict[str, PipelineStage]] = {
        PipelineStage.PENDING: {"start": PipelineStage.TRANSLATING},
        PipelineStage.TRANSLATING: {
            "done": PipelineStage.CLEANING,
            "fail": PipelineStage.CLEANING_PARTIAL,
        },
        PipelineStage.CLEANING: {"done": PipelineStage.CHUNKING},
        PipelineStage.CLEANING_PARTIAL: {"done": PipelineStage.CHUNKING},
        PipelineStage.CHUNKING: {"done": PipelineStage.INGESTING},
        PipelineStage.INGESTING: {"done": PipelineStage.READY},
        PipelineStage.READY: {},
        PipelineStage.FAILED: {},
    }

    # 终态集合
    _TERMINAL_STAGES: Set[PipelineStage] = {PipelineStage.READY, PipelineStage.FAILED}

    def __init__(self, trace_id: str) -> None:
        """初始化 FSM。

        Args:
            trace_id: 追踪 ID（32hex）
        """
        ...

    @property
    def current_stage(self) -> PipelineStage:
        """当前状态（只读）。"""
        ...

    @property
    def history(self) -> Tuple[PipelineStage, ...]:
        """状态历史（只读）。"""
        ...

    def transition(self, event: str) -> PipelineStage:
        """触发状态转移

        Args:
            event: 事件名（start/done/fail/...）

        Returns:
            转移后的新状态

        Raises:
            PipelineStateError: 非法转移（当前状态不接受该事件或处于终态）
        """
        ...

    def is_terminal(self) -> bool:
        """判断是否处于终态

        Returns:
            True if current_stage in {READY, FAILED}
        """
        ...

    def force_fail(self, reason: str) -> PipelineStage:
        """强制转移至 FAILED 状态（任意状态下调用）

        Args:
            reason: 失败原因（用于审计日志）

        Returns:
            FAILED 状态
        """
        ...

    def snapshot(self) -> Dict[str, str]:
        """导出状态快照（用于持久化与审计）

        Returns:
            包含 current_stage / history / trace_id 的字典
        """
        ...
