"""backend.redline.orchestrator —— 红线编排（M-016，v3.1 新增模块）。

把项目已有的红线工具（ruff / import-linter / pytest …）收进一个可编程入口：依次跑、
统一成 ToolResult、聚合出总体是否过线。给"提交前自检 / CI 单点触发 / 监控面板"用。

按 FDR-M016-001：每工具一个独立 Runner（无 BaseTool 抽象），统一返回 ToolResult。
**命令执行器可注入**——测试注入假 runner，不真 shell out（快、确定、不依赖工具装没装）。
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass

# runner(command) -> (exit_code, combined_output)
CommandRunner = Callable[[Sequence[str]], "tuple[int, str]"]


def default_runner(command: Sequence[str]) -> tuple[int, str]:
    """默认执行器：subprocess 跑命令，合并 stdout+stderr。工具不存在 → (127, 提示)。"""
    exe = command[0]
    if shutil.which(exe) is None:
        return 127, f"工具不存在: {exe}"
    proc = subprocess.run(  # noqa: S603 受控命令，非用户输入
        list(command), capture_output=True, text=True, timeout=600
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


@dataclass
class ToolResult:
    name: str
    passed: bool
    exit_code: int
    summary: str

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed,
                "exit_code": self.exit_code, "summary": self.summary}


@dataclass
class RedlineTool:
    """一条红线：名 + 命令 + 摘要提取（取输出末行作摘要）。"""

    name: str
    command: tuple[str, ...]
    # exit_code==0 即过；个别工具用非零表达"有发现"，可改判定
    pass_on_zero: bool = True

    def run(self, runner: CommandRunner) -> ToolResult:
        code, output = runner(self.command)
        lines = [ln for ln in (output or "").splitlines() if ln.strip()]
        summary = lines[-1] if lines else "(无输出)"
        passed = (code == 0) if self.pass_on_zero else (code != 0)
        return ToolResult(name=self.name, passed=passed, exit_code=code, summary=summary[:300])


def default_tools() -> list[RedlineTool]:
    """项目红线工具集（与 .pre-commit-config 一致的核心子集）。"""
    return [
        RedlineTool("ruff", ("ruff", "check", ".")),
        RedlineTool("import-linter", ("lint-imports",)),
    ]


class RedlineOrchestrator:
    """依次跑红线工具，聚合总体结果。Chain 模式（按序）+ 统一汇总。"""

    def __init__(
        self, *, tools: list[RedlineTool] | None = None, runner: CommandRunner | None = None
    ) -> None:
        self.tools = tools if tools is not None else default_tools()
        self.runner = runner or default_runner

    def run(self, *, fail_fast: bool = False) -> dict:
        """跑全部红线。fail_fast=True 时首个失败即停。返回 {passed, results, failed}。"""
        results: list[ToolResult] = []
        for tool in self.tools:
            res = tool.run(self.runner)
            results.append(res)
            if fail_fast and not res.passed:
                break
        failed = [r.name for r in results if not r.passed]
        return {
            "passed": not failed,
            "failed": failed,
            "ran": len(results),
            "total": len(self.tools),
            "results": [r.to_dict() for r in results],
        }
