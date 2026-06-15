"""backend.build —— 打包调度（M-015，对应 v2 #11 打包发布）。

Nuitka onedir（非 onefile，R-01）编译 → UPX 软压缩 → 产物校验 FSM。命令执行器可注入。
"""
from __future__ import annotations

from .nuitka import BuildConfig, NuitkaBuilder
from .orchestrator import BuildOrchestrator
from .upx import UPXCompressor
from .verifier import ArtifactVerifier

__all__ = [
    "BuildOrchestrator",
    "BuildConfig",
    "NuitkaBuilder",
    "UPXCompressor",
    "ArtifactVerifier",
]
