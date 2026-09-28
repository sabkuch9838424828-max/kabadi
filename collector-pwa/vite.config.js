import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// The Collector PWA is served on the public port 12000 and proxies the FastAPI
// backend, so the browser never needs direct access to the backend port.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      includeAssets: ['icons/icon-192.png', 'icons/icon-512.png'],
      manifest: {
        name: 'Kabadiwala Connect — Collector',
        short_name: 'Kabadiwala',
        description:
          'Composition-aware, offline-tolerant e-waste collection app for informal collectors (SIH26229).',
        theme_color: '#0f766e',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        lang: 'hi',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any maskable' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
        ]
      },
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,png,svg,ico,json}']
      },
      devOptions: { enabled: false }
    })
  ],
  server: {
    host: '0.0.0.0',
    port: 12000,
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
    port: 12000,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
