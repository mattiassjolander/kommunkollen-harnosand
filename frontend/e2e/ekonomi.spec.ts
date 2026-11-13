import { expect, test } from '@playwright/test'
import { API_PORT } from '../playwright.config'

test.beforeAll(async ({ request }) => {
  // Förbered data: kör en insamling mot de inspelade Kolada-svaren.
  const svar = await request.post(`http://127.0.0.1:${API_PORT}/api/insamlingar`)
  expect(svar.ok()).toBeTruthy()
})

test('ekonomivyn visar årets resultat som tidsserie med källrad', async ({ page }) => {
  await page.goto('/ekonomi')

  const kort = page.getByTestId('nyckeltal')
  await expect(kort.getByRole('heading', { name: 'Årets resultat kommun, kr/inv' })).toBeVisible()

  // Standardvisning från 2022: 2022–2025 i inspelningen.
  await expect(kort.getByTestId('stapel')).toHaveCount(4)

  const kallrad = page.getByTestId('kallrad')
  await expect(kallrad).toContainText('Kolada')
  await expect(kallrad).toContainText('N03007')
  await expect(kallrad).toContainText('Avser 2022–2025')
  await expect(kallrad).toContainText('Publicerad 28 aug 2026')

  // Tooltip vid hover visar år, värde med enhet och källa.
  const yta = kort.locator('rect.traffyta').last()
  await yta.hover()
  const tips = page.getByRole('tooltip')
  await expect(tips).toContainText('2025')
  await expect(tips).toContainText('972 kr/inv')
  await expect(tips).toContainText('Kolada')
})
