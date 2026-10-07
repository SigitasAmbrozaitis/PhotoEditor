import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Backend (photoedit ui / uvicorn) address used by the dev-server proxy.
const BACKEND = process.env.PHOTOEDIT_BACKEND ?? 'http://127.0.0.1:8765'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
