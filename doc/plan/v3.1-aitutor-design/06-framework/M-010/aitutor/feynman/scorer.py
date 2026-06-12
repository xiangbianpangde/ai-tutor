"""aitutor.feynman.scorer - 费曼评分器（Strategy 主入口）

> 对应模块: M-010 费曼评分
> 关联接口: IC-002（学习回合 — 评分异常触发 E00901 → FSM 兜底 10%）
> 关联选型: TS-006 httpx（LLM 调用）/ TS-001 Python 3.11
> 设计模式: Strategy（评分策略可替换：LLM / 规则 / 混合）
> 来源标注: [DD-001:MD-010] + [DD-001:FS-010] + [AR:API-002 费曼]

[文件路径]      src/aitutor/feynman/scorer.py
[文件职责]      实现 FeynmanScorer 主类，编排 Prompt 构建→LLM 调用→响应解析
[所属模块]      M-010
[关联设计规范]   MD-010 类设计 / IC-002 学习回合 / FS-010 依赖关系
[功能描述]
  功能1: 同步/异步评分入口 score_feynman(question, user_answer) → FeynmanScore
  功能2: 子模块 sm010-score（LLM 评分 + 解析）实现
  功能3: 异常兜底：E01001 LLM 不可用→返回 0+WARN；E01002 解析失败→重试 1 次
[输入输出]
  输入: question: str（问题）/ user_answer: str（用户回答）
  输出: FeynmanScore（score: int [0,5], reasoning: str, raw: str）
[依赖关系]
  依赖文件: aitutor/feynman/prompt.py（FeynmanPromptBuilder）
            aitutor/feynman/parser.py（ScoreParser）
            aitutor/shared/exceptions.py（自定义异常）
            aitutor/monitor/logger.py（结构化日志）
            httpx（第三方）
  被依赖文件: aitutor/feynman/__init__.py（re-export）
              aitutor/teaching/orchestrator.py（M-009 跨模块调用）
[注意事项]
  注意1: 跨模块依赖 M-006 monitor/logger（trace_id 注入），文件头已声明
  注意2: LLM HTTP 调用必须 await + 超时控制（CS 7. 性能与并发）
  注意3: 异常必须 raise ... from e 保留链（CS 5.3 异常转换）
  注意4: 评分结果必须钳制到 score_range=(0, 5)（MD-010）
  注意5: 并发安全：无共享可变状态，天然线程安全（FeynmanScorer 实例可复用）
[代码风格]     CS（Ruff/PEP8/Google docstring/snake_case 函数/PascalCase 类）
[创建日期]     2026-06-02
[修改历史]     2026-06-02: DD-M-010 - 初始版本（注释骨架）
[作者]         DD-M-010-20260602
[来源标注]     [DD-001:MD-010] + [DD-001:IC-002] + [AR:API-002 费曼]
"""
# [DD-M推断:依据=CS 4.1 导入顺序 标准库→第三方→本地]
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from aitutor.feynman.parser import ScoreParser
    from aitutor.feynman.prompt import FeynmanPromptBuilder


# 评分区间常量（UPPER_SNAKE_CASE — CS 1. 命名规范）
# [来源标注] [DD-001:MD-010] FeynmanScorer.score_range=(0,5)
FEYNMAN_SCORE_MIN: Final[int] = 0
FEYNMAN_SCORE_MAX: Final[int] = 5

# LLM 调用超时（毫秒）
# [DD-M推断:依据=IC-002 单回合≤5s(P95)，扣除 RAG+其他 stage 后费曼评分预算约 1500ms]
LLM_REQUEST_TIMEOUT_MS: Final[int] = 1500
LLM_RETRY_TIMES: Final[int] = 1  # MD-010 E01002 重试 1 次


@dataclass(frozen=True, slots=True)
class FeynmanScore:
    """费曼评分结果（不可变值对象）。

    [类名] FeynmanScore
    [职责] 承载评分整数 + 推理理由 + 原始 LLM 响应
    [关联设计规范] [DD-001:MD-010] 函数 score_feynman → FeynmanScore
    [属性]
      属性1: score   int  评分整数 [0, 5]
      属性2: reasoning str  评分理由（≤200 字）
      属性3: raw      str  LLM 原始响应（debug 用）
      属性4: degraded bool 是否兜底（LLM 不可用时为 True）
    [方法列表]
      方法1: is_pass() → bool - 评分是否≥3（DD-M推断的及格阈值）
    [状态机] N/A
    [异常处理] N/A（值对象）
    [来源标注] [DD-001:MD-010] + [DD-M推断:dataclass frozen 保证不可变]
    """

    score: int
    reasoning: str
    raw: str
    degraded: bool = False

    def is_pass(self) -> bool:
        """评分是否达到及格阈值（≥3）。

        [职责] 提供及格判定，避免下游重复硬编码阈值
        [前置条件] score ∈ [0, 5]
        [后置条件] 返回布尔
        [来源标注] [DD-M推断:依据=MD-009 教学编排 LEARN→REVIEW 转移依赖及格判定]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现


class FeynmanScorer:
    """费曼评分器主类（Strategy 主入口）。

    [类名] FeynmanScorer
    [职责] 编排 Prompt 构建→LLM 调用→响应解析，对外暴露统一评分 API
    [关联设计规范] [DD-001:MD-010] FeynmanScorer 类设计
    [属性]
      属性1: _prompt_builder  FeynmanPromptBuilder  Prompt 构造器
      属性2: _parser          ScoreParser           响应解析器
      属性3: _score_range     tuple[int, int]       评分区间 (0, 5)
      属性4: _http_client     httpx.AsyncClient     LLM HTTP 客户端
    [方法列表]
      方法1: __init__(prompt_builder, parser, score_range, http_client) → None
      方法2: score_feynman(question, user_answer) → FeynmanScore
      方法3: _call_llm(prompt) → str（内部 LLM 调用，含重试）
      方法4: _clamp_score(raw_score) → int（钳制到评分区间）
    [状态机] N/A（无状态 Strategy）
    [异常处理]
      异常1: LLMUnavailableError - LLM 不可用（E01001）触发，返回 degraded=True 的 0 分
      异常2: ScoreParseError    - 响应解析失败（E01002），重试 1 次仍失败则返回 degraded=True
    [并发安全] 是（无共享可变状态；httpx.AsyncClient 内置连接池线程安全）
    [来源标注] [DD-001:MD-010] FeynmanScorer
    """

    def __init__(
        self,
        prompt_builder: FeynmanPromptBuilder,
        parser: ScoreParser,
        *,
        score_range: tuple[int, int] = (FEYNMAN_SCORE_MIN, FEYNMAN_SCORE_MAX),
        http_client: object | None = None,  # 实际类型 httpx.AsyncClient，避免 import 副作用
    ) -> None:
        """初始化 Scorer 实例。

        [职责] 依赖注入装配 Strategy 组件
        [参数说明]
          prompt_builder: FeynmanPromptBuilder 必填 Prompt 构造策略
          parser:         ScoreParser          必填 响应解析策略
          score_range:    tuple[int, int]     可选 评分区间，默认 (0, 5)
          http_client:    httpx.AsyncClient   可选 LLM 客户端（测试时 mock）
        [前置条件] 三个依赖均已实例化
        [后置条件] Scorer 可立即调用 score_feynman
        [来源标注] [DD-001:MD-010] + [DD-M推断:DI 友好]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    async def score_feynman(
        self,
        question: str,
        user_answer: str,
    ) -> FeynmanScore:
        """对用户的费曼式回答进行评分（公开主入口）。

        [函数名] score_feynman
        [职责] 单次评分主流程：Prompt→LLM→解析→钳制→返回
        [关联接口契约] [DD-001:MD-010] score_feynman(question, user_answer) → FeynmanScore
        [参数说明]
          question:    str 必填 教师/系统提出的问题（长度 [1, 2000]，校验由调用方负责）
          user_answer: str 必填 用户的费曼式解释（长度 [1, 2000]）
        [返回值]
          类型: FeynmanScore
          描述: 评分结果，含 score/reasoning/raw/degraded
          特殊值: degraded=True 表示走兜底（LLM 不可用或解析连续失败）
        [错误码]
          错误码1: E01001 LLM 不可用 - 抛出 LLMUnavailableError，由调用方记录 WARN 后兜底
          错误码2: E01002 响应解析失败 - 内部重试 1 次后仍败则 degraded=True
          错误码3: E00901 LLM 评分失败 - 调用方（M-009）将该异常映射为 FSM 兜底 10%
        [前置条件] question / user_answer 均非空
        [后置条件] 返回结果 score ∈ [0, 5]，degraded ∈ {True, False}
        [并发安全] 是（无共享可变状态，httpx.AsyncClient 池化）
        [幂等性] 是（同 input 返回相同 score 不保证，因 LLM 非确定；语义幂等即可）
        [性能约束] P95 ≤1500ms（来源 IC-002 单回合 5s 预算分摊）
        [示例]
            ```python
            scorer = build_feynman_scorer()
            result = await scorer.score_feynman(
                question="解释一下牛顿第二定律",
                user_answer="F = m * a，力等于质量乘以加速度...",
            )
            assert 0 <= result.score <= 5
            ```
        [来源标注] [DD-001:MD-010] + [DD-001:IC-002 错误码 E00901]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    async def _call_llm(self, prompt: str) -> str:
        """私有：调用 LLM HTTP 接口（含 1 次重试）。

        [职责] 仅负责 HTTP 通信 + 重试，不解析响应
        [参数说明]
          prompt: str 必填 完整 Prompt（已由 PromptBuilder 构造）
        [返回值] LLM 原始响应字符串
        [错误码]
          E01001 LLM 不可用 - 重试后仍失败 → LLMUnavailableError
        [并发安全] 是（httpx.AsyncClient 池化）
        [性能约束] 单次调用 ≤1500ms，重试间退避 200ms
        [来源标注] [DD-001:MD-010 sm010-score] + [DD-M推断:依据=IC-002 性能预算]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现

    def _clamp_score(self, raw_score: int) -> int:
        """私有：将解析得到的整数钳制到 [score_range]。

        [职责] 防御性钳制，避免下游接收越界值
        [参数说明]
          raw_score: int 必填 解析得到的原始分数（可能 <0 或 >5）
        [返回值] int 钳制后的分数
        [并发安全] 是（纯函数）
        [来源标注] [DD-001:MD-010 score_range=(0,5)] + [DD-M推断:依据=防御性编程]
        """
        raise NotImplementedError  # 由 DD-S/DEV 实现
