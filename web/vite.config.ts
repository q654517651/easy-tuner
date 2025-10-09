import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import svgr from 'vite-plugin-svgr'
import electron from 'vite-plugin-electron/simple'
import path from 'node:path'

// 后端端口配置（优先环境变量）
const BACKEND_PORT = process.env.VITE_BACKEND_PORT || '8000'
const BACKEND_TARGET = `http://localhost:${BACKEND_PORT}`

// https://vite.dev/config/
export default defineConfig({
  base: './', // Electron打包后使用相对路径
  plugins: [
    svgr(),
    react(),
    tailwindcss(),
    electron({
      main: { entry: "electron/main.ts" },
      preload: { input: { preload: "electron/preload.ts" } },
    }),
  ],
  build: {
    outDir: "dist", // 统一使用dist目录
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'), // 让 @ 指向 src/
    },
  },
  server: {
    proxy: {
      // 通用代理配置
      '^/(api|ws|workspace|health|healthz|readyz)': {
        target: BACKEND_TARGET,
        changeOrigin: true,
        ws: true, // 支持 WebSocket
      },
    },
  },
})
