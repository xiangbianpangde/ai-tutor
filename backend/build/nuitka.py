"""backend.build.nuitka —— Nuitka onedir 后端编译（M-015）。

走向决议 R-01 证伪 PyInstaller onefile（自解压冷启慢 + 杀软误报），改 **Nuitka
--standalone（onedir）**。NuitkaBuilder 只负责"拼正确的命令 + 调执行器"，执行器可注入
（CI/测试不必真编译，真编译 5-15min）。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

CommandRunner = Callable[[Sequence[str]], "tuple[int, str]"]


@dataclass
class NuitkaBuilder:
    """构造并（可选）执行 Nuitka onedir 编译命令。"""

    entry: str = "backend/main.py"
    output_dir: str = "dist"
    output_name: str = "ai-tutor-backend"
    data_dirs: tuple[tuple[str, str], ...] = (("data", "data"),)
    exclude_imports: tuple[str, ...] = ("pytest", "ruff")
    python_exe: str = "python"

    def build_args(self) -> list[str]:
        """生成 Nuitka 命令参数。**onedir（--standalone），绝不 --onefile**。"""
        args = [
            self.python_exe, "-m", "nuitka",
            "--standalone",  # onedir，不是 onefile（R-01）
            f"--output-dir={self.output_dir}",
            f"--output-filename={self.output_name}",
            "--assume-yes-for-downloads",
        ]
        for src, dst in self.data_dirs:
            args.append(f"--include-data-dir={src}={dst}")
        for mod in self.exclude_imports:
            args.append(f"--nofollow-import-to={mod}")
        args.append(self.entry)
        return args

    def build(self, runner: CommandRunner) -> dict:
        """执行编译。返回 {ok, exit_code, command, summary}。"""
        cmd = self.build_args()
        code, output = runner(cmd)
        lines = [ln for ln in (output or "").splitlines() if ln.strip()]
        return {
            "ok": code == 0,
            "exit_code": code,
            "command": cmd,
            "summary": (lines[-1] if lines else "(无输出)")[:300],
        }


@dataclass
class BuildConfig:
    """打包配置聚合，供 orchestrator 透传。"""

    nuitka: NuitkaBuilder = field(default_factory=NuitkaBuilder)
    enable_upx: bool = True
    max_size_mb: int = 200  # 软门禁（超标仅 WARN）
