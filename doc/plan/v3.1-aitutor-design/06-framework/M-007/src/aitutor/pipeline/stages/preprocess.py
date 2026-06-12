"""preprocess - 阶段1: query 预处理

> 对应模块: M-007
> 关联接口: IC-002（学习回合）
> 关联选型: TS-001 Python
> 来源标注: [DD-001:FS-M-007/MD-M-007/IC-002]

[文件职责]  query 分词 + 特征提取
[所属模块]  M-007（Pipeline 调度）
[关联设计规范]  MD-M-007 子模块 sm007-preprocess / 类设计 PreprocessStage 行
[功能描述]
  功能1: 分词（jieba）
  功能2: 关键词提取（TF-IDF）
  功能3: 意图识别（rule-based 关键字匹配）
  功能4: 实体识别（人名 / 公式 / 章节号）
[输入输出]
  输入: 原始 query 字符串
  输出: QueryFeatures 数据类
[依赖关系]
  依赖文件: aitutor.shared.types
  被依赖文件: ../orchestrator.py
[注意事项]
  注意1: 长度 [1, 2000] 校验（来自 IC-002）
  注意2: 单阶段超时 200ms
[代码风格]  CS-AITutor-V3.1-20260602
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-007 - 初始框架注释
[作者]  DD-M-007-20260602
[来源标注]  [DD-001:MD-M-007 PreprocessStage]
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from aitutor.shared.types import QueryFeatures


class BaseStage(ABC):
    """[类名] BaseStage

    [职责]  Stage 抽象基类
    [关联设计规范]  [DD-M推断:依据=Pipeline 模式]
    """
    @abstractmethod
    async def run(self, input_data):  # noqa: ANN001
        """抽象方法：运行阶段。"""


@dataclass
class PreprocessStage(BaseStage):
    """[类名] PreprocessStage

    [职责]  阶段1 query 预处理
    [关联设计规范]  MD-M-007 类设计 PreprocessStage 行

    [属性]
      属性1: max_length int - 最大长度（默认 2000，对应 IC-002）

    [方法列表]
      方法1: run(query) -> QueryFeatures - 主入口
      方法2: tokenize(query) -> list[str] - 分词
      方法3: extract_keywords(tokens) -> list[str] - 关键词提取
      方法4: detect_intent(query) -> str - 意图识别

    [异常处理]
      异常1: ValidationError - query 长度越界

    [来源标注]  [DD-001:MD-M-007 PreprocessStage]
    """
    max_length: int = 2000

    async def run(self, query: str) -> QueryFeatures:
        """[函数名] run

        [职责]  执行预处理
        [关联接口契约]  IC-002（学习回合）

        [参数说明]
          参数1: query str 必填 用户问题

        [返回值]
          类型:  QueryFeatures
          描述:  含 keywords / intent / entities / lang
          特殊值:  无

        [错误码]
          错误码1: ValidationError - query 长度越界

        [前置条件]  query 非空
        [后置条件]  QueryFeatures 进入 retrieve 阶段
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤200ms
        [来源标注]  [DD-001:MD-M-007 函数签名 preprocess 行]
        """
        # [DD-001:MD-M-007 函数签名 preprocess] 阶段 1 入口
        # [DD-001:IC-002 入参 query 长度 [1, 2000]]
        # [DD-M推断:依据=DD洞察-001] 提取 keywords + intent 供 M-008 routing 使用
        pass

    async def tokenize(self, query: str) -> list[str]:
        """[函数名] tokenize

        [职责]  分词（jieba）
        [关联接口契约]  无

        [参数说明]
          参数1: query str 必填

        [返回值]
          类型:  list[str]
          描述:  token 列表
          特殊值:  空列表表示无可分词

        [错误码]
          错误码1: 无

        [前置条件]  query 非空
        [后置条件]  无副作用
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤50ms
        [来源标注]  [DD-M推断:依据=M-007 阶段 1 实现]
        """
        # [DD-M推断:依据=M-007 阶段 1] jieba 分词
        pass

    async def extract_keywords(self, tokens: list[str]) -> list[str]:
        """[函数名] extract_keywords

        [职责]  关键词提取（TF-IDF）
        [关联接口契约]  无

        [参数说明]
          参数1: tokens list[str] 必填 分词结果

        [返回值]
          类型:  list[str]
          描述:  关键词列表（去重 + 排序）
          特殊值:  空列表表示无关键词

        [错误码]
          错误码1: 无

        [前置条件]  tokens 非空
        [后置条件]  无副作用
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤80ms
        [来源标注]  [DD-M推断:依据=M-007 阶段 1 实现]
        """
        # [DD-M推断:依据=M-008 routing] 关键词供路由决策
        pass

    async def detect_intent(self, query: str) -> str:
        """[函数名] detect_intent

        [职责]  意图识别（rule-based）
        [关联接口契约]  无

        [参数说明]
          参数1: query str 必填 原始 query

        [返回值]
          类型:  str
          描述:  意图标签（learn/review/explain/compare）
          特殊值:  未知意图返回 "unknown"

        [错误码]
          错误码1: 无

        [前置条件]  query 非空
        [后置条件]  无副作用
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤30ms
        [来源标注]  [DD-M推断:依据=M-007 阶段 1 + M-008 routing]
        """
        # [DD-M推断:依据=IC-002 action Literal] 意图对齐 action
        pass
