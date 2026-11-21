import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  test.setTimeout(300_000) // LibreOffice räknar om fem prognosfiler
  // Förbered data: samla in SKR:s skatteunderlagsprognoser från inspelningen (#61).
  const api = `http://127.0.0.1:${API_PORT}`
  expect((await request.post(`${api}/api/auth/test/redaktor`)).ok()).toBeTruthy()
  const svar = await request.post(`${api}/api/insamlingar?kalla=skr-skatteunderlagsprognos`, { timeout: 300_000 })
  expect(svar.ok()).toBeTruthy()
})

test('skatteunderlagsprognosen är öppen och visar senaste cirkuläret i mnkr med källa', async ({ page }) => {
  await page.goto('/ekonomi')
  await page.getByRole('link', { name: 'Skatteunderlagsprognos' }).click()
  await expect(page).toHaveURL(/\/ekonomi\/skatteunderlag$/)

  // Ingen inloggning krävs för att läsa.
  await expect(page.getByTestId('anvandare').getByRole('button', { name: 'Logga in' })).toBeVisible()

  const senaste = page.getByTestId('senaste-prognos')
  await expect(senaste.getByRole('heading', { name: 'Senaste prognosen, cirkulär 26:28' })).toBeVisible()
  await expect(senaste).toContainText('Publicerad 6 okt 2026')
  await expect(senaste).toContainText('23,34 %')

  const tabell = senaste.getByTestId('prognostabell')
  await expect(tabell.getByRole('columnheader', { name: '2033' })).toBeVisible()
  // Summa intäkter inklusive avräkning och fastighetsavgift 2027: 2 222 069 tkr.
  await expect(tabell.locator('[data-rad="summa_inkl"]')).toContainText(/2\s222,1 mnkr/)
  await expect(tabell.locator('[data-rad="invanare"]')).toContainText(/24\s360/)

  const kalla = senaste.getByRole('link', { name: 'Prognosunderlag-K-2026-2033-26028.xlsm' })
  await expect(kalla).toHaveAttribute('href', /skr\.se\/download\/.*26028\.xlsm$/)
})

test('diagrammet har en linje per cirkulär, tabellvy och CSV', async ({ page }) => {
  await page.goto('/ekonomi/skatteunderlag')
  const diagram = page.getByTestId('prognosdiagram')
  await expect(diagram.locator('path.linje')).toHaveCount(5)
  await expect(diagram.getByLabel('Teckenförklaring')).toContainText('Cirkulär 26:12')

  // Tooltip vid hover med år, värde, enhet och källa.
  await diagram.locator('svg').hover()
  const tips = diagram.getByRole('status')
  await expect(tips).toContainText('mnkr')
  await expect(tips).toContainText('SKR')

  await diagram.getByText('Visa som tabell').click()
  await expect(diagram.getByTestId('cirkulartabell').locator('tbody tr')).toHaveCount(5)

  const nedladdning = page.waitForEvent('download')
  await diagram.getByTestId('exportera').click()
  expect((await nedladdning).suggestedFilename()).toBe('skatteunderlagsprognoser-2280.csv')
})
