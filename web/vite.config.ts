import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import svgr from 'vite-plugin-svgr'
import electron from 'vite-plugin-electron/simple'
import path from 'node:path'

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
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/workspace': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
