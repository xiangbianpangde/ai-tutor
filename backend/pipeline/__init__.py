"""backend.pipeline —— 数据管线（M-014）：采集→清洗→结构化建图 + 噪声红线。

架构契约：本层不反向依赖 backend.routers/app/main（由它们装配调用）。
"""
from __future__ import annotations

from .data_pipeline import DataPipeline, StageRunner
from .noise_gate import NoiseGate

__all__ = ["DataPipeline", "NoiseGate", "StageRunner"]
