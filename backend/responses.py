"""backend.responses —— 统一 JSON 响应信封。

成功: ``{"ok": true, "data": ...}``
失败: ``{"ok": false, "error": {"code": ..., "message": ..., "hint": ...}}``

（开发规范 04-api：统一响应格式 / 设计文档-后端API层 §统一响应格式）
"""
from __future__ import annotations

from typing import Any

from .core import TutorError

# 业务错误码 → HTTP 状态码。未列出的业务错误一律 400（客户端可改正）。
_STATUS_BY_CODE: dict[str, int] = {
    "CORPUS_NOT_FOUND": 404,
    "KG_NOT_FOUND": 404,
    "KG_NOT_BUILT": 409,
    "SUBJECT_NOT_FOUND": 404,
    "SESSION_NOT_FOUND": 404,
    "SESSION_EXPIRED": 410,
    "AUTH_REQUIRED": 401,
    "RATE_LIMITED": 429,
    "LLM_BUDGET_EXCEEDED": 402,
    "COGNITIVE_OVERLOAD": 200,  # 非错误：教学层主动建议休息，正常返回
    "DATABASE_ERROR": 500,
    "INTERNAL_ERROR": 500,
}


def ok(data: Any = None) -> dict[str, Any]:
    """成功信封。"""
    return {"ok": True, "data": data}


def error_payload(err: TutorError) -> dict[str, Any]:
    """失败信封（不含 HTTP 状态码，状态码由 :func:`status_for` 给出）。"""
    return {
        "ok": False,
        "error": {
            "code": err.code,
            "message": err.message,
            "hint": err.hint,
            "retryable": err.retryable,
        },
    }


def status_for(code: str) -> int:
    """业务错误码映射到 HTTP 状态码。"""
    return _STATUS_BY_CODE.get(code, 400)
