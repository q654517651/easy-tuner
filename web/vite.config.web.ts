import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import svgr from 'vite-plugin-svgr'
import path from 'node:path'

// 后端端口配置（优先环境变量）
const BACKEND_PORT = process.env.VITE_BACKEND_PORT || '8000'
const BACKEND_TARGET = `http://localhost:${BACKEND_PORT}`

// https://vite.dev/config/
// 云服务器专用配置（不包含 Electron）
export default defineConfig({
  base: '/', // Web模式使用绝对路径
  plugins: [
    svgr(),
    react(),
    tailwindcss(),
    // 注意：不包含 electron 插件，适用于云服务器部署
  ],
  build: {
    outDir: "dist",
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0', // 允许外部访问
    port: 6006, // 云服务器端口
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

