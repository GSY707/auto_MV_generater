import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        timeout: 600000,
        proxyTimeout: 600000,
        configure: (proxy) => {
          // 不缓冲响应，支持大文件流式传输
          proxy.on('proxyRes', (proxyRes) => {
            // 确保 Range 请求正确传递
            const ct = proxyRes.headers['content-type'] || ''
            if (ct.startsWith('video/') || ct === 'application/octet-stream') {
              proxyRes.headers['accept-ranges'] = 'bytes'
            }
          })
        },
      }
    }
  }
})
