"""教学策略抽象基类。

合同来源: ai-tutor-system-design/specs/teaching-strategy-formalism.md

设计:
- 6 种策略（reduction / feynman / socratic / pbl / analogy / spaced_repetition）
  各自实现一个状态机。Spine 切片只实现 ReductionStub（最简单）。
- start(): 初始化状态机
- get_action(): 当前状态对应的 TeachingAction
- transition(event, payload): 状态机迁移；event 列表见各策略 spec
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from shared.schemas import Concept, TeachingAction


class Strategy(ABC):
    """所有教学策略的基类。子类必须实现 3 个抽象方法 + 设 name。

    引擎集成约定（P1 #4）：
    - TERMINAL_STATES：达到这些状态表示"本概念教学完成"，引擎据此切下一个概念。
    - FLAG_STATES：达到这些状态表示"卡住，建议换策略"。
    - export_state/restore_state：引擎每轮从 ctx 无损重建策略实例所需的内部状态
      （state + 各策略自己的计数器/产出）。带内部计数器的策略必须 override。
    """

    name: ClassVar[str] = "base"
    # 教学完成态（默认 NEXT；各策略按自己的终止态覆盖）
    TERMINAL_STATES: ClassVar[frozenset[str]] = frozenset({"NEXT"})
    # 卡住态
    FLAG_STATES: ClassVar[frozenset[str]] = frozenset({"FLAG_DIFFICULT"})
    # export_state 额外要持久化的实例属性名（基类只存 state + attempt_count）
    STATE_FIELDS: ClassVar[tuple[str, ...]] = ()

    def __init__(self) -> None:
        self.state: str = "IDLE"
        self.target: Concept | None = None
        self.attempt_count: int = 0

    @abstractmethod
    def start(
        self,
        *,
        target: Concept,
        mastery_map: dict[str, float],
        params: dict[str, Any],
    ) -> None:
        """开始教学一个目标概念。设置 target、加载 params、进入第一个状态。"""

    @abstractmethod
    def get_action(self) -> TeachingAction:
        """返回当前状态对应的下一个 TeachingAction。"""

    @abstractmethod
    def transition(self, *, event: str, payload: dict[str, Any]) -> None:
        """处理外部事件（学生答题、超时、求助等），推动状态机。"""

    # ------------------------------------------------------------------ #
    # 引擎集成：完成检测 + 状态序列化
    # ------------------------------------------------------------------ #
    def advance_event(self) -> str | None:
        """当前状态若是"纯讲解/展示"态（不等学生作答），返回推动它前进的事件名；
        否则返回 None（表示该状态在等学生 respond，由 'answered' 推进）。

        引擎的 advance() tool 据此让 host 在讲解步骤后继续，而问答步骤走 respond。
        默认 None：多数精简策略的展示态本就靠 'answered' 推进（respond 即可）。"""
        return None

    def is_complete(self) -> bool:
        """本概念是否教学完成（引擎据此推进到下一概念）。"""
        return self.state in self.TERMINAL_STATES

    def is_flagged(self) -> bool:
        """是否卡住（引擎可据此换策略）。"""
        return self.state in self.FLAG_STATES

    def export_state(self) -> dict[str, Any]:
        """导出可 JSON 序列化的内部状态，供引擎存进 ctx.strategy_internal。

        set 类字段统一转成排序后的 list（JSON 友好）；restore_state 负责转回。
        """
        out: dict[str, Any] = {"state": self.state, "attempt_count": self.attempt_count}
        for field in self.STATE_FIELDS:
            val = getattr(self, field, None)
            out[field] = sorted(val) if isinstance(val, set) else val
        return out

    def restore_state(self, data: dict[str, Any]) -> None:
        """从 export_state 的输出还原内部状态（只设存在的键）。

        约定：必须在 start() 之后调用——set 类字段（如 jiangjie.weak_atoms）靠
        当前属性已是 set 才能从 list 还原回 set。引擎在 _make_strategy 里恒为
        start() → restore_state 顺序，调用方勿打破。
        """
        if not data:
            return
        if "state" in data:
            self.state = data["state"]
        if "attempt_count" in data:
            self.attempt_count = int(data["attempt_count"])
        for field in self.STATE_FIELDS:
            if field in data:
                cur = getattr(self, field, None)
                val = data[field]
                # 原本是 set 的字段还原成 set
                setattr(self, field, set(val) if isinstance(cur, set) else val)
