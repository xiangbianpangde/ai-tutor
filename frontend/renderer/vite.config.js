import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base './' → 产物用相对路径，Electron file:// 直接加载（onedir 打包友好）
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
  server: { port: 5173 },
});
