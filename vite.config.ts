import { defineConfig } from 'vitest/config';
import { VitePWA } from 'vite-plugin-pwa';

// GitHub Pages serves the project under /<repo>/; override with BASE_PATH for other hosts.
const base = process.env.BASE_PATH ?? '/';

export default defineConfig({
  base,
  plugins: [
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg', 'apple-touch-icon.png'],
      workbox: {
        // The normal-density art ships with the app for offline play; the sharp
        // @2x sheets are fetched and kept only once a player zooms in.
        globPatterns: ['**/*.{js,css,html,svg,png,ico,webmanifest}', 'art/towers.json', 'art/**/*@1x.{webp,json}', 'art/portraits.json', 'art/portraits/*.webp'],
        runtimeCaching: [
          {
            urlPattern: /\/art\/.*@2x\.(webp|json)$/,
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'art-2x', expiration: { maxEntries: 60 } },
          },
        ],
      },
      manifest: {
        name: 'Стрелите',
        short_name: 'Стрелите',
        description: 'Tower defence',
        lang: 'bg',
        start_url: '.',
        scope: '.',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#141a12',
        theme_color: '#141a12',
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
  test: { include: ['tests/**/*.test.ts'] },
});
