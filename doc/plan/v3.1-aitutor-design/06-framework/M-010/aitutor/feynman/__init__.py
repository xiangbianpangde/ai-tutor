"""aitutor.feynman - 费曼评分模块入口

> 对应模块: M-010 费曼评分
> 关联接口: IC-002（学习回合 — action=learn 触发费曼评分）
> 关联选型: TS-006 httpx / TS-001 Python
> 设计模式: Strategy（评分策略可替换：LLM 评分 / 规则评分 / 混合评分）
> 来源标注: [DD-001:FS-010] + [DD-001:MD-010]

[文件路径]      src/aitutor/feynman/__init__.py
[文件职责]      M-010 包入口；仅导出公共接口，不含业务实现
[所属模块]      M-010
[关联设计规范]   FS-010 / MD-010 / IC-002
[功能描述]
  功能1: 公共接口 re-export（FeynmanScorer / FeynmanPromptBuilder / ScoreParser）
  功能2: 工厂函数 build_feynman_scorer（封装依赖装配）
[输入输出]
  输入: 无（包级初始化）
  输出: 公共类型 / 工厂函数
[依赖关系]
  依赖文件: scorer.py / prompt.py / parser.py（同模块内）
  被依赖文件: aitutor/teaching/orchestrator.py（M-009 跨模块调用，仅通过包入口）
[注意事项]
  注意1: 严禁内部实现细节外泄；外部仅通过 __all__ 暴露
  注意2: 跨模块依赖仅向上提供调用入口，不反向 import M-009
  注意3: 避免循环导入，使用 TYPE_CHECKING 守卫类型引用
[代码风格]     遵循 CS（Ruff + Google docstring + snake_case 文件名）
[创建日期]     2026-06-02
[修改历史]     2026-06-02: DD-M-010 - 初始版本（注释骨架）
[作者]         DD-M-010-20260602
[来源标注]     [DD-001:FS-010] + [DD-001:MD-010]
"""
# [DD-M推断:依据=Python src layout 最佳实践 + Import Linter contract 1/2]
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # 类型检查阶段导入，运行期不触发，避免与 scorer.py 循环
    # [DD-M推断:依据=CS 4.2 禁止循环导入 + soul R26]
    from aitutor.feynman.parser import ScoreParser
    from aitutor.feynman.prompt import FeynmanPromptBuilder
    from aitutor.feynman.scorer import FeynmanScore, FeynmanScorer


# 公共导出清单
# [来源标注] [DD-001:MD-010] 三类设计 + [DD-001:FS-010] 三文件命名
__all__: list[str] = [
    "FeynmanPromptBuilder",
    "FeynmanScore",
    "FeynmanScorer",
    "ScoreParser",
    "build_feynman_scorer",  # 工厂函数（DD-M推断：封装依赖装配）
]


def build_feynman_scorer(
    prompt_template: str | None = None,
    score_range: tuple[int, int] = (0, 5),
) -> "FeynmanScorer":
    """构造 FeynmanScorer 工厂。

    [职责] ≤30 字：封装 Scorer + PromptBuilder + Parser 装配
    [关联接口契约] [DD-001:MD-010] FeynmanScorer 属性 [prompt_template, score_range]

    Args:
        prompt_template: 评分 Prompt 模板，None 时使用默认模板（DD-M推断）
        score_range: 评分区间，默认 (0, 5)（来源 MD-010 类属性）

    Returns:
        FeynmanScorer: 装配完毕的评分器实例

    Note:
        [DD-M推断:依据=MD-010 三类协作关系；工厂模式由 DD-M 引入以支持 DI 测试]
        [来源标注] [DD-001:MD-010] + [DD-M推断:DI 友好性]
    """
    raise NotImplementedError  # 由 DD-S/DEV 实现（仅注释骨架）
