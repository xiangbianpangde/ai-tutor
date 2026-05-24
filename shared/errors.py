"""统一错误模型 + 错误码表 + TutorError 异常类。

合同来源: ai-tutor-system-design/specs/shared-schemas.md §八
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


ERROR_CODES: dict[str, str] = {
    "PLUGIN_NOT_AVAILABLE": "插件不可用，请检查配置",
    "DEPENDENCY_MISSING": "缺少依赖",
    "CORPUS_NOT_FOUND": "语料库不存在",
    "KG_NOT_BUILT": "请先构建知识图谱",
    "KG_NOT_FOUND": "知识图谱不存在",
    "SUBJECT_NOT_FOUND": "科目不存在",
    "SESSION_EXPIRED": "会话已过期",
    "SESSION_NOT_FOUND": "会话不存在",
    "COGNITIVE_OVERLOAD": "检测到认知过载，建议休息",
    "RATE_LIMITED": "请求频率过高",
    "AUTH_REQUIRED": "需要认证",
    "GPU_NOT_AVAILABLE": "未检测到 GPU，将以 CPU 模式运行",
    "LLM_BUDGET_EXCEEDED": "本次任务的 LLM 预算已用尽",
    "INVALID_CONCEPT_ID": "Concept.id 格式不合法",
    "KG_QUALITY_GATE_FAILED": "知识图谱质量门未通过",
    "INVALID_KG_EDIT_ACTION": "review_kg 编辑动作不合法",
}


class TutorErrorDetail(BaseModel):
    """对外暴露的错误详情（同 spec §八）。"""

    code: str
    message: str
    hint: str | None = None
    retryable: bool = False
    details: dict[str, Any] | None = None


class TutorError(Exception):
    """所有业务层错误的基类。从 MCP tool 抛出会被包装成 TutorErrorDetail 返回。"""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        hint: str | None = None,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message or ERROR_CODES.get(code, code)
        self.hint = hint
        self.retryable = retryable
        self.details = details
        super().__init__(f"[{code}] {self.message}")

    def to_detail(self) -> TutorErrorDetail:
        return TutorErrorDetail(
            code=self.code,
            message=self.message,
            hint=self.hint,
            retryable=self.retryable,
            details=self.details,
        )
