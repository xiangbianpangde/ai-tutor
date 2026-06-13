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
  // 开发期用仓库 .venv 的解释器；可经 AITUTOR_PYTHON 覆盖。打包后换内置 python（C5）。
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
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
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
});

ipcMain.handle('get-backend-url', () => BACKEND_URL);

app.on('before-quit', () => backendProc && backendProc.kill());
app.on('window-all-closed', () => {
  if (backendProc) backendProc.kill();
  if (process.platform !== 'darwin') app.quit();
});
