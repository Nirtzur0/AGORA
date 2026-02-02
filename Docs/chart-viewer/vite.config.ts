import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  // So `dist/index.html` can be opened directly (file://) without a dev server.
  base: './',
  plugins: [react()],
})
