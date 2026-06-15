'use strict';
// AI-Tutor 桌面客户端主进程（M-003 客户端入口）。
// 职责：spawn Python 后端 → 轮询 /api/knowledge/health（15s 超时，spec 04 场景2）
//       → 就绪后把状态推给渲染层。打包形态（内置解释器）见 C5 / M-015。

const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('node:child_process');
const path = require('node:path');
const http = require('node:http');

const HOST = '127.0.0.1';
const PORT = Number(process.env.AITUTOR_PORT || 18501);
const BACKEND_URL = `http://${HOST}:${PORT}`;
const HEALTH_PATH = '/api/knowledge/health';
const HEALTH_TIMEOUT_MS = 15000; // spec 04 场景2：超 15s 显示“后端启动失败”
const REPO_ROOT = path.resolve(__dirname, '..');

let backendProc = null;
let mainWindow = null;

function startBackend() {
  if (app.isPackaged) {
    // 打包形态（C5/M-015）：spawn 内置 Nuitka onedir 后端 exe（resources/backend/）。
    const exe = path.join(
      process.resourcesPath, 'backend',
      process.platform === 'win32' ? 'ai-tutor-backend.exe' : 'ai-tutor-backend',
    );
    backendProc = spawn(exe, [], {
      cwd: path.dirname(exe),
      env: { ...process.env, NO_PROXY: '*' },
      stdio: 'inherit',
    });
  } else {
    // 开发期用仓库 .venv 的解释器；可经 AITUTOR_PYTHON 覆盖。
    const defaultPython = path.join(
      REPO_ROOT,
      '.venv',
      process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
    );
    const python = process.env.AITUTOR_PYTHON || defaultPython;
    backendProc = spawn(python, ['-m', 'backend.main'], {
      cwd: REPO_ROOT,
      env: { ...process.env, NO_PROXY: '*' }, // 死系统代理绕法（见持久记忆）
      stdio: 'inherit',
    });
  }
  backendProc.on('exit', (code) => console.log(`[backend] exited code=${code}`));
}

function pollHealth(deadline) {
  return new Promise((resolve) => {
    const retry = () => (Date.now() > deadline ? resolve(false) : setTimeout(attempt, 500));
    const attempt = () => {
      const req = http.get(`${BACKEND_URL}${HEALTH_PATH}`, (res) => {
        res.resume();
        if (res.statusCode === 200) resolve(true);
        else retry();
      });
      req.on('error', retry);
      req.setTimeout(1000, () => req.destroy());
    };
    attempt();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 760,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  // 优先加载 Vite 构建产物（renderer/dist）；未构建时回退到源 index.html 提示。
  // 开发期可设 AITUTOR_RENDERER_URL=http://localhost:5173 用 Vite dev server（热更新）。
  const devUrl = process.env.AITUTOR_RENDERER_URL;
  if (devUrl) {
    mainWindow.loadURL(devUrl);
  } else {
    const built = path.join(__dirname, 'renderer', 'dist', 'index.html');
    const fallback = path.join(__dirname, 'renderer', 'index.html');
    mainWindow.loadFile(require('node:fs').existsSync(built) ? built : fallback);
  }
}

app.whenReady().then(async () => {
  createWindow();
  startBackend();
  const ready = await pollHealth(Date.now() + HEALTH_TIMEOUT_MS);
  if (mainWindow) {
    mainWindow.webContents.send(
      'backend-status',
      ready
        ? { ready: true, url: BACKEND_URL }
        : { ready: false, error: '后端启动失败（15 秒未就绪）' },
    );
  }

  // 验证模式（AITUTOR_VERIFY=<png 路径>）：渲染完成后截图并退出。CI/无人值守真跑验证用。
  if (process.env.AITUTOR_VERIFY && mainWindow) {
    const out = process.env.AITUTOR_VERIFY;
    const fs = require('node:fs');
    await new Promise((r) => setTimeout(r, 2500)); // 等 React 渲染 + 首次数据拉取
    try {
      const img = await mainWindow.webContents.capturePage();
      fs.writeFileSync(out, img.toPNG());
      console.log(`[verify] screenshot -> ${out}`);
    } catch (e) {
      console.log(`[verify] capture failed: ${e}`);
    }
    app.quit();
  }
});

ipcMain.handle('get-backend-url', () => BACKEND_URL);

app.on('before-quit', () => backendProc && backendProc.kill());
app.on('window-all-closed', () => {
  if (backendProc) backendProc.kill();
  if (process.platform !== 'darwin') app.quit();
});
