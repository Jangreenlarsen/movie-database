import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

const certDir = fileURLToPath(new URL('./.cert', import.meta.url))
const keyPath = `${certDir}/key.pem`
const certPath = `${certDir}/cert.pem`

// HTTPS is required for camera access (getUserMedia) from any device that
// isn't literally "localhost" — e.g. testing the scan flow from a phone
// over the LAN. Generate certs with (from frontend/):
//   mkdir .cert && cd .cert && openssl req -x509 -newkey rsa:2048 -nodes \
//     -keyout key.pem -out cert.pem -days 365 -subj "/CN=movie-database-dev" \
//     -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:<your-lan-ip>"
// Self-signed, so phones will show a security warning — accept it to continue.
const httpsConfig =
  existsSync(keyPath) && existsSync(certPath)
    ? { key: readFileSync(keyPath), cert: readFileSync(certPath) }
    : undefined

// https://vite.dev/config/
export default defineConfig({
  server: {
    host: true,
    https: httpsConfig,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Film & TV-database',
        short_name: 'Film & TV',
        description: 'Personligt film- og TV-serie-bibliotek med stregkode-scanning og tags',
        start_url: '/',
        display: 'standalone',
        background_color: '#0f0f0f',
        theme_color: '#0f0f0f',
        icons: [
          {
            src: '/favicon.svg',
            sizes: 'any',
            type: 'image/svg+xml',
          },
        ],
      },
    }),
  ],
})
