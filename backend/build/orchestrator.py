"""backend.build.orchestrator —— 打包调度 FSM（M-015，对应 v2 #11 打包发布）。

四步状态机：NUITKA 编译 → UPX 软压缩 → VERIFY 校验 → DONE。Nuitka 失败=硬停；
UPX/体积超标=软降级（WARN 续走，FDR-M015-002）。命令执行器可注入（CI/测试不真编译）。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from .nuitka import BuildConfig
from .upx import UPXCompressor
from .verifier import ArtifactVerifier

CommandRunner = Callable[[Sequence[str]], "tuple[int, str]"]

STATE_NUITKA = "NUITKA"
STATE_UPX = "UPX"
STATE_VERIFY = "VERIFY"
STATE_DONE = "DONE"
STATE_FAILED = "FAILED"


class BuildOrchestrator:
    """编排 Nuitka onedir 打包全流程，聚合每步结果 + 最终是否成功。"""

    def __init__(
        self, config: BuildConfig | None = None, *, runner: CommandRunner | None = None
    ) -> None:
        self.config = config or BuildConfig()
        self._runner = runner

    def run(self, *, dist_dir: str | None = None) -> dict:
        """跑全流程。dist_dir 省略时取 config 里 nuitka 的 onedir 目录。"""
        runner = self._runner or self._default_runner

        steps: list[dict] = []
        warnings: list[str] = []

        # 1) Nuitka 编译（硬）
        nuitka_res = self.config.nuitka.build(runner)
        steps.append({"state": STATE_NUITKA, **nuitka_res})
        if not nuitka_res["ok"]:
            return self._final(STATE_FAILED, steps, warnings,
                               error="Nuitka 编译失败（硬停）")

        out_dir = dist_dir or f"{self.config.nuitka.output_dir}/main.dist"

        # 2) UPX 压缩（软）
        if self.config.enable_upx:
            upx_res = UPXCompressor(runner=runner).compress_dir(out_dir)
            steps.append({"state": STATE_UPX, **upx_res})
            warnings.extend(upx_res.get("warnings", []))

        # 3) 校验（exe 硬 / 体积软）
        verify_res = ArtifactVerifier(max_size_mb=self.config.max_size_mb).verify(
            out_dir, exe_name=self.config.nuitka.output_name
        )
        steps.append({"state": STATE_VERIFY, **verify_res})
        warnings.extend(verify_res.get("warnings", []))
        if not verify_res["ok"]:
            return self._final(STATE_FAILED, steps, warnings,
                               error="产物校验硬失败：" + "；".join(verify_res["errors"]))

        return self._final(STATE_DONE, steps, warnings)

    @staticmethod
    def _final(state: str, steps: list[dict], warnings: list[str], error: str | None = None) -> dict:
        return {
            "ok": state == STATE_DONE,
            "state": state,
            "steps": steps,
            "warnings": warnings,
            "error": error,
        }

    @staticmethod
    def _default_runner(command: Sequence[str]) -> tuple[int, str]:
        import shutil
        import subprocess

        if shutil.which(command[0]) is None:
            return 127, f"工具不存在: {command[0]}"
        proc = subprocess.run(  # noqa: S603 受控命令
            list(command), capture_output=True, text=True, timeout=1800
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
