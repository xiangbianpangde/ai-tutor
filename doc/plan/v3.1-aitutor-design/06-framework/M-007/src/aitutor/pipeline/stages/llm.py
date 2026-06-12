"""llm - 阶段4: LLM 调用

> 对应模块: M-007
> 关联接口: IC-002（学习回合）
> 关联选型: TS-006 httpx
> 来源标注: [DD-001:FS-M-007/MD-M-007/IC-002]

[文件职责]  调用 LLM Provider 生成答案
[所属模块]  M-007（Pipeline 调度）
[关联设计规范]  MD-M-007 子模块 sm007-llm / 类设计 LLMStage 行
[功能描述]
  功能1: 构造 prompt（含上下文）
  功能2: httpx 异步调用 LLM Provider
  功能3: 流式 / 非流式支持
[输入输出]
  输入: list[Chunk] 上下文
  输出: str 原始答案
[依赖关系]
  依赖文件: aitutor.shared.types、aitutor.pipeline.stages.preprocess
  被依赖文件: ../orchestrator.py、../fallback.py
[注意事项]
  注意1: 单阶段超时 4s（剩余 1s 给 postprocess）
  注意2: LLM 不可用时由 fallback 兜底
[代码风格]  CS-AITutor-V3.1-20260602
[创建日期]  2026-06-02
[修改历史]
  2026-06-02: DD-M-007 - 初始框架注释
[作者]  DD-M-007-20260602
[来源标注]  [DD-001:MD-M-007 LLMStage]
"""
from dataclasses import dataclass

import httpx

from aitutor.shared.types import Chunk
from aitutor.pipeline.stages.preprocess import BaseStage


@dataclass
class LLMStage(BaseStage):
    """[类名] LLMStage

    [职责]  阶段4 LLM 调用
    [关联设计规范]  MD-M-007 类设计 LLMStage 行

    [属性]
      属性1: provider_url str - LLM Provider URL
      属性2: model_name str - 模型名
      属性3: timeout_ms int - 超时（默认 4000）
      属性4: stream bool - 是否流式

    [方法列表]
      方法1: run(context) -> str - 主入口
      方法2: _build_prompt(context) -> str - 构造 prompt
      方法3: _call_provider(prompt) -> str - HTTP 调用

    [异常处理]
      异常1: E00702 LLM 不可用 - 触发兜底
      异常2: E00704 LLM 超时 - 触发兜底

    [来源标注]  [DD-001:MD-M-007 LLMStage]
    """
    provider_url: str = "http://localhost:1234/v1/chat/completions"
    model_name: str = "default"
    timeout_ms: int = 4000
    stream: bool = False

    async def run(self, context: list[Chunk]) -> str:
        """[函数名] run

        [职责]  执行 LLM 调用
        [关联接口契约]  IC-002（学习回合）

        [参数说明]
          参数1: context list[Chunk] 必填 重排后上下文

        [返回值]
          类型:  str
          描述:  LLM 原始答案
          特殊值:  空字符串表示失败

        [错误码]
          错误码1: E00702 LLM 不可用
          错误码2: E00704 LLM 超时

        [前置条件]  LLM Provider 可达、context 非空
        [后置条件]  原始答案进入 postprocess 阶段
        [并发安全]  是（httpx 连接池）
        [幂等性]  是 / 幂等键: prompt_hash
        [性能约束]  ≤4s
        [来源标注]  [DD-001:MD-M-007 函数签名 call_llm 行] + [DD-001:IC-002]
        """
        # [DD-001:MD-M-007 函数签名 call_llm] 阶段 4 入口
        # [DD-001:IC-002 E00704] 超时兜底
        # [DD-001:IC-002 E00702] 不可用兜底
        # [DD-M推断:依据=TS-006 httpx] 异步 HTTP
        pass

    async def _build_prompt(self, context: list[Chunk]) -> str:
        """[函数名] _build_prompt

        [职责]  构造 prompt（含上下文 + 系统指令）
        [关联接口契约]  无

        [参数说明]
          参数1: context list[Chunk] 必填

        [返回值]
          类型:  str
          描述:  完整 prompt（含 system + user + 引用源）

        [错误码]
          错误码1: 无

        [前置条件]  context 非空
        [后置条件]  无副作用
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤20ms
        [来源标注]  [DD-M推断:依据=M-007 阶段 4]
        """
        # [DD-M推断:依据=IC-002 sources] 引用源注入 prompt
        pass

    async def _call_provider(self, prompt: str) -> str:
        """[函数名] _call_provider

        [职责]  HTTP 调用 LLM Provider
        [关联接口契约]  无

        [参数说明]
          参数1: prompt str 必填

        [返回值]
          类型:  str
          描述:  LLM 响应内容

        [错误码]
          错误码1: httpx.HTTPError - Provider 不可达

        [前置条件]  provider_url 可达
        [后置条件]  无副作用
        [并发安全]  是
        [幂等性]  是
        [性能约束]  ≤4s
        [来源标注]  [DD-001:MD-M-007 异常处理 E00702]
        """
        # [DD-001:MD-M-007 异常处理 E00702] 不可用兜底
        # [DD-M推断:依据=TS-006 httpx] async client
        pass
