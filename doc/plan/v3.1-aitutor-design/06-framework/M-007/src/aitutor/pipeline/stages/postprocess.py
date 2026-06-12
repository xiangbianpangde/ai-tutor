"""postprocess - 阶段5: 答案后处理

> 对应模块: M-007
> 关联接口: IC-002（学习回合）
> 关联选型: TS-001 Python
> 来源标注: [DD-001:FS-M-007/MD-M-007/IC-002]

[文件职责]  答案后处理（引用源拼装 / 格式整理）
[所属模块]  M-007（Pipeline 调度）
[关联设计规范]  MD-M-007 子模块 sm007-postprocess / 类设计 PostprocessStage 行
[功能描述]
  功能1: 替换占位符 [1]/[2] 为引用源
  功能2: 拼装 sources 列表
  功能3: 异常时返回原文 + WARN
[输入输出]
  输入: str 原始答案
  输出: str 最终答案
[依赖关系]
  依赖文件: aitutor.shared.types、aitutor.pipeline.stages.preprocess
  被依赖文件: ../orchestrator.py
[注意事项]
  注意1: 单阶段超时 50ms
  注意2: 不阻塞主流程，失败仅 WARN
[代码风格]  CS-AITutor-V3.1-20260602
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-007 - 初始框架注释
[作者]  DD-M-007-20260602
[来源标注]  [DD-001:MD-M-007 PostprocessStage]
"""
from dataclasses import dataclass

from aitutor.shared.types import Chunk, SourceRef
from aitutor.pipeline.stages.preprocess import BaseStage


@dataclass
class PostprocessStage(BaseStage):
    """[类名] PostprocessStage

    [职责]  阶段5 答案后处理
    [关联设计规范]  MD-M-007 类设计 PostprocessStage 行

    [属性]
      属性1: sources list[SourceRef] - 引用源列表
      属性2: max_refs int - 最大引用数（默认 5）

    [方法列表]
      方法1: run(answer) -> str - 主入口
      方法2: _replace_placeholders(answer) -> str - 替换占位符
      方法3: _build_sources_section() -> str - 拼装引用源段落

    [异常处理]
      异常1: E00701 Stage 失败 - 跳过引用拼装返回原文

    [来源标注]  [DD-001:MD-M-007 PostprocessStage]
    """
    sources: list = None  # type: ignore[assignment]
    max_refs: int = 5

    async def run(self, answer: str) -> str:
        """[函数名] run

        [职责]  执行后处理
        [关联接口契约]  IC-002（学习回合）

        [参数说明]
          参数1: answer str 必填 LLM 原始答案

        [返回值]
          类型:  str
          描述:  最终答案（含引用源段落）
          特殊值:  None 表示处理失败（回退原文）

        [错误码]
          错误码1: E00701 Stage 失败

        [前置条件]  answer 非空
        [后置条件]  最终答案返回 PipelineResult.answer
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤50ms
        [来源标注]  [DD-001:MD-M-007 函数签名 postprocess 行] + [DD-001:IC-002]
        """
        # [DD-001:MD-M-007 函数签名 postprocess] 阶段 5 入口
        # [DD-001:IC-002 出参 answer/sources] 引用源拼装
        # [DD-M推断:依据=IC-002 sources List[SourceRef]] 输出对齐
        pass

    async def _replace_placeholders(self, answer: str) -> str:
        """[函数名] _replace_placeholders

        [职责]  替换 [1]/[2] 占位符为引用标注
        [关联接口契约]  无

        [参数说明]
          参数1: answer str 必填

        [返回值]
          类型:  str
          描述:  替换后的答案

        [错误码]
          错误码1: 无

        [前置条件]  sources 非空
        [后置条件]  无副作用
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤20ms
        [来源标注]  [DD-M推断:依据=IC-002 sources]
        """
        # [DD-M推断:依据=IC-002 sources 字段] 占位符→引用源
        pass

    async def _build_sources_section(self) -> str:
        """[函数名] _build_sources_section

        [职责]  拼装引用源段落
        [关联接口契约]  IC-002

        [参数说明]
          参数1: 无

        [返回值]
          类型:  str
          描述:  引用源 markdown 段落

        [错误码]
          错误码1: 无

        [前置条件]  sources 非空
        [后置条件]  无副作用
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤10ms
        [来源标注]  [DD-001:IC-002 sources 字段]
        """
        # [DD-001:IC-002 sources 字段] 输出格式
        pass
