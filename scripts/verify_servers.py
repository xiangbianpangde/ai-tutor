"""验证 4 个 MCP server 在 stdio 模式能正常启动并响应 list_tools。

模拟 Claude Desktop 接入时的协议握手：
1. 启 server 子进程（stdio transport）
2. 发 initialize 请求
3. 发 initialized notification
4. 发 tools/list 请求
5. 关闭

任一步失败 → 报告错误（exit 1）。
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent

SERVERS = [
    ("knowledge-mcp", "servers.knowledge_mcp.server"),
    ("tutoring-mcp", "servers.tutoring_mcp.server"),
    ("digest-mcp", "servers.digest_mcp.server"),
    ("sync-mcp", "servers.sync_mcp.server"),
]


def _send(proc: subprocess.Popen, payload: dict) -> None:
    line = json.dumps(payload) + "\n"
    proc.stdin.write(line.encode("utf-8"))
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen, timeout: float = 8.0) -> dict | None:
    """读一行 JSON 响应。"""
    import select
    if os.name == "nt":
        # Windows 没 select for pipes —— 用 readline 阻塞，但加超时通过 thread
        import threading
        result: list[bytes] = [b""]
        def _do():
            result[0] = proc.stdout.readline()
        t = threading.Thread(target=_do, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            return None
        line = result[0]
    else:
        rlist, _, _ = select.select([proc.stdout], [], [], timeout)
        if not rlist:
            return None
        line = proc.stdout.readline()

    if not line:
        return None
    try:
        return json.loads(line.decode("utf-8").strip())
    except json.JSONDecodeError:
        return None


def verify_server(name: str, module: str) -> tuple[bool, str]:
    """返回 (success, message_with_tool_names_or_error)。"""
    cmd = ["uv", "run", "--directory", str(ROOT), "python", "-m", module]
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{(ROOT / 'data' / 'tutor.db').as_posix()}"
    env["AI_TUTOR_DATA_ROOT"] = str(ROOT / "data")
    env["PYTHONIOENCODING"] = "utf-8"
    env["LOG_LEVEL"] = "WARNING"

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        # MCP initialize
        _send(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "verify-script", "version": "0.1"},
            },
        })
        init_resp = _read_response(proc, timeout=15.0)
        if init_resp is None or "result" not in init_resp:
            return False, f"initialize 无响应/错误: {init_resp}"

        # initialized notification
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        # list tools
        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools_resp = _read_response(proc, timeout=10.0)
        if tools_resp is None or "result" not in tools_resp:
            return False, f"tools/list 无响应/错误: {tools_resp}"
        tools = tools_resp["result"].get("tools", [])
        names = sorted(t.get("name", "?") for t in tools)
        return True, f"{len(names)} tools: {', '.join(names)}"
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    print(f"{'─' * 60}\n验证 4 个 MCP server stdio 启动\n{'─' * 60}")
    print(f"项目根: {ROOT}\n")
    all_ok = True
    for name, module in SERVERS:
        print(f"  → {name} ({module})")
        ok, msg = verify_server(name, module)
        status = "[OK]" if ok else "[FAIL]"
        print(f"    {status}  {msg}\n")
        if not ok:
            all_ok = False

    if all_ok:
        print(f"{'─' * 60}\n✓ 全部 4 个 server 可正常启动并响应 tools/list\n{'─' * 60}")
        sys.exit(0)
    else:
        print(f"{'─' * 60}\n✗ 至少一个 server 启动失败，见上方日志\n{'─' * 60}")
        sys.exit(1)


if __name__ == "__main__":
    main()
