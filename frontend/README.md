# AI-Tutor 桌面客户端（frontend/）

C1 第一波交付的**客户端入口骨架**（M-003）。当前只做三件事：

1. `app.whenReady` 后开窗 + `spawn` Python 后端（`python -m backend.main`）；
2. 轮询 `GET /api/knowledge/health`，**15 秒**未就绪显示“后端启动失败”（spec 04 场景2）；
3. 就绪后渲染层探测四引擎 health,展示连接状态。

后续波次再补 spec 04 的完整能力：5 页面路由 / 仪表盘 / 首次向导 / WebSocket 实时教学 + 断线重连。

## 运行（开发期）

```bash
cd frontend
npm install          # 下载 electron（较大；死代理时先设 NO_PROXY）
npm run check        # node 语法自检 main.js / preload.js（无需 electron）
npm start            # 启动 Electron，自动拉起后端
```

- 后端解释器默认用仓库 `.venv`；可用 `AITUTOR_PYTHON` 覆盖，`AITUTOR_PORT` 改端口（默认 18501）。
- 打包形态（内置 Python 解释器、不依赖系统 .venv）属 C5 / M-015，用 **Nuitka onedir**（非 PyInstaller，R-01 证伪）。

## 安全基线

- `contextIsolation: true` + `nodeIntegration: false`，渲染层只经 `preload.js` 的 `window.aitutor` 拿最小 API。
- CSP 限定 `connect-src` 仅本地后端。
