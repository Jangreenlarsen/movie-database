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
      // Feature #190 — den automatisk indsatte standard-registrering tjekker
      // kun for en ny version ved en rigtig sideindlæsning/navigation, hvilket
      // for en PWA der bliver stående åben i lang tid (typisk "Føj til
      // hjemmeskærm" på Jans iPhone) kan betyde at en ny version aldrig
      // opdages før appen selv lukkes og genåbnes. `src/pwa.js` registrerer
      // derfor selv service workeren, med et periodisk `registration.update()`-
      // tjek lagt oveni (se den fil for detaljer) — kræver at pluginets EGEN
      // auto-injicerede script slås fra her, ellers registreres SW'en to gange.
      injectRegister: false,
      includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
      workbox: {
        // BUGS.md #102 — SKAL stå eksplicit. vite-plugin-pwa sætter kun
        // disse to af sig selv ved `autoUpdate` når `injectRegister` er
        // "auto"; med `injectRegister: false` ovenfor (feature #190) blev de
        // stille udeladt, og hver ny version lå så i "waiting" indtil ALLE
        // faner med appen var lukket — derfor krævede en ny version et hard
        // reload. Med dem aktiveres en ny service worker straks, overtager
        // de åbne sider, og `registerSW` genindlæser dem (pwa.js).
        skipWaiting: true,
        clientsClaim: true,
        // BUGS.md #68 — uden denne ekskludering fanger service workerens
        // NavigationRoute (workbox' SPA-fallback) ALLE top-niveau-
        // navigationer, ogsaa direkte "aabn i ny fane"-links til statiske
        // filer (PDF/billeder/video i /cinema/, feature #160), og serverer
        // index.html i stedet for selve filen -- appen sprang derfor
        // "tilbage" til hovedsiden i stedet for at vise filen. En sti der
        // ender paa en filendelse er per definition aldrig en SPA-rute.
        navigateFallbackDenylist: [/\.[^/?]+$/],
      },
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
          {
            src: '/pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/pwa-maskable-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  // Feature #103 — Vitest laeser denne config, saa test-opsaetningen bor her
  // frem for i en egen vitest.config.js: aliasser, plugins og alt andet der
  // gaelder for appen gaelder saa ogsaa i testene, uden at skulle holdes ens
  // to steder.
  test: {
    // jsdom frem for node: komponent-testene skal bruge et DOM at rendere i.
    environment: 'jsdom',
    // Goer describe/it/expect globale, saa testfilerne ligner backendens
    // pytest-filer: ingen import-stoej oeverst i hver fil.
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
    // PWA-pluginet genererer en service worker ved build. Under test er det
    // ren stoej, og det skriver filer til dist/.
    exclude: ['node_modules', 'dist'],
  },
})
