'use strict';
// 预加载脚本：经 contextBridge 给渲染层暴露最小安全 API（不开 nodeIntegration）。

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('aitutor', {
  // 主进程健康检查结束后推送 { ready, url } 或 { ready:false, error }
  onBackendStatus: (cb) => ipcRenderer.on('backend-status', (_event, status) => cb(status)),
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
});
