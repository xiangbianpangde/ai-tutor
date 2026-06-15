"""backend.build.upx —— UPX 软压缩（M-015，FDR-M015-002 软降级）。

体积是**软约束**（ADR-009）：UPX 不可用、压缩失败、超目标体积——**一律只 WARN，不抛**。
执行器可注入。
"""
from __future__ import annotations

import shutil
from collections.abc import Callable, Sequence
from pathlib import Path

CommandRunner = Callable[[Sequence[str]], "tuple[int, str]"]


class UPXCompressor:
    """对 onedir 产物里的大二进制软压缩。永不阻塞构建。"""

    def __init__(self, *, runner: CommandRunner | None = None, min_bytes: int = 1_000_000) -> None:
        self._runner = runner
        self._min_bytes = min_bytes  # 太小的文件不值得压

    def compress_dir(self, target_dir: str | Path) -> dict:
        """压目录内 .so/.pyd/.dll/可执行；返回 {compressed, skipped, warnings}。"""
        target = Path(target_dir)
        warnings: list[str] = []
        if shutil.which("upx") is None and self._runner is None:
            return {"compressed": 0, "skipped": 0,
                    "warnings": ["UPX 不存在——跳过压缩（软约束，不阻塞）"]}
        if not target.exists():
            return {"compressed": 0, "skipped": 0, "warnings": [f"目录不存在: {target}"]}

        runner = self._runner or self._default_runner
        compressed = skipped = 0
        for f in target.rglob("*"):
            if not f.is_file() or f.suffix.lower() not in (".so", ".pyd", ".dll", ".exe", ".bin"):
                continue
            if f.stat().st_size < self._min_bytes:
                skipped += 1
                continue
            code, output = runner(["upx", "--best", str(f)])
            if code == 0:
                compressed += 1
            else:
                skipped += 1
                warnings.append(f"压缩失败（软降级）: {f.name}")
        return {"compressed": compressed, "skipped": skipped, "warnings": warnings}

    @staticmethod
    def _default_runner(command: Sequence[str]) -> tuple[int, str]:
        import subprocess

        proc = subprocess.run(  # noqa: S603 受控命令
            list(command), capture_output=True, text=True, timeout=300
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
