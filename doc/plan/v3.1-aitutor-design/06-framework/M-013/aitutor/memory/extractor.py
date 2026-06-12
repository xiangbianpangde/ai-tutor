"""memory.extractor - LLM 事实提取器

[文件路径] src/aitutor/memory/extractor.py
[文件职责] 调用 LLM Provider（httpx）从对话中提取事实
[所属模块] M-013（长期记忆）
[关联设计规范] MD-013 sm013-extract
[功能描述]
  功能1: 构造事实抽取 prompt
  功能2: httpx 异步调用 LLM Provider
  功能3: 解析 LLM 响应为 FactExtractionResult
  功能4: 重试 1 次 / 失败丢弃（E01301）
[输入输出]
  输入: FactExtractionRequest（conversation / user_id / max_facts）
  输出: FactExtractionResult（facts / confidence / trace_id）
[依赖关系]
  依赖文件: aitutor.memory.models / aitutor.shared.exceptions
  被依赖文件: aitutor.memory.service
[注意事项]
  注意1: httpx 超时 30s（与 M-014 翻译一致）
  注意2: 失败重试 1 次（IC-007 E01301），仍失败丢弃 + WARN 日志
  注意3: prompt 模板与 Pydantic 解析强绑定，避免 hallucination
  注意4: 不允许 eval / exec（CS-NNN §8 安全规范）
[代码风格] 遵循 CS-NNN
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-013 - 初版注释框架
[作者] DD-M-013-20260602
[来源标注] [DD-001:MD-013 sm013-extract] + [DD-001:IC-007 E01301]
"""
from __future__ import annotations

# 1. 标准库
import json
from typing import Any

# 2. 第三方库
import httpx
from pydantic import ValidationError

# 3. 本地模块
from aitutor.memory.models import FactExtractionRequest, FactExtractionResult
from aitutor.shared.exceptions import LLMUnavailableError
from aitutor.shared.types import TraceIdType


# [类名] FactExtractor
# [职责] LLM 事实提取（httpx 异步）
# [关联设计规范] MD-013 FactExtractor
# [属性]
#   属性1: client httpx.AsyncClient HTTP 客户端
#   属性2: llm_endpoint str LLM Provider URL
#   属性3: prompt_template str 抽取 prompt 模板
#   属性4: timeout_seconds float 单次超时（默认 30s）
#   属性5: max_retries int 重试次数（默认 1）
# [方法列表]
#   方法1: extract(request: FactExtractionRequest) → FactExtractionResult - 入口
#   方法2: _build_prompt(request: FactExtractionRequest) → str - 构造 prompt
#   方法3: _call_llm(prompt: str) → dict - 调 LLM
#   方法4: _parse_response(raw: dict) → FactExtractionResult - 解析
# [状态机] N/A
# [异常处理]
#   异常1: LLMUnavailableError - LLM 不可用（E01301 重试 1 次后仍失败）
#   异常2: ValidationError - 响应解析失败
# [来源标注] [DD-001:MD-013] + [DD-001:IC-007 E01301]
class FactExtractor:
    """LLM 事实提取器（httpx 异步 + 重试 + 解析）。"""

    # 默认 prompt 模板（事实抽取）
    # [DD-M推断:依据=MD-013 FactExtractor.prompt + 角色任务描述最佳实践]
    DEFAULT_PROMPT_TEMPLATE: str = (
        "你是一名教学助理。请从以下对话中抽取不超过 {max_facts} 条"
        "可长期复用的客观事实。每条事实独立成行，格式为：- <事实>。"
        "仅返回事实列表，不要其他解释。\n\n"
        "对话：\n{conversation}\n\n"
        "事实列表："
    )

    def __init__(
        self,
        client: httpx.AsyncClient,
        llm_endpoint: str,
        *,
        prompt_template: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
    ) -> None:
        # [DD-M推断:依据=MD-013 FactExtractor 属性 + httpx 异步客户端注入]
        ...

    async def extract(
        self,
        request: FactExtractionRequest,
    ) -> FactExtractionResult:
        """从对话中提取事实。

        Args:
            request: 抽取请求（含 conversation / user_id / max_facts）。

        Returns:
            FactExtractionResult: 抽取结果。

        Raises:
            LLMUnavailableError: LLM 调用失败（E01301）。
            ValidationError: 响应解析失败。
        """
        ...

    def _build_prompt(self, request: FactExtractionRequest) -> str:
        """构造 LLM prompt（按模板填充）。"""
        ...

    async def _call_llm(self, prompt: str) -> dict[str, Any]:
        """调用 LLM Provider（httpx POST）。

        Raises:
            LLMUnavailableError: 调 LLM 失败 / 重试仍败。
        """
        ...

    def _parse_response(self, raw: dict[str, Any]) -> FactExtractionResult:
        """解析 LLM 响应为 FactExtractionResult。

        Raises:
            ValidationError: 响应格式非法。
        """
        ...
