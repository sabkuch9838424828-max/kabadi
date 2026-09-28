import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Recycler Console is at /console, Ministry Dashboard at /dashboard.
// Served on public port 12001, proxying /api to the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 12001,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  preview: {
    host: '0.0.0.0',
    port: 12001,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
