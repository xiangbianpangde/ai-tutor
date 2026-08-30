"""backend.routers.settings —— 运行时 LLM 配置（前缀 /api/settings）。

让前端设置页把 OpenAI 兼容端点（base_url / api_key / model）热接入教学
管线，无需重启：

- ``GET  /llm``   当前生效 provider 的脱敏描述（key 打码，永不含完整 key）。
- ``POST /llm``   应用配置：校验后实例化 OpenAICompatProvider 并热替换；
                  key 只存进程内存（app.state），不落盘、不入日志。
- ``POST /llm/test`` 用给定配置探测连通性（1-token ping），不替换当前。
- ``POST /llm/reset`` 清除运行时覆盖，回到 env 选择链
                  （DeepSeek env > MiniMax env > 本地判分器）。

base_url 由用户显式配置；scheme 限定 http/https。本地 Ollama/vLLM 的
``http://localhost`` 是合法场景（用户自配端点的有意豁免，非服务端 SSRF 面
——请求目标是用户为自己机器明确选择的推理端点）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request

from ..responses import ok
from ..teaching.openai_compat_provider import OpenAICompatProvider
from shared.errors import TutorError

router = APIRouter(tags=["settings"])


def _effective_llm(request: Request) -> tuple[Any, str]:
    """返回 (当前 llm 或 None, 来源描述)。"""
    runtime = getattr(request.app.state, "tutor_llm_runtime", None)
    if runtime is not None:
        return runtime, "runtime"
    injected = getattr(request.app.state, "tutor_llm", None)
    if injected is not None:
        return injected, "injected"
    return None, "fallback"


def _describe(llm: Any, source: str) -> dict[str, Any]:
    if llm is None:
        return {"provider": "local_judge", "source": source,
                "detail": "未配置真 LLM，当前为本地判分器（基础模式）"}
    describe = getattr(llm, "describe", None)
    if callable(describe):
        return {**describe(), "source": source}
    name = getattr(llm, "name", type(llm).__name__)
    model = getattr(llm, "model", "")
    return {"provider": name, "model": model, "source": source,
            "api_key_masked": "***"}


@router.get("/llm", summary="当前 LLM 配置（脱敏）")
async def get_llm(request: Request) -> dict:
    llm, source = _effective_llm(request)
    return ok(_describe(llm, source))


def _apply(request: Request, provider: OpenAICompatProvider) -> dict[str, Any]:
    """实例化后热替换：app.state + orchestrator（若已缓存）的 engine 缓存失效。"""
    request.app.state.tutor_llm_runtime = provider
    teaching = getattr(request.app.state, "teaching", None)
    if teaching is not None and hasattr(teaching, "set_llm"):
        teaching.set_llm(provider)
    return {**provider.describe(), "source": "runtime"}


@router.post("/llm", summary="应用 OpenAI 兼容 LLM 配置（热替换，key 仅存内存）")
async def apply_llm(
    request: Request,
    base_url: str = Body(..., embed=True),
    api_key: str = Body(..., embed=True),
    model: str = Body(..., embed=True),
) -> dict:
    provider = OpenAICompatProvider(
        api_key=api_key, base_url=base_url, model=model,
    )
    return ok(_apply(request, provider))


@router.post("/llm/test", summary="探测给定的 LLM 配置（不替换当前）")
async def test_llm(
    request: Request,
    base_url: str = Body(..., embed=True),
    api_key: str = Body(..., embed=True),
    model: str = Body(..., embed=True),
) -> dict:
    try:
        provider = OpenAICompatProvider(
            api_key=api_key, base_url=base_url, model=model, timeout=30.0,
        )
        return ok(provider.ping())
    except TutorError:
        raise
    except Exception as exc:  # 探测失败也返回结构化结果，不打断设置页
        return ok({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:160]}"})


@router.post("/llm/reset", summary="清除运行时覆盖（回到 env 选择链）")
async def reset_llm(request: Request) -> dict:
    request.app.state.tutor_llm_runtime = None
    teaching = getattr(request.app.state, "teaching", None)
    if teaching is not None and hasattr(teaching, "set_llm"):
        teaching.set_llm(None)
    llm, source = _effective_llm(request)
    return ok(_describe(llm, source))
