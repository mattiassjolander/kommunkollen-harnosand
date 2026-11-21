import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// /api och kalenderflödena (/kalender/….ics) skickas vidare till backend. Porten kan ändras med API_PORT (e2e kör egen backend).
const apiPort = process.env.API_PORT ?? '8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': `http://127.0.0.1:${apiPort}`,
      '^/kalender/.+\\.ics$': `http://127.0.0.1:${apiPort}`,
    },
  },
})
