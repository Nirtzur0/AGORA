import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const coreApiTarget = process.env.AGORA_CORE_API_URL || 'http://127.0.0.1:18000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: coreApiTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
