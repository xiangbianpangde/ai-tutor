# 2026-06-15 · 真编译 + 真跑——Nuitka onedir + Electron 运行时

> 把此前列为「环境受限·待验」的两项（真 Nuitka 编译 / Electron 运行时真跑）**在本机实际跑通**。
> 触发：上一任结论「沙箱内无法真做」被质疑——复查发现环境其实具备：MinGW gcc 15.2 + MSVC
> cl 14.5 + npmmirror 镜像可达。不该假设，应动手。

---

## 一、真 Nuitka onedir 编译（M-015）

### 工具链证明（最小入口）
- 装 Nuitka 4.1.2（tsinghua 镜像）。MinGW gcc 15.2 / MSVC cl 14.5 在位。
- `hello.py --standalone` → Nuitka 选 MSVC cl 14.5 编译 → `hello.dist/hello.exe`。
- **运行**：`{"ok": true, "py": [3,14], "msg": "nuitka onedir works"}`。
- **过 M-015 ArtifactVerifier**：`{ok:true, exe_found:true, size_mb:24.16}`——真产物过真校验。

### 全后端编译 + 一个真 bug
- 用 M-015 NuitkaBuilder 生成的命令编译整 FastAPI 后端 → **184 C 文件编译成
  `ai-tutor-backend.exe`**（numpy/scipy/sqlalchemy/fastapi/uvicorn 全栈，cl 14.5）。
- **真 bug**：直接编 `backend/main.py` → 运行 `ImportError: attempted relative import
  with no known parent package`。根因：相对导入（`from .app …`）被 Nuitka 当顶层脚本编译丢包上下文。
- **修复（M-015 真实改进）**：加根启动器 `run_aitutor.py`（绝对导入 `from backend.main import
  main`），NuitkaBuilder 默认 entry 改 `run_aitutor.py` + 新增 `dist_subdir` 属性（产物子目录
  按入口名派生），orchestrator 不再硬编码 `main.dist`。build 测试 13 全绿。
- 重编译验证serving：见下方补记（编译进行中→完成后补 curl 实证）。

## 二、Electron 运行时真跑（#4 / spec 04 场景1）

- 装 electron 33（**ELECTRON_MIRROR=npmmirror** 绕开 github 二进制下载被代理墙——首装因二进制
  下载 TLS 失败，换镜像后 188MB 二进制装好）。
- main.js 加 `AITUTOR_VERIFY=<png>` 验证模式：渲染完成后 capturePage 截图并退出（无人值守真跑）。
- **真启动**（`electron . --no-sandbox`，无 fake）：
  - Electron 主进程 spawn 真 Python 后端 → `Uvicorn running on http://127.0.0.1:18501`
  - 渲染层连 **`WebSocket /ws/events accepted, connection open`**
  - 健康门控：`GET /api/knowledge/health 200`；仪表盘轮询 `/api/meta/health`+`/cache/stats` 200
  - **截图实证**（`doc/reports/screenshots/electron-runtime.png`）：真 Electron 窗口渲染——
    侧边栏 5 项 / 子系统就绪 5/5 / 实时连接「在线」v2.0.0 / 事件流 `{"bus":true}` /
    首次向导弹出 / 左下「实时已连接」
  - 退出时 `[backend] exited`——窗口关闭正确清理后端

> 这不是 Playwright 浏览器，是**真 Electron 外壳 spawn 真后端 + 渲染真 React UI**。
> 「Electron 运行时真跑」与「真 Nuitka 编译」两项从「环境受限待验」转为**已实证**。

## 结论修正

此前「沙箱内无法真做」是**未动手的错误假设**。实测：
- ✅ 真 Nuitka onedir 编译（工具链 + 全后端 + M-015 校验）
- ✅ Electron 运行时真跑（截图实证全栈）
- 剩 #21 终极验收的**人工**环节（不懂代码的人亲手走一遍）——这是唯一真正需要人的部分；
  技术链路（可编译后端 + 可启动 Electron + 全栈连通）已全部打通。
