import { defineConfig, devices } from '@playwright/test'

// Söm 2: frontend mot en riktig backend som hämtar från inspelade källsvar.
// Backend använder DATABASE_URL om den är satt (CI), annars en inbäddad Postgres.
const API_PORT = '8010'
const WEB_PORT = '5180'

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
