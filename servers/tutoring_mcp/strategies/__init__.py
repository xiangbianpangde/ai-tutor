"""教学策略合集 + 工厂函数。

6 种策略（详见 specs/teaching-strategy-formalism.md）:
- reduction          降阶法
- feynman            费曼法
- socratic           苏格拉底法
- analogy            类比桥接
- pbl                项目驱动法
- spaced_repetition  间隔复习
"""
from __future__ import annotations

from shared.errors import TutorError

from .analogy import AnalogyStrategy
from .base import Strategy
from .feynman import FeynmanStrategy
from .jiangjie import JiangjieStrategy
from .pbl import PBLStrategy
from .reduction import ReductionStrategy, ReductionStub
from .socratic import SocraticStrategy
from .spaced_repetition import SpacedRepetitionStrategy

_REGISTRY: dict[str, type[Strategy]] = {
    "reduction": ReductionStrategy,
    "jiangjie": JiangjieStrategy,
    "feynman": FeynmanStrategy,
    "socratic": SocraticStrategy,
    "analogy": AnalogyStrategy,
    "pbl": PBLStrategy,
    "spaced_repetition": SpacedRepetitionStrategy,
}


def get_strategy(name: str) -> Strategy:
    """按 name 取一个策略实例。未知 name → DEPENDENCY_MISSING。"""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise TutorError(
            "DEPENDENCY_MISSING",
            hint=f"未知策略: {name!r}（支持: {', '.join(_REGISTRY)}）",
        )
    return cls()


def list_strategies() -> list[str]:
    return list(_REGISTRY.keys())


__all__ = [
    "Strategy",
    "ReductionStrategy",
    "ReductionStub",
    "JiangjieStrategy",
    "FeynmanStrategy",
    "SocraticStrategy",
    "AnalogyStrategy",
    "PBLStrategy",
    "SpacedRepetitionStrategy",
    "get_strategy",
    "list_strategies",
]
