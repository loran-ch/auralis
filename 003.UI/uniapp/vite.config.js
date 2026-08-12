import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8002',
      '/health': 'http://127.0.0.1:8002',
      '/uploads': 'http://127.0.0.1:8002',
    },
  },
})
