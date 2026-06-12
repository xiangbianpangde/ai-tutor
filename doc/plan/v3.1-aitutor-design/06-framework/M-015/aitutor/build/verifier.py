"""aitutor.build.verifier - 产物校验器（sha256 + 体积门禁）。

> 对应模块: M-015 打包调度（子模块 sm015-verify）
> 关联接口: IC-005 打包构建（VERIFYING 阶段）
> 关联选型: hashlib（标准库）
> 来源标注: [DD-001:MD-M015] + [DD-001:IC-005]

[文件路径] src/aitutor/build/verifier.py
[文件职责] 校验产物 sha256 一致性，检查体积门禁（CLI≤50MB / GUI≤200MB）
[所属模块] M-015 打包调度
[关联设计规范] FS-M015 / MD-M015 子模块 sm015-verify
[功能描述]
  功能1: 递归计算 onedir 目录或单文件 sha256（hashlib）
  功能2: 与 expected_sha256 比对（若提供），不一致触发 E01503
  功能3: 体积门禁检查：CLI>50MB 或 GUI>200MB → 标 WARN_SIZE（不阻塞）
  功能4: 生成 VerifyResult 报告（含 size_bytes / sha256 / passed / warnings）
[输入输出]
  输入: artifact_path: str, expected_sha256: Optional[str], format: Literal["cli","gui"]
  输出: VerifyResult(passed, size_bytes, sha256, warnings)
[依赖关系]
  依赖文件: 无（独立子模块）
  依赖跨模块: aitutor/shared/exceptions.py (BuildError)
  被依赖文件: aitutor/build/orchestrator.py
[注意事项]
  注意1: sha256 计算用 chunk 流式读取（64KB），避免大文件 OOM
  注意2: 体积门禁来源 IC-005 E01501 / EX-020：CLI>50MB / GUI>200MB
  注意3: warn_size 是软约束，不抛异常仅写 WARN 日志（ADR-009）
  注意4: sha256 不匹配触发 E01503 → orchestrator 自动重建 1 次
[代码风格] 遵循 CS-001（Python PEP8 / Ruff / Google Docstring）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-015 - 初始版本，定义 ArtifactVerifier + verify_artifact + VerifyResult
[作者] DD-M-015-20260602
[来源标注] [DD-001:MD-M015 line 439] + [DD-001:IC-005 错误码 E01501/E01503] + [DD-001:EX-020/EX-021]
"""

# ============================================================
# 导入区（DD-S 阶段填充）
# ============================================================
# from __future__ import annotations
#
# import hashlib
# from dataclasses import dataclass, field
# from pathlib import Path
# from typing import Literal
#
# from aitutor.shared.exceptions import BuildError


# ============================================================
# 校验结果数据类
# ============================================================

# [类名] VerifyResult
# [职责] 封装一次校验的全部结果
# [关联设计规范] IC-005 出参 line 177-182
# [属性]
#   passed:     bool  是否通过（sha256 一致 且 无致命错误）
#   size_bytes: int   产物总字节数
#   sha256:     str   64hex 校验和
#   warnings:   list[str]  警告列表（含 warn_size 等软约束）
# [方法列表]
#   is_warn_size() → bool  是否仅触发体积警告（不阻塞）
# [来源标注] [DD-001:IC-005 出参定义] + [DD-M推断:依据=校验结果聚合]
# @dataclass(frozen=True)
# class VerifyResult:
#     passed: bool
#     size_bytes: int
#     sha256: str
#     warnings: list[str] = field(default_factory=list)
#
#     def is_warn_size(self) -> bool:
#         """是否触发体积软警告（不阻塞）。"""
#         ...


# ============================================================
# 校验器
# ============================================================

# [类名] ArtifactVerifier
# [职责] 计算 sha256、检查体积门禁
# [关联设计规范] MD-M015 类设计第 4 项 ArtifactVerifier
# [属性]
#   expected_size:   int | None  期望体积上限（字节）；None 时按 format 选默认
#   expected_sha256: str | None  期望 sha256；None 时仅计算不比对
#   _chunk_size:     int = 65536  流式读取块大小（64KB）
#   _size_limit_cli: int = 50 * 1024 * 1024   CLI 门禁 50MB（IC-005 E01501）
#   _size_limit_gui: int = 200 * 1024 * 1024  GUI 门禁 200MB（IC-005 E01501）
# [方法列表]
#   __init__(expected_size: int | None = None, expected_sha256: str | None = None) → None
#   verify(artifact_path: Path, format: Literal["cli","gui"] = "cli") → VerifyResult
#   _compute_sha256(path: Path) → str  流式计算（私有）
#   _compute_size(path: Path) → int    递归累计字节数（私有）
#   _check_size_limit(size: int, format: str) → list[str]  体积门禁（私有）
# [状态机] N/A
# [异常处理]
#   E01503 sha256 不匹配: 抛 BuildError("sha256_mismatch")
#   E01501 体积超目标: 仅写入 warnings，不抛异常
# [来源标注] [DD-001:MD-M015 line 439] + [DD-001:IC-005 错误码 E01501/E01503]
# class ArtifactVerifier:
#     def __init__(self, expected_size: int | None = None, expected_sha256: str | None = None) -> None:
#         """初始化校验器。
#
#         Args:
#             expected_size: 期望体积上限（字节），None 时按 format 默认
#             expected_sha256: 期望 sha256，None 时仅计算
#         """
#         ...
#
#     def verify(self, artifact_path: Path, format: Literal["cli", "gui"] = "cli") -> VerifyResult:
#         """校验产物。
#
#         Args:
#             artifact_path: onedir 目录或单文件路径
#             format: "cli" 或 "gui"，决定体积门禁阈值
#
#         Returns:
#             VerifyResult: 含 passed / size / sha256 / warnings
#
#         Raises:
#             BuildError: E01503 sha256 不匹配（致命）
#
#         Note:
#             幂等：相同 artifact 多次调用结果一致
#             性能：1GB 产物 sha256 计算约 10s
#         """
#         ...
#
#     def _compute_sha256(self, path: Path) -> str:
#         """流式计算 sha256（64KB chunk）。"""
#         ...
#
#     def _compute_size(self, path: Path) -> int:
#         """递归累计目录/文件字节数。"""
#         ...
#
#     def _check_size_limit(self, size: int, format: Literal["cli", "gui"]) -> list[str]:
#         """体积门禁检查。
#
#         Returns:
#             list[str]: 警告列表（空表示通过，非空仅 WARN 不阻塞）
#         """
#         ...


# ============================================================
# 公开函数
# ============================================================

# [函数名] verify_artifact
# [职责] 模块级公开入口：默认参数校验产物
# [关联接口契约] IC-005（VERIFYING 阶段）
# [参数说明]
#   artifact_path:   str  必填  产物路径
#   format:          str  可选  默认 "cli"
#   expected_sha256: str  可选  默认 None（仅计算不比对）
# [返回值]
#   类型: VerifyResult
#   描述: passed / size_bytes / sha256 / warnings
#   特殊值: passed=False 且 warnings 非空表示软警告（如 warn_size）
# [错误码]
#   E01503 sha256 不匹配 - 抛 BuildError
#   E01501 体积超目标 - WARN only
# [前置条件] artifact_path 存在
# [后置条件] 无副作用（纯查询）
# [并发安全] 是（无共享状态）
# [幂等性] 是（相同输入 → 相同输出）
# [性能约束] 1GB 产物 ≤15s
# [示例]
#   ```
#   result = verify_artifact("dist/aitutor.dist/", format="cli", expected_sha256="abc123...")
#   if not result.passed and not result.is_warn_size():
#       raise RuntimeError("verify failed")
#   ```
# [来源标注] [DD-001:MD-M015 函数签名 line 443] + [DD-001:IC-005 VERIFYING]
# def verify_artifact(
#     artifact_path: str,
#     format: Literal["cli", "gui"] = "cli",
#     expected_sha256: str | None = None,
# ) -> VerifyResult:
#     """校验产物 sha256 + 体积门禁。"""
#     ...
