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
- **真 bug 2**：换启动器重编后又暴露 `FileNotFoundError: pypinyin/pinyin_dict.json`——
  Nuitka onedir 默认不带 pypinyin 的数据文件（shared/slug.py 用 pypinyin，import 期读 JSON）。
- **修复（M-015 两处真实改进）**：
  ① 加根启动器 `run_aitutor.py`（绝对导入 `from backend.main import main`），NuitkaBuilder
     默认 entry 改它 + `dist_subdir` 属性（产物子目录按入口派生），orchestrator 不再硬编码 main.dist；
  ② NuitkaBuilder 加 `include_package_data=("pypinyin",)` → `--include-package-data=pypinyin`。
  build 测试 16 全绿（+入口须绝对导入启动器 / dist_subdir 派生 / 含 pypinyin 包数据）。
- **重编译 + 运行实证**：launcher 重编 `ai-tutor-backend.exe`（184 C 文件）→ 带上 pypinyin
  数据 → **跑起来真 serving**：
  - `GET /api/meta/health` → `{ok:true, subsystems:{db,cache,sessions,tasks,events 全 true}}`
  - `GET /api/knowledge/health` → `{ok:true, version:2.0.0}`
  - `POST /api/tutoring/review/schedule {rating:3}` → 真 FSRS（stability 3.173 / 下次 2026-06-18）
  - `POST /api/knowledge/rag/validate` → `{is_supported:true, confidence:0.6, method:heuristic}`
  **整个 FastAPI 后端作为原生 exe 真跑且功能正确**（非解释器）。「真 Nuitka 编译」彻底闭环。

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

## 三、NSIS 安装包 + 打包应用真跑（#21 可安装包）

- electron-builder 26（ELECTRON_BUILDER_BINARIES_MIRROR=npmmirror 绕 github 二进制下载）。
- package.json 加 build 配置：extraResources 把**编译后端 onedir**（286MB）塞进
  `resources/backend/`；main.js 加 `app.isPackaged` 分支——打包形态 spawn 内置
  `ai-tutor-backend.exe`（非 .venv python）。
- **产出真安装包**：`frontend/release/AI-Tutor Setup 2.0.0.exe`（**139MB NSIS 安装包**，
  含 Electron 外壳 + Chromium + React 渲染层 + 编译后端 + pypinyin 数据；签名 + blockmap）。
  （尾部 publish-info 报错是自动更新元信息生成需 repo 配置，**不影响安装包本体**；已加
  `publish:null` 消除。）
- **打包应用真跑**（`win-unpacked/AI-Tutor.exe`，`isPackaged=true`，**无 .venv 无开发 Python**）：
  spawn `resources/backend/ai-tutor-backend.exe` 内置编译后端 → 渲染层连接 → 截图实证
  （`doc/reports/screenshots/packaged-app.png`：子系统就绪 5/5 / 实时在线 v2.0.0 /
  实时已连接 / 首次向导）。**完整桌面应用 = 编译后端 + Electron 外壳，自包含运行。**

## 结论修正

此前「沙箱内无法真做」是**未动手的错误假设**。实测：
- ✅ 真 Nuitka onedir 编译（工具链 + 全后端 exe 真 serving + 功能正确 + M-015 校验）；
  顺带从真编译里抓出 2 个真打包 bug（相对导入 / pypinyin 包数据）并修进 M-015
- ✅ Electron 运行时真跑（截图实证全栈）
- ✅ NSIS 安装包真产出（139MB）+ 打包应用真跑（内置编译后端，无 .venv）
- 剩 #21 终极验收的**唯一人工环节**：找个真不懂代码的人，亲手双击安装包 → 走到学完第一课。
  **技术链路 100% 打通**（可编译后端真 serving + 可启动 Electron + 真安装包 + 打包应用自包含真跑）；
  缺的只是一个真人——这是 AI 无法替代的部分，不是技术阻塞。
