"""backend.build.verifier —— 产物校验（M-015）。

校验 onedir 产物：可执行存在（硬）+ 目录非空（硬）+ 总体积在软门禁内（超标仅 WARN）。
"""
from __future__ import annotations

from pathlib import Path


class ArtifactVerifier:
    """校验 Nuitka onedir 产物完整性 + 体积软门禁。"""

    def __init__(self, *, max_size_mb: int = 200) -> None:
        self.max_size_mb = max_size_mb

    def verify(self, dist_dir: str | Path, *, exe_name: str = "ai-tutor-backend") -> dict:
        """返回 {ok, errors, warnings, size_mb, exe_found}。errors 非空 = 硬失败。"""
        dist = Path(dist_dir)
        errors: list[str] = []
        warnings: list[str] = []

        if not dist.exists() or not dist.is_dir():
            return {"ok": False, "errors": [f"产物目录不存在: {dist}"],
                    "warnings": [], "size_mb": 0.0, "exe_found": False}

        # 可执行存在（onedir 里通常是 exe_name 或 exe_name.exe / .bin）
        candidates = [dist / exe_name, dist / f"{exe_name}.exe", dist / f"{exe_name}.bin"]
        exe_found = any(c.exists() for c in candidates)
        if not exe_found:
            errors.append(f"未找到可执行 {exe_name}(.exe/.bin) 于 {dist}")

        files = [f for f in dist.rglob("*") if f.is_file()]
        if not files:
            errors.append("产物目录为空")

        size_bytes = sum(f.stat().st_size for f in files)
        size_mb = round(size_bytes / 1_048_576, 2)
        if size_mb > self.max_size_mb:
            warnings.append(
                f"体积 {size_mb}MB 超软门禁 {self.max_size_mb}MB（软约束，不阻塞）"
            )

        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "size_mb": size_mb,
            "exe_found": exe_found,
        }
