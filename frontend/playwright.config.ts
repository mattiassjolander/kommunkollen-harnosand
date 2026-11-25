import { defineConfig, devices } from '@playwright/test'

// Söm 2: frontend mot en riktig backend som hämtar från inspelade källsvar.
// Backend använder DATABASE_URL om den är satt (CI), annars en inbäddad Postgres.
// Portarna kan ändras med E2E_API_PORT och E2E_WEB_PORT, t.ex. när flera arbetskopior kör testerna samtidigt.
const API_PORT = process.env.E2E_API_PORT || '8010'
const WEB_PORT = process.env.E2E_WEB_PORT || '5180'

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  // Testfilerna delar en databas och startar insamlingar, så de körs efter varandra.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `uv run --directory ../backend kommunkollen-dev --port ${API_PORT} --inspelningar tests/recordings --databas .e2e-db --budgetforslag tests/fixtures/budgetforslag`,
      url: `http://127.0.0.1:${API_PORT}/api/halsa`,
      // Kalendern visar kommande sammanträden. Dagens datum låses så att testerna inte beror på när de körs.
      // Vektorsökningen (#69) med testmodellen: söm 2 behöver inte språkmodellen. Inspelningarna har en fil per
      // rubrik på sidan med kommunens styrande dokument (#63).
      env: { KOMMUNKOLLEN_IDAG: '2026-11-20', SOKMODELL: 'test', STYRANDE_URVAL: '1' },
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort --host 127.0.0.1`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { API_PORT },
      reuseExistingServer: !process.env.CI,
    },
  ],
})

export { API_PORT }
